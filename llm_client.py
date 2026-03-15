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
from models import ArchitecturePlan, HardwareSpec
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
    TIER_GRUNT     = ("gemini/gemini-3.1-pro-preview",    "claude-haiku-4-5-20251001")
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
        self.spec_model = ExpertTier.TIER_GRUNT.primary

        # Optional RAG agent — set to None to disable context retrieval
        self.rag: HardwareRAG | None = rag

    @staticmethod
    # ------------------------------------------------------------------
    # Structured spec generation (now powered by Pydantic + Instructor)
    # ------------------------------------------------------------------
    @staticmethod
    def extract_python_code(raw_text: str) -> str:
        """Extract Python from markdown/code fences and strip framing keywords."""
        text = raw_text.strip()
        match = re.search(r"```(?:python)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
        if match:
            text = match.group(1)
        else:
            text = text.replace("```python", "").replace("```", "")
        text = text.strip()
        text = re.sub(r"^python\\b", "", text, flags=re.IGNORECASE).strip()
        return text

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
            "into a strict hardware architecture specification that matches the "
            "HardwareSpec schema.\n\n"
            f'User Request: "{user_request}"\n\n'
            "Return ONLY a JSON object. Do not wrap it in markdown, prose, or code fences.\n"
            "CRITICAL: Do NOT produce any Python golden model or test vector code. "
            "This phase only defines the RTL skeleton.\n"
            "The JSON must include the following fields:\n"
            "  1. module_name (lowercase letters, numbers, underscores).\n"
            "  2. description (a concise behavioral summary).\n"
            "  3. is_sequential (true if clk/rst are required, false otherwise).\n"
            "  4. parameters (list of {name, default_value}; use [] when no tunables exist).\n"
            "  5. inputs and outputs (each list item must include 'name' and 'width').\n"
            "  6. dse_strategies (EXACTLY three distinct strategy strings describing different design trade-offs).\n"
        )
        try:
            spec: HardwareSpec = self.instructor_client.chat.completions.create(
            model=ExpertTier.TIER_GRUNT.primary,
            max_tokens=8192,
            max_retries=2,
            temperature=0.1,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user",   "content": prompt},
            ],
            response_model=HardwareSpec,
        )

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

    def decompose_architecture(self, user_request: str) -> ArchitecturePlan | str:
        """Break complex CPU requests into a bottom-up task list."""
        print(f"[SYSTEM] Decomposing architecture for request: {user_request[:80]}...")
        ip_library_dir = "ip_library"
        if os.path.isdir(ip_library_dir):
            available_ips = [
                os.path.splitext(filename)[0]
                for filename in os.listdir(ip_library_dir)
                if filename.endswith(".sv")
            ]
            catalog_entries = []
            for json_path in os.listdir(ip_library_dir):
                if not json_path.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(ip_library_dir, json_path), "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                except Exception:
                    continue
                module_name = data.get("module_name")
                description = data.get("description")
                if module_name and description:
                    catalog_entries.append(f"- {module_name}: {description}")
            ip_catalog_text = "\n".join(catalog_entries)
        else:
            available_ips = []
            ip_catalog_text = ""
        prompt = (
            "You are a Lead CPU Architect mapping user needs to a modular implementation plan.\n"
            f"User Request: \"{user_request}\"\n"
            f"AVAILABLE IP INVENTORY: {available_ips}.\n"
            "AVAILABLE SEMANTIC IP CATALOG:\n"
            f"{ip_catalog_text}\n"
            "Return a JSON object conforming EXACTLY to the ArchitecturePlan schema.\n"
            "Rules:\n"
            "1. is_complex must be true when multiple modules are required (e.g., full CPU). "
            "If the request is a single leaf like an ALU or oscillator, set is_complex to false and emit one task.\n"
            "2. tasks must be ordered from bottom-level primitives up to the top-level integration.\n"
            "3. Each task must include module_name, a highly specific prompt, and a boolean requires_dummy_oracle.\n"
            "4. For any task that represents a top-level integration (e.g., the overall CPU), set requires_dummy_oracle to true so the verification oracle falls back to a pass-through model.\n"
            "5. Keep prompts detailed enough for a HardwareSpec generator to implement the requested block.\n"
            "6. INTELLIGENT REUSE: Compare your required sub-modules against the AVAILABLE IP INVENTORY. "
            "Read the descriptions in the AVAILABLE SEMANTIC IP CATALOG. If an existing IP's description semantically fulfills a sub-module you need, you MUST reuse its exact module_name instead of inventing a new task. Do not duplicate existing functionality.\n"
            "CRITICAL ARCHITECTURE RULES:\n"
            " - DO NOT create tasks to generate RAM, ROM, Instruction Memory, Data Memory, or Caches. The top-level CPU core must instead expose standard memory interface ports (imem_addr, imem_rdata, dmem_addr, dmem_wdata, dmem_we) to communicate with external memory.\n"
            " - Limit your decomposition strictly to the core processing elements (ProgramCounter, ALU, RegisterFile, ImmGen, ControlUnit, and the top-level integration).\n"
        )
        try:
            plan: ArchitecturePlan = self.instructor_client.chat.completions.create(
                model=ExpertTier.TIER_GRUNT.primary,
                max_tokens=2048,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": "You are a Lead CPU Architect and decomposition expert."},
                    {"role": "user", "content": prompt},
                ],
                response_model=ArchitecturePlan,
            )

            print("✅ Decomposition plan generated.")
            return plan
        except ValidationError as e:
            error_msg = f"❌ VALIDATION ERROR: ArchitecturePlan schema mismatch.\n{e}"
            print(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ ERROR: Failed to decompose architecture: {e}"
            print(error_msg)
            return error_msg
    
    def review_and_fix_spec(self, spec: HardwareSpec) -> HardwareSpec:
        """Placeholder reviewer for skeleton-first specs (no golden model included)."""
        print("[SYSTEM] Reviewer Agent skipped (python golden model handled separately).")
        return spec

    def generate_verification_oracle(self, spec_dict: dict, user_request: str) -> dict:
        """Generate the Python golden model/test vector pair in a second pass."""
        print("[SYSTEM] Generating verification oracle (golden model + test vectors)...")
        base_prompt = (
            "You are a Senior Python QA Engineer. You have previously defined the RTL "
            "skeleton described below. Using that skeleton plus the original user "
            f"request: \"{user_request}\", write TWO extremely concise Python functions: "
            "`def golden_model(state, inputs)` and `def generate_test_vectors()`.\n"
            "Ensure:\n"
            "1. CHAIN OF THOUGHT: Use standard # comments for your truth table to prevent AST parsing errors with string literals.\n"
            "2. All undefined opcodes produce outputs with every field set to 0.\n"
            "3. `generate_test_vectors()` returns a list of dictionaries describing sequential cycles when `is_sequential` is true or combinational inputs otherwise.\n"
            "4. The `golden_model(state, inputs)` MUST return exactly a tuple of TWO dictionaries: (updated_state, expected_outputs_dict).\n"
            "5. SAFE FALLBACKS: The golden_model MUST end with `return model_state, expected_output` covering any undefined inputs, and `generate_test_vectors()` MUST end with `return test_vectors` so a list is always returned even if your logic hits an unknown path.\n"
            "6. TOKEN LIMIT AVOIDANCE: When writing `generate_test_vectors()`, DO NOT hardcode a massive list of 100 dictionaries. Hardcode 10 to 15 core edge-cases (e.g., valid RISC-V opcodes), and then use a Python for loop with the `random` module to append the remaining vectors. This prevents massive string truncation and bracket errors.\n"
            "7. Keep the code terse, avoid extra comments beyond the required roadmap, and focus on bitwise/lookup logic.\n"
            "8. CRITICAL STRUCTURE: You must use the exact skeleton below and return the required values. Do not wrap the functions in a class.\n"
            "```python\n"
            "def generate_test_vectors():\n"
            "    test_vectors = []\n"
            "    # Hardcode 10-15 edge cases here\n"
            "    # Use a for loop to append random combinations up to 100\n"
            "    return test_vectors\n\n"
            "def golden_model(model_state, inputs):\n"
            "    expected_output = {}\n"
            "    # Your logic here. Default all outputs to 0 if the opcode is unknown!\n"
            "    return model_state, expected_output\n"
            "```\n"
            "You MUST use exactly those function names, and you MUST return `test_vectors` and `model_state, expected_output`.\n"
            "9. CRITICAL RULE: The `generate_test_vectors()` function MUST return a valid Python list of dictionaries. It absolutely CANNOT return None.\n"
            "10. Include a fallback `return []` at the end so a list is always produced even if your logic fails.\n"
            "Hardware Skeleton (JSON):\n"
            f"{json.dumps(spec_dict, indent=2)}\n"
        )

        prompt_suffix = ""
        for attempt in range(3):
            final_prompt = base_prompt + prompt_suffix
            raw_text = self.moe.route_task(
                prompt=final_prompt,
                tier=ExpertTier.TIER_CODER,
                max_tokens=4096,
                temperature=0.1,
            )
            clean_python = self.extract_python_code(raw_text)
            try:
                ast.parse(clean_python)
                local_scope = {}
                exec(clean_python, globals(), local_scope)
                if "generate_test_vectors" not in local_scope or "golden_model" not in local_scope:
                    raise ValueError("Missing required functions 'generate_test_vectors' or 'golden_model'.")
                test_vecs = local_scope["generate_test_vectors"]()
                if not isinstance(test_vecs, list) or len(test_vecs) < 5:
                    raise ValueError(f"generate_test_vectors must return a list of at least 5 dictionaries. Got: {test_vecs}")
                local_scope["golden_model"]({}, test_vecs[0])
                return {"golden_model_and_test_generator": clean_python}
            except SyntaxError as exc:
                print(f"[SYSTEM] Oracle Python syntax error: {exc}. Retrying...")
                prompt_suffix = (
                    f"\nCRITICAL: Your Python code failed ast.parse() with SyntaxError: {exc}. "
                    "Fix your commas, brackets, and indentation.\n"
                )
            except Exception as exc:
                print(f"[SYSTEM] Oracle Python execution error: {exc}. Retrying...")
                prompt_suffix = (
                    f"\nCRITICAL: Your Python code passed syntax checks, but crashed during sandbox execution with: "
                    f"{type(exc).__name__}: {exc}. Ensure you import any required libraries (like random or math) inside your functions, "
                    "and verify your variable logic.\n"
                )
        raise ValueError("Unable to generate a syntax-valid Python oracle after 3 attempts.")

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
        available_interfaces = ""
        ip_dir = Path("ip_library")
        if ip_dir.exists():
            interface_lines = []
            for json_path in sorted(ip_dir.glob("*.json")):
                try:
                    with open(json_path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                except Exception:
                    continue
                module_name = data.get("module_name")
                inputs = data.get("inputs")
                outputs = data.get("outputs")
                parameters = data.get("parameters")
                if not module_name:
                    continue
                interface_lines.append(
                    f"{module_name}: inputs={inputs}, outputs={outputs}, parameters={parameters}"
                )
            if interface_lines:
                available_interfaces = "\n".join(interface_lines)

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

        golden_model_code = spec_dict.get("golden_model_python")
        if golden_model_code:
            golden_alignment_block = (
                "\n\nCRITICAL ALIGNMENT: Here is the Python Golden Model used for verification. "
                "You MUST ensure your SystemVerilog internal signal encodings (like alu_control states) "
                "perfectly match the integer values defined in this Python code!\n\n"
                "```python\n"
                f"{golden_model_code}\n"
                "```\n"
            )
        else:
            golden_alignment_block = ""

        for i in range(num_variations):
            seed = strategies[i] if i < len(strategies) else strategies[0]
            print(f"  -> Generating Variation {i + 1} (Strategy: {seed[:40]}...)")

            wiring_context_block = ""
            if available_interfaces:
                wiring_context_block = (
                    "\n\nCRITICAL WIRING CONTEXT: Here are the exact port interfaces for "
                    "the sub-modules available in your IP library. If you instantiate any "
                    "of these modules, you MUST wire them using EXACTLY these port names:\n"
                    f"{available_interfaces}\n"
                )

            prompt = f"""
            You are a master ASIC RTL designer. Implement the following module based STRICTLY on this JSON specification:
            {json.dumps(spec_dict, indent=2)}

            {golden_alignment_block}
            {wiring_context_block}

            STRATEGY FOR THIS VARIATION:
            {seed}

            CRITICAL RULES:
            {timing_rules}
            4. The module must have ONLY the exact ports listed in the JSON. No extra ports.
            5. Output ONLY the raw SystemVerilog code. Do not explain anything.
            
            CRITICAL CODING STANDARDS:
            - DO NOT use massive concatenated binary literals (e.g., 13'b100...). Assign signals individually, or use cleanly formatted localparam definitions for states and opcodes to prevent bit-counting errors.
            - CHAIN OF THOUGHT: For complex logic like decoders or control units, you MUST write a brief Truth Table or Logic Map in Verilog comments (//) immediately before the always_comb block to plan your routing.
            - Always include a default: case in case statements that safely sets all outputs to 0.
            """
            try:
                raw_text = self.moe.route_task(
                    prompt=prompt,
                    tier=ExpertTier.TIER_CODER,
                    max_tokens=8192,
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
            "You must output ONLY the fully corrected raw SystemVerilog code.\n"
            "CRITICAL: You may provide a brief explanation before the code block, but "
            "the corrected code MUST be wrapped inside a ```systemverilog ... ``` block.\n"
            "CRITICAL CONSTRAINTS:\n"
            f"{timing_rules}\n"
            "4. The module must have ONLY the ports the testbench uses. Do NOT add extra ports.\n"
            "5. Fix any MULTIDRIVEN, LATCH, or syntax errors reported by Verilator.\n"
            "6. ORACLE OBEDIENCE: If the simulator error log shows a mismatch between your Hardware Output and the Golden Model Expected output, you MUST modify your SystemVerilog to perfectly match the Golden Model's expected integers, even if you believe the Golden Model is architecturally incorrect. You MUST output the modified code wrapped in a systemverilog block.\n"
            "7. CRITICAL SYNTHESIS RULE: You MUST wrap any timing constructs (like #1) in an ifndef block so synthesis tools ignore them. Like this:\n"
            "   `ifndef SYNTHESIS\n"
            "   initial begin #1; end\n"
            "   `endif\n"
            "8. You MUST wrap the corrected RTL in a ```systemverilog ... ``` block (explanations may precede it)."
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
            if not match:
                print("    [CRITIC] Warning: no Verilog code block detected; returning broken code.")
                return broken_code
            fixed_code = match.group(1).strip()
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
