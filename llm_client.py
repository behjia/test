import os
import json
import re
import shutil
from enum import Enum
from pathlib import Path
import ast
import litellm
from litellm import completion
import instructor
from dotenv import load_dotenv
from pydantic import ValidationError
from models import HardwareSpec
from rag_agent import HardwareRAG

# Silence litellm's verbose success messages; keep warnings/errors
litellm.success_callback = []

# Load local .env file if it exists
load_dotenv()


# ==========================================================================
# Expert Tier Definitions
# ==========================================================================

class ExpertTier(Enum):
    """Maps logical complexity tiers to primary/fallback model pairs.

    Cost optimisation strategy
    --------------------------
    TIER_GRUNT     – Cheapest/fastest; ideal for first-pass fixes and
                     boilerplate generation. Falls back to Gemini Pro if
                     Flash is rate-limited.
    TIER_CODER     – Mid-tier; handles non-trivial RTL with nuanced logic.
                     Falls back to Gemini Pro under rate pressure.
    TIER_ARCHITECT – Heavy reasoning; reserved for multi-retry escalation
                     where cheaper models have already failed. No fallback
                     (Opus is the ceiling).
    """
    TIER_GRUNT     = ("gemini/gemini-3.1-flash-lite-preview",    "claude-haiku-4-5-20251001")
    TIER_CODER     = ("claude-sonnet-4-5-20250929", "gemini/gemini-3.1-pro-preview")
    TIER_ARCHITECT = ("claude-sonnet-4-5-20250929",        None)   # No fallback
    # Preferred LiteLLM-native NVIDIA route:
    TIER_HARDWARE_ORACLE = ("nvidia_nim/meta/llama-3.1-70b-instruct", None)

    @property
    def primary(self) -> str:
        return self.value[0]

    @property
    def fallback(self) -> str | None:
        return self.value[1]


# ==========================================================================
# MoE Router Client
# ==========================================================================

