import os
import json
import re
import shutil
from pathlib import Path
import anthropic
import instructor
from dotenv import load_dotenv
from pydantic import ValidationError
from models import HardwareSpec
# Load local .env file if it exists
load_dotenv()
class EDA_LLM_Client:
    def __init__(self):
        """
        Initializes the Anthropic client securely using the injected environment variable.
        """
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("CRITICAL: ANTHROPIC_API_KEY environment variable is not set.")
        # Raw Anthropic client for free-form generation (variations, fixes)
        self._raw_client = anthropic.Anthropic(api_key=self.api_key)
        # Instructor-patched client for structured Pydantic extraction
        self.client = instructor.from_anthropic(self._raw_client)
        self.model_name = "claude-haiku-4-5-20251001"
        self.system_prompt = (
            "You are an expert ASIC and FPGA Digital Design Engineer. "
            "Your job is to generate highly optimized, synthesizable SystemVerilog code. "
            "CRITICAL RULES:\n"
            "1. You must output ONLY the requested code or JSON. \n"
            "2. DO NOT include markdown formatting (like ```verilog or ```json) unless explicitly requested. \n"
            "3. DO NOT include conversational filler, greetings, or explanations. \n"
            "4. Ensure all modules have explicit input/output port width declarations."
        )
    # ------------------------------------------------------------------
    # Connection smoke-test
    # ------------------------------------------------------------------
    def test_connection(self):
        print(f"[SYSTEM] Sending test prompt to {self.model_name}...")
        try:
            response = self._raw_client.messages.create(
                model=self.model_name,
                max_tokens=256,
                temperature=0.1,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": "Write a tiny 1-bit Verilog half-adder module. "
                                   "Output nothing but the raw Verilog code.",
                    }
                ],
            )
            return response.content[0].text
        except Exception as e:
            return f"❌ ERROR: An unexpected error occurred: {e}"
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
        print(f"[SYSTEM] Translating request to HardwareSpec using {self.model_name}...")
        prompt = (
            "You are a systems architect. Convert the following user request "
            "into a strict hardware architecture specification.\n\n"
            f'User Request: "{user_request}"\n\n'
            "Return the specification as valid JSON conforming to the schema. "
            "CRITICAL: For the 'golden_model_python' field, output PURE Python code. "
            "DO NOT wrap it in ```python markdown blocks. Do not use markdown at all. "
            "The function MUST be named 'golden_model(inputs)' where 'inputs' is a dictionary containing the input port names. "
            "Example for an ALU: 'def golden_model(inputs):\n    return (inputs[\"a\"] + inputs[\"b\"]) & 0xF'"
        )
        try:
            spec: HardwareSpec = self.client.messages.create(
                model=self.model_name,
                max_tokens=512,
                max_retries=2,                     # instructor auto-retries on validation failure
                temperature=0.1,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}],
                response_model=HardwareSpec,       # ← Pydantic extraction
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
    # ------------------------------------------------------------------
    # RTL variation generation (unchanged — free-form text output)
    # ------------------------------------------------------------------
    def generate_variations(self, spec: HardwareSpec | dict, num_variations: int = 3):
        spec_dict = spec.model_dump() if isinstance(spec, HardwareSpec) else spec
        print(f"\n[SYSTEM] Generating {num_variations} RTL variations using {self.model_name}...")
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
                response = self._raw_client.messages.create(
                    model=self.model_name,
                    max_tokens=1024,
                    temperature=0.8,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw_text = response.content[0].text
                match = re.search(r"```(?:verilog|systemverilog)?(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
                clean_verilog = match.group(1).strip() if match else raw_text.strip()
                variations.append(clean_verilog)
            except Exception as e:
                print(f"❌ ERROR on variation {i}: {e}")
                variations.append(f"// Generation Failed: {e}")
        return variations
    # ------------------------------------------------------------------
    # Self-healing fix (unchanged — free-form text output)
    # ------------------------------------------------------------------
    def fix_design(self, broken_code: str, error_log: str, testbench_code: str = "", is_sequential: bool = False) -> str:
        """Takes broken SystemVerilog code, its simulator error log, and
        optionally the testbench, then returns a corrected version.
        """
        print(f"[SYSTEM] Attempting auto-fix using {self.model_name}...")
        
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
            "5. Fix any MULTIDRIVEN, LATCH, or syntax errors reported by Verilator."
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
            response = self._raw_client.messages.create(
                model=self.model_name,
                max_tokens=2048,
                temperature=0.2,
                system=fix_system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.content[0].text
            match = re.search(
                r"```(?:verilog|systemverilog)?(.*?)```",
                raw_text,
                re.DOTALL | re.IGNORECASE,
            )
            fixed_code = match.group(1).strip() if match else raw_text.strip()
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
# import os
# import json
# import re
# import shutil
# from pathlib import Path 
# import anthropic
# from dotenv import load_dotenv

# # Load local .env file if it exists
# load_dotenv()

# class EDA_LLM_Client:
#     def __init__(self):
#         """
#         Initializes the Anthropic client securely using the injected environment variable.
#         """
#         self.api_key = os.getenv("ANTHROPIC_API_KEY")
#         if not self.api_key:
#             raise ValueError("CRITICAL: ANTHROPIC_API_KEY environment variable is not set.")
        
#         self.client = anthropic.Anthropic(api_key=self.api_key)
#         self.model_name = "claude-haiku-4-5-20251001" 

#         self.system_prompt = (
#             "You are an expert ASIC and FPGA Digital Design Engineer. "
#             "Your job is to generate highly optimized, synthesizable SystemVerilog code. "
#             "CRITICAL RULES:\n"
#             "1. You must output ONLY the requested code or JSON. \n"
#             "2. DO NOT include markdown formatting (like ```verilog or ```json) unless explicitly requested. \n"
#             "3. DO NOT include conversational filler, greetings, or explanations. \n"
#             "4. Ensure all modules have explicit input/output port width declarations."
#         )

#     def test_connection(self):
#         print(f"[SYSTEM] Sending test prompt to {self.model_name}...")
#         try:
#             response = self.client.messages.create(
#                 model=self.model_name,
#                 max_tokens=256,
#                 temperature=0.1, 
#                 system=self.system_prompt,
#                 messages=[
#                     {"role": "user", "content": "Write a tiny 1-bit Verilog half-adder module. Output nothing but the raw Verilog code."}
#                 ]
#             )
#             return response.content[0].text
#         except Exception as e:
#             return f"❌ ERROR: An unexpected error occurred: {e}"

#     def generate_spec(self, user_request: str):
#         """
#         Translates a natural language hardware request into a strict JSON architecture specification.
#         """
#         print(f"[SYSTEM] Translating request to JSON Spec using {self.model_name}...")
        
#         json_schema = """
#         {
#             "module_name": "string (lowercase_with_underscores)",
#             "description": "string (brief behavioral description)",
#             "parameters": [
#                 {"name": "string", "default_value": "integer/string"}
#             ],
#             "inputs": [
#                 {"name": "string", "width": "integer (e.g., 1, 8, 32)"}
#             ],
#             "outputs": [
#                 {"name": "string", "width": "integer"}
#             ]
#         }
#         """
        
#         prompt = f"""
#         You are a systems architect. Convert the following user request into a strict JSON architecture specification.
#         You must match this exact schema:
#         {json_schema}
        
#         User Request: "{user_request}"
        
#         CRITICAL: Output ONLY valid JSON. Do not wrap it in ```json blocks. Do not explain your thought process.
#         """
        
#         try:
#             response = self.client.messages.create(
#                 model=self.model_name,
#                 max_tokens=512,
#                 temperature=0.1, 
#                 system=self.system_prompt,
#                 messages=[{"role": "user", "content": prompt}]
#             )
            
#             raw_output = response.content[0].text.strip()
            
#             spec_dict = json.loads(raw_output)
#             print("✅ SUCCESS: Valid JSON specification generated.")
#             return spec_dict
            
#         except json.JSONDecodeError as e:
#             return f"❌ ERROR: LLM failed to output valid JSON. Raw output was:\n{raw_output}\nError details: {e}"
#         except Exception as e:
#             return f"❌ ERROR: An unexpected error occurred: {e}"

#     def generate_variations(self, spec_dict: dict, num_variations: int = 3):
#         """
#         Takes a strict JSON spec and generates N distinct SystemVerilog architectural variations.
#         """
#         print(f"\n[SYSTEM] Generating {num_variations} RTL variations using {self.model_name}...")
#         variations = []
        
#         # Variation seeds to force architectural diversity
#         variation_seeds = [
#             "Implementation Strategy: Write standard, highly readable behavioral RTL using always_comb and case statements.",
#             "Implementation Strategy: Focus on lowest possible gate count and area utilization. Share logic where possible.",
#             "Implementation Strategy: Focus on maximum performance and minimum gate-delay latency, even if it costs more area."
#         ]
        
#         for i in range(num_variations):
#             seed = variation_seeds[i] if i < len(variation_seeds) else "Implementation Strategy: Generate a unique structural variation."
#             print(f"  -> Generating Variation {i+1}...")
            
#             prompt = f"""
#             You are a master ASIC RTL designer. Implement the following module based STRICTLY on this JSON specification:
#             {json.dumps(spec_dict, indent=2)}

#             {seed}

#             CRITICAL RULES:
#             1. This design must be PURELY COMBINATIONAL. Do NOT use clk, rst, or any sequential logic.
#             2. Use always_comb with logic type variables, or pure assign statements. Never use always @(posedge clk).
#             3. For Verilator compatibility: variables assigned inside always_comb MUST be declared as 'logic', NOT 'wire'.
#             4. The module must have ONLY these ports: a, b, opcode, result. No extra ports (no carry_out, no zero_flag, no clk, no rst_n).
#             5. Output ONLY the raw code. Do not explain anything.
#             """
            
#             try:
#                 response = self.client.messages.create(
#                     model=self.model_name,
#                     max_tokens=1024,
#                     temperature=0.8, # High temperature forces creativity
#                     system=self.system_prompt,
#                     messages=[{"role": "user", "content": prompt}]
#                 )
                
#                 raw_text = response.content[0].text
                
#                 # Regex Extraction to strip away accidental markdown tags
#                 match = re.search(r"```(?:verilog|systemverilog)?(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
#                 if match:
#                     clean_verilog = match.group(1).strip()
#                 else:
#                     clean_verilog = raw_text.strip()
                
#                 variations.append(clean_verilog)
                
#             except Exception as e:
#                 print(f"❌ ERROR on variation {i}: {e}")
#                 variations.append(f"// Generation Failed: {e}")
                
#         return variations

#     def fix_design(self, broken_code: str, error_log: str, testbench_code: str = "") -> str:
#         """
#         Takes broken SystemVerilog code, its simulator error log, and optionally
#         the testbench, then returns a corrected version of the code.
#         """
#         print(f"[SYSTEM] Attempting auto-fix using {self.model_name}...")

#         fix_system_prompt = (
#             "You are a Senior Design Verification Engineer. "
#             "Your job is to analyze failed SystemVerilog code and the corresponding EDA simulator error log. "
#             "You must output ONLY the fully corrected raw SystemVerilog code. "
#             "Do not include markdown formatting, explanations, or conversational text.\n"
#             "CRITICAL CONSTRAINTS:\n"
#             "1. The design must be PURELY COMBINATIONAL. No clk, rst_n, or sequential logic.\n"
#             "2. Use always_comb or assign statements ONLY.\n"
#             "3. VERILATOR RULE: Any variable assigned inside always_comb MUST be declared as 'logic', NOT 'wire'. "
#             "Verilator will reject procedural assignments to wire (PROCASSWIRE error).\n"
#             "4. The module must have ONLY the ports the testbench uses. Do NOT add extra ports like carry_out or zero_flag "
#             "unless the testbench explicitly references them.\n"
#             "5. Do NOT use parameters unless the testbench uses them."
#         )

#         prompt = (
#             "The following SystemVerilog code has failed EDA verification.\n\n"
#             "--- BROKEN CODE ---\n"
#             f"{broken_code}\n\n"
#         )

#         if testbench_code:
#             prompt += (
#                 "--- TESTBENCH (DO NOT MODIFY — your code must conform to this) ---\n"
#                 f"{testbench_code}\n\n"
#             )

#         prompt += (
#             "--- SIMULATOR ERROR LOG ---\n"
#             f"{error_log}\n\n"
#             "Analyze the errors and output ONLY the fully corrected SystemVerilog code. "
#             "The module name, port names, and port widths MUST match what the testbench expects."
#         )

#         try:
#             response = self.client.messages.create(
#                 model=self.model_name,
#                 max_tokens=2048,
#                 temperature=0.2,
#                 system=fix_system_prompt,
#                 messages=[{"role": "user", "content": prompt}]
#             )

#             raw_text = response.content[0].text

#             match = re.search(r"```(?:verilog|systemverilog)?(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
#             if match:
#                 fixed_code = match.group(1).strip()
#             else:
#                 fixed_code = raw_text.strip()

#             print("✅ SUCCESS: Corrected code generated.")
#             return fixed_code

#         except Exception as e:
#             print(f"❌ ERROR: Auto-fix failed: {e}")
#             return broken_code

# def setup_workspaces(variations: list, base_dir: str = "workspace"):
#     """
#     Takes a list of Verilog code strings, creates isolated sandbox directories,
#     and saves each string as `design.sv` in its respective folder.
#     """
#     print(f"\n[SYSTEM] Setting up isolated EDA workspaces in './{base_dir}'...")
    
#     base_path = Path(base_dir)
    
#     # Clean up old runs so we don't clutter the Codespace
#     if base_path.exists():
#         shutil.rmtree(base_path)
#     base_path.mkdir(parents=True)
    
#     # Loop through the variations and save them
#     saved_paths = []
#     for idx, rtl_code in enumerate(variations):
#         # Create a folder like: workspace/run_0
#         run_folder = base_path / f"run_{idx}"
#         run_folder.mkdir()
        
#         # Save the Verilog file
#         file_path = run_folder / "design.sv"
#         with open(file_path, "w") as f:
#             f.write(rtl_code)
            
#         saved_paths.append(str(run_folder))
#         print(f"  -> Saved Variation {idx+1} to {file_path}")
        
#     return saved_paths

# # =============================================================================
# # Execution block for testing
# # =============================================================================
# if __name__ == "__main__":
#     ai_client = EDA_LLM_Client()
    
#     # 1. Ask for a 4-bit ALU
#     test_request = "Design a 4-bit ALU that can do addition, subtraction, AND, and OR operations. It needs a 2-bit opcode selector."
    
#     # 2. Get the JSON Spec
#     spec = ai_client.generate_spec(test_request)
    
#     # 3. Generate hardware variations
#     if isinstance(spec, dict):
#         rtl_variations = ai_client.generate_variations(spec, num_variations=3)
        
#         # 4. Save them to isolated folders
#         if rtl_variations:
#             sandbox_dirs = setup_workspaces(rtl_variations)
#             print("\n✅ SUCCESS: Week 2 Pipeline Complete. Variations are isolated and ready for Ray.")
#         else:
#             print("❌ ERROR: Variations list is empty.")
#     else:
#         print("\nAborting hardware generation due to JSON failure.")
        