class MoE_Client:
    """Mixture-of-Experts router that wraps litellm.completion.

    All model calls go through ``route_task()``, which:
    1. Attempts the *primary* model for the requested tier.
    2. Catches :class:`litellm.exceptions.RateLimitError` and
       transparently retries on the tier's *fallback* model.
    3. Re-raises any other exception so the caller can handle it.
    """

    def __init__(self, default_system_prompt: str = ""):
        self.default_system_prompt = default_system_prompt
        self.nvidia_api_key = os.getenv("NVIDIA_API_KEY")
        self.nvidia_api_base = os.getenv("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1")

    def _provider_kwargs(self, model_name: str | None) -> dict:
        if not model_name:
            return {}

        is_nvidia = (
            model_name.startswith("nvidia_nim/")
            or model_name == "openai/nvidia/llama-3.1-70b-instruct"
        )
        if not is_nvidia:
            return {}

        if not self.nvidia_api_key:
            raise ValueError("NVIDIA_API_KEY is required for NVIDIA NIM routing.")

        return {
            "api_base": self.nvidia_api_base,
            "api_key": self.nvidia_api_key,
        }

    # ------------------------------------------------------------------
    # Core routing primitive
    # ------------------------------------------------------------------
    def route_task(
        self,
        prompt: str,
        tier: ExpertTier,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> str:
        """Route a prompt through the model tier with automatic rate-limit fallback.

        Parameters
        ----------
        prompt:
            The user-turn message.
        tier:
            An :class:`ExpertTier` member that determines which models to use.
        system_prompt:
            Overrides the client-level default system prompt when provided.
        max_tokens:
            Maximum tokens for the response.
        temperature:
            Sampling temperature.

        Returns
        -------
        str
            Raw text content of the model response.

        Raises
        ------
        litellm.exceptions.RateLimitError
            Raised only when *both* primary and fallback are rate-limited
            (or when there is no fallback defined for the tier).
        Exception
            Any other API or network error is re-raised immediately.
        """
        sys_msg = system_prompt if system_prompt is not None else self.default_system_prompt
        messages = []
        if sys_msg:
            messages.append({"role": "system", "content": sys_msg})
        messages.append({"role": "user", "content": prompt})

        # ---- Attempt primary model ----
        try:
            print(f"    [MoE] Routing to PRIMARY  → {tier.primary}")
            response = completion(
                model=tier.primary,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **self._provider_kwargs(tier.primary),
            )
            return response.choices[0].message.content

        except litellm.exceptions.RateLimitError as primary_err:
            if tier.fallback is None:
                print(f"    [MoE] ⚠️  Rate-limited on {tier.primary}; no fallback configured.")
                raise

            print(
                f"    [MoE] ⚠️  Rate-limited on {tier.primary}. "
                f"Falling back to → {tier.fallback}"
            )

        # ---- Attempt fallback model ----
        try:
            response = completion(
                model=tier.fallback,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **self._provider_kwargs(tier.fallback),
            )
            return response.choices[0].message.content

        except litellm.exceptions.RateLimitError:
            print(f"    [MoE] ❌  Rate-limited on fallback {tier.fallback} as well. Giving up.")
            raise

    # ------------------------------------------------------------------
    # Tier-selection helper (escalation routing)
    # ------------------------------------------------------------------
    @staticmethod
    def tier_for_retry(retry_count: int) -> ExpertTier:
        """Return the appropriate :class:`ExpertTier` based on retry depth.

        Escalation table
        ----------------
        retry_count == 0  →  TIER_GRUNT     (cheapest, fastest)
        retry_count == 1  →  TIER_CODER     (mid-tier Sonnet)
        retry_count >= 2  →  TIER_ARCHITECT (Opus — last resort)
        """
        if retry_count == 0:
            return ExpertTier.TIER_GRUNT
        elif retry_count == 1:
            return ExpertTier.TIER_CODER
        else:
            return ExpertTier.TIER_ARCHITECT
# ==========================================================================
# EDA LLM Client  (now backed by MoE_Client)
# ==========================================================================

class EDA_LLM_Client:
    def __init__(self, rag: HardwareRAG | None = None):
        """Initialise the EDA client.

        API keys are read from environment variables (via .env):
        - ANTHROPIC_API_KEY  — required for Claude models
        - GEMINI_API_KEY     — required for Gemini models (or use GOOGLE_API_KEY)

        Parameters
        ----------
        rag:
            Optional :class:`~rag_agent.HardwareRAG` instance.  When provided,
            ``generate_variations`` will retrieve relevant spec rules from the
            vector DB and inject them into the system prompt before every
            RTL generation call.  Pass ``None`` (default) to run without RAG.
        """
        # Validate that at least Anthropic key is present (Gemini is optional
        # but strongly recommended for the fallback / TIER_GRUNT primary).
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("CRITICAL: ANTHROPIC_API_KEY environment variable is not set.")

        self.system_prompt = (
            "You are an expert ASIC and FPGA Digital Design Engineer. "
            "Your job is to generate highly optimized, synthesizable SystemVerilog code. "
            "CRITICAL RULES:\n"
            "1. You must output ONLY the requested code or JSON. \n"
            "2. DO NOT include markdown formatting (like ```verilog or ```json) unless explicitly requested. \n"
            "3. DO NOT include conversational filler, greetings, or explanations. \n"
            "4. Ensure all modules have explicit input/output port width declarations."
        )

        # MoE router — single entry-point for all model calls
        self.moe = MoE_Client(default_system_prompt=self.system_prompt)

        # Instructor-patched litellm client for structured Pydantic extraction
        # (instructor supports litellm natively via instructor.from_litellm)
        self.instructor_client = instructor.from_litellm(completion)

        # Explicitly use Claude for Pydantic/Instructor tasks to avoid Gemini tool-call bugs
        self.spec_model = "claude-sonnet-4-5-20250929"

        # Optional RAG agent — set to None to disable context retrieval
        self.rag: HardwareRAG | None = rag

    @staticmethod
    def extract_python_code(raw_text: str) -> str:
        """Ruthlessly extracts Python code, destroying any and all LLM Markdown."""
        text = raw_text.strip()
        # 1. Look for code inside markdown blocks
        match = re.search(r"```(?:python)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
        if match:
            text = match.group(1)
        else:
            text = text.replace("```python", "").replace("```", "")
        
        text = text.strip()
        # 2. Destroy the loose word 'python' if it is sitting at the very start of the string
        text = re.sub(r"^python\b", "", text, flags=re.IGNORECASE).strip()
        return text
    # ------------------------------------------------------------------
    # Structured spec generation (now powered by Pydantic + Instructor)
    # ------------------------------------------------------------------
    def generate_spec(self, user_request: str) -> HardwareSpec | str:
        """Translate a natural-language hardware request into a validated
        ``HardwareSpec`` Pydantic model.

        Returns
        -------
        HardwareSpec
            On success — a fully-validated spec object.
        str
            On failure — a human-readable error message.
        """
        print(f"[SYSTEM] Translating request to HardwareSpec using {self.spec_model}...")
        prompt = (
            "You are a systems architect. Convert the following user request "
            "into a strict hardware architecture specification.\n\n"
            f'User Request: "{user_request}"\n\n'
            "Return the specification as valid JSON conforming to the schema.\n"
            "CRITICAL RULE 1 - GOLDEN MODEL:\n"
            "The 'golden_model_python' field MUST be a single function named 'golden_model(state, inputs)'.\n"
            "It returns a tuple: (updated_state, expected_outputs_dict).\n"
            "CRITICAL RULE 2 - TEST VECTOR GENERATOR:\n"
            "The 'test_vector_generator_python' field MUST contain PURE Python code (no markdown).\n"
            "It MUST be a single function named 'generate_test_vectors()'.\n"
            "It MUST return a list of exactly 100 dictionaries, where each dictionary represents the 'inputs' for one clock cycle.\n"
            "The generator MUST mix purely random noise with highly constrained, valid edge-cases (e.g., valid RISC-V opcodes, or valid AXI handshakes) to ensure 100% coverage of the internal logic.\n"
            "Example:\n"
            "def generate_test_vectors():\n"
            "    import random\n"
            "    vectors = []\n"
            "    for i in range(100):\n"
            "        # Mix 80% valid opcodes and 20% random garbage\n"
            "        vectors.append({'instruction': random.choice([0x00000033, 0x00000013, random.randint(0, 0xFFFFFFFF)])})\n"
            "    return vectors\n"
        )
        try:
            spec: HardwareSpec = self.instructor_client.chat.completions.create(
                model=self.spec_model,
                max_tokens=4096,                # Increased to 4096
                max_retries=2,                  # instructor auto-retries on validation failure
                temperature=0.1,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user",   "content": prompt},
                ],
                response_model=HardwareSpec,    # ← Pydantic extraction
            )
            # SAFETY SCRUBBER: Ruthlessly extract python code and strip markdown
            spec.golden_model_python = self.extract_python_code(spec.golden_model_python)
            spec.test_vector_generator_python = self.extract_python_code(spec.test_vector_generator_python) # <--- NEW SCRUBBER

            print("✅ SUCCESS: Valid HardwareSpec generated.")
            return spec

        except ValidationError as e:
            error_msg = f"❌ VALIDATION ERROR: LLM output did not match HardwareSpec schema.\n{e}"
            print(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ ERROR: An unexpected error occurred: {e}"
            print(error_msg)
            return error_msg
    
    def review_and_fix_spec(self, spec: HardwareSpec) -> HardwareSpec:
        """Acts as a Senior Software Engineer to verify the Python Golden Model is mathematically sound."""
        print("[SYSTEM] Reviewer Agent analyzing Python Golden Model...")
        
        # Save the original code in case the Reviewer Agent hallucinates!
        original_code = spec.golden_model_python 
        
        prompt = (
            "You are a Senior Python QA Engineer. Review this proposed Golden Reference Model for a hardware testbench.\n"
            f"Module: {spec.module_name}, Sequential: {spec.is_sequential}\n\n"
            f"```python\n{spec.golden_model_python}\n```\n\n"
            "CRITICAL CHECK:\n"
            "1. The model MUST be a single function named exactly 'def golden_model(state, inputs):'. Do NOT use classes.\n"
            "2. It must return a tuple of two dictionaries: (updated_state, outputs_dict).\n"
            "3. It must not call any undefined helper functions.\n"
            "If the code violates ANY of these rules, rewrite it perfectly.\n"
            "CRITICAL: You MUST wrap your Python code inside a ```python ... ``` block. "
            "If the code is already perfect, output it inside a ```python ... ``` block anyway. Do not output conversational text."
        )
        
        try:
            # UPGRADE: Force the Reviewer to use Claude Sonnet (TIER_ARCHITECT) for perfect Python syntax
            fixed_code = self.moe.route_task(
                prompt=prompt,
                tier=ExpertTier.TIER_ARCHITECT, 
                max_tokens=1500,
                temperature=0.1
            )
            
            cleaned_code = self.extract_python_code(fixed_code)
            
            try:
                # We execute the code in a blank dictionary to ensure it doesn't crash on import
                exec(cleaned_code, {})
                spec.golden_model_python = cleaned_code
                print("✅ [REVIEWER] Golden Model syntax AND runtime semantics verified.")
            except Exception as runtime_err:
                print(f"❌ [REVIEWER] Python Runtime Error detected in reviewed code: {type(runtime_err).__name__} - {runtime_err}")
                print("⚠️ [REVIEWER] Reverting to original Golden Model generated in Phase 1.")
                # FIX: Fallback to the original Sonnet code, NOT a blank dictionary!
                spec.golden_model_python = original_code
                
        except Exception as e:
            print(f"⚠️ [REVIEWER] API failed, proceeding with original spec. Error: {e}")
            spec.golden_model_python = original_code
        
        return spec

    # ------------------------------------------------------------------
    # RTL variation generation (unchanged — free-form text output)
    # ------------------------------------------------------------------
    def generate_variations(self, spec: HardwareSpec | dict, num_variations: int = 3):
        spec_dict = spec.model_dump() if isinstance(spec, HardwareSpec) else spec
        print(
            f"\n[SYSTEM] Generating {num_variations} RTL variations using "
            f"Claude Sonnet (TIER_CODER)..."
        )
        variations = []

        # 1. Check if the Planner Agent decided this needs a clock
        is_seq = spec_dict.get("is_sequential", False)
        if is_seq:
            timing_rules = (
                "1. This is a SEQUENTIAL design. You MUST include a 'clk' input.\n"
                "2. Use standard synchronous design practices (always_ff @(posedge clk)).\n"
                "3. Ensure proper reset behavior if an rst or rst_n port is specified."
            )
        else:
            timing_rules = (
                "1. This design must be PURELY COMBINATIONAL. Do NOT use clk, rst, or any sequential logic.\n"
                "2. Use always_comb with logic type variables, or pure assign statements.\n"
                "3. Include an 'initial begin #1; end' block for Verilator VM_TIMING compatibility.\n"
                "4. CRITICAL SYNTHESIS RULE: You MUST wrap any timing constructs (like #1) in an ifndef block so synthesis tools ignore them. Like this:\n"
                "   `ifndef SYNTHESIS\n"
                "   initial begin #1; end\n"
                "   `endif"
            )

        # 2. Extract the dynamic DSE strategies generated by the Planner Agent
        strategies = spec_dict.get("dse_strategies", [
            "Write standard behavioral RTL.", "Focus on area.", "Focus on speed."
        ])

        # ------------------------------------------------------------------
        # 3. RAG CONTEXT RETRIEVAL
        # Build a semantic query from the spec so the vector DB can return
        # the most relevant opcode tables, bus rules, or timing constraints.
        # This block runs once per generate_variations() call, not per variation,
        # because all variations share the same architectural requirements.
        # ------------------------------------------------------------------
        rag_context_block = ""
        if self.rag is not None:
            rag_query = (
                f"{spec_dict.get('module_name', '')} "
                f"{spec_dict.get('description', '')} "
                f"{'sequential' if is_seq else 'combinational'}"
            ).strip()
            print(f"  [RAG] Querying vector DB with: '{rag_query[:80]}...'")
            retrieved = self.rag.retrieve_context(rag_query, n_results=3)
            if retrieved:
                rag_context_block = (
                    "\n\n=== RETRIEVED HARDWARE SPECIFICATIONS ===\n"
                    "The following rules are AUTHORITATIVE. They are extracted from\n"
                    "verified hardware specification documents. You MUST follow them\n"
                    "exactly. Do NOT invent opcodes, signal names, or bus rules.\n\n"
                    f"{retrieved}\n"
                    "=== END OF RETRIEVED SPECIFICATIONS ==="
                )
                print(f"  [RAG] ✅ Context injected ({len(rag_context_block)} chars).")
            else:
                print("  [RAG] ⚠️  No relevant rules found in DB. Proceeding without RAG context.")

        # Build the RAG-augmented system prompt once and reuse it for all
        # variations in this call.  When rag_context_block is empty (RAG
        # disabled or no results) this degrades gracefully to the base prompt.
        augmented_system_prompt = self.system_prompt + rag_context_block

        for i in range(num_variations):
            seed = strategies[i] if i < len(strategies) else strategies[0]
            print(f"  -> Generating Variation {i + 1} (Strategy: {seed[:40]}...)")

            prompt = f"""
            You are a master ASIC RTL designer. Implement the following module based STRICTLY on this JSON specification:
            {json.dumps(spec_dict, indent=2)}

            STRATEGY FOR THIS VARIATION:
            {seed}

            CRITICAL RULES:
            {timing_rules}
            4. The module must have ONLY the exact ports listed in the JSON. No extra ports.
            5. Output ONLY the raw SystemVerilog code. Do not explain anything.
            """
            try:
                raw_text = self.moe.route_task(
                    prompt=prompt,
                    tier=ExpertTier.TIER_CODER,
                    max_tokens=4096,
                    temperature=0.8,
                    system_prompt=augmented_system_prompt,  # ← RAG-injected
                )
                match = re.search(r"```(?:verilog|systemverilog)?(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
                clean_verilog = match.group(1).strip() if match else raw_text.strip()

                # SAFETY SCRUBBER: Remove hallucinated backtick macros before saving
                clean_verilog = clean_verilog.replace("`systemverilog\n", "")
                clean_verilog = clean_verilog.replace("`verilog\n", "")
                clean_verilog = clean_verilog.replace("`systemverilog", "")  # Catch it without the newline just in case

                variations.append(clean_verilog)
            except Exception as e:
                print(f"❌ ERROR on variation {i}: {e}")
                variations.append("module sync_fifo_16x32(); endmodule")
        return variations
    
    # ------------------------------------------------------------------
    # Self-healing fix (unchanged — free-form text output)
    # ------------------------------------------------------------------
    def fix_design(
        self,
        broken_code: str,
        error_log: str,
        testbench_code: str = "",
        is_sequential: bool = False,
        retry_count: int = 0,
    ) -> str:
        """Takes broken SystemVerilog code, its simulator error log, and
        optionally the testbench, then returns a corrected version.

        Escalation Routing
        ------------------
        The ``retry_count`` argument drives automatic model escalation via the
        MoE router so that costs stay minimal on the first attempt while
        progressively heavier models are engaged for stubborn failures:

        retry_count == 0  →  TIER_CODER     (Claude Sonnet)
        retry_count >= 1  →  TIER_ARCHITECT (Claude Opus — no fallback)

        Parameters
        ----------
        broken_code:
            The failing SystemVerilog source.
        error_log:
            Simulator / linter error output (Verilator, iverilog, etc.).
        testbench_code:
            Optional testbench source to give the model constraint context.
        is_sequential:
            When True, enforce sequential RTL rules; otherwise combinational.
        retry_count:
            Number of previous failed fix attempts — controls tier escalation.
        """
        if retry_count == 0:
            tier = ExpertTier.TIER_CODER
        else:
            tier = ExpertTier.TIER_ARCHITECT
        print(
            f"[SYSTEM] Attempting auto-fix "
            f"(retry #{retry_count} → {tier.name}, primary: {tier.primary})..."
        )

        # DYNAMIC CRITIC RULES
        if is_sequential:
            timing_rules = (
                "1. The design is SEQUENTIAL. You MUST use 'always_ff @(posedge clk)' for state/memory.\n"
                "2. Do NOT use 'assign' statements for variables updated inside an always_ff block.\n"
                "3. Ensure synchronous or asynchronous reset logic matches standard industry practices."
            )
        else:
            timing_rules = (
                "1. The design must be PURELY COMBINATIONAL. No clk, rst_n, or sequential logic.\n"
                "2. Use always_comb or assign statements ONLY.\n"
                "3. VERILATOR RULE: Any variable assigned inside always_comb MUST be declared as 'logic', NOT 'wire'."
            )

        fix_system_prompt = (
            "You are a Senior Design Verification Engineer. "
            "Your job is to analyze failed SystemVerilog code and the corresponding EDA simulator error log. "
            "You must output ONLY the fully corrected raw SystemVerilog code. "
            "Do not include markdown formatting, explanations, or conversational text.\n"
            "CRITICAL CONSTRAINTS:\n"
            f"{timing_rules}\n"
            "4. The module must have ONLY the ports the testbench uses. Do NOT add extra ports.\n"
            "5. Fix any MULTIDRIVEN, LATCH, or syntax errors reported by Verilator.\n"
            "6. CRITICAL SYNTHESIS RULE: You MUST wrap any timing constructs (like #1) in an ifndef block so synthesis tools ignore them. Like this:\n"
            "   `ifndef SYNTHESIS\n"
            "   initial begin #1; end\n"
            "   `endif"
        )

        prompt = (
            "The following SystemVerilog code has failed EDA verification.\n\n"
            "--- BROKEN CODE ---\n"
            f"{broken_code}\n\n"
        )
        if testbench_code:
            prompt += (
                "--- TESTBENCH (DO NOT MODIFY — your code must conform to this) ---\n"
                f"{testbench_code}\n\n"
            )
        prompt += (
            "--- SIMULATOR ERROR LOG ---\n"
            f"{error_log}\n\n"
            "Analyze the errors and output ONLY the fully corrected SystemVerilog code. "
            "The module name, port names, and port widths MUST match what the testbench expects."
        )

        try:
            raw_text = self.moe.route_task(
                prompt=prompt,
                tier=tier,
                system_prompt=fix_system_prompt,
                max_tokens=2048,
                temperature=0.2,
            )
            match = re.search(
                r"```(?:verilog|systemverilog)?(.*?)```",
                raw_text,
                re.DOTALL | re.IGNORECASE,
            )
            fixed_code = match.group(1).strip() if match else raw_text.strip()
            # SAFETY SCRUBBER: Remove hallucinated backtick macros
            fixed_code = fixed_code.replace("`systemverilog\n", "")
            fixed_code = fixed_code.replace("`verilog\n", "")
            
            print("✅ SUCCESS: Corrected code generated.")
            return fixed_code
        except Exception as e:
            print(f"❌ ERROR: Auto-fix failed: {e}")
            return broken_code
# =========================================================================
# Workspace scaffolding (unchanged)
# =========================================================================
def setup_workspaces(variations: list, base_dir: str = "workspace"):
    """Creates isolated sandbox directories and saves each variation as
    ``design.sv`` in its respective folder.
    """
    print(f"\n[SYSTEM] Setting up isolated EDA workspaces in './{base_dir}'...")
    base_path = Path(base_dir)
    if base_path.exists():
        shutil.rmtree(base_path)
    base_path.mkdir(parents=True)
    saved_paths = []
    for idx, rtl_code in enumerate(variations):
        run_folder = base_path / f"run_{idx}"
        run_folder.mkdir()
        file_path = run_folder / "design.sv"
        file_path.write_text(rtl_code, encoding="utf-8")
        saved_paths.append(str(run_folder))
        print(f"  -> Saved Variation {idx + 1} to {file_path}")
    return saved_paths
# =========================================================================
# CLI smoke-test
# =========================================================================
if __name__ == "__main__":
    ai_client = EDA_LLM_Client()
    # 1. Ask for a 4-bit ALU
    test_request = (
        "Design a 4-bit ALU that can do addition, subtraction, AND, and OR "
        "operations. It needs a 2-bit opcode selector."
    )
    # 2. Get the validated HardwareSpec
    spec = ai_client.generate_spec(test_request)
    # 3. Generate hardware variations
    if isinstance(spec, HardwareSpec):
        print(f"\n📋 Validated spec: {spec.model_dump_json(indent=2)}")
        rtl_variations = ai_client.generate_variations(spec, num_variations=3)
        # 4. Save them to isolated folders
        if rtl_variations:
            sandbox_dirs = setup_workspaces(rtl_variations)
            print("\n✅ SUCCESS: Pipeline Complete. Variations are isolated and ready for Ray.")
        else:
            print("❌ ERROR: Variations list is empty.")
    else:
        print(f"\nAborting hardware generation due to spec failure:\n{spec}")
