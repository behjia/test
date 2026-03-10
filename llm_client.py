import os
import json
import re
import shutil
from pathlib import Path 
import anthropic
from dotenv import load_dotenv

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
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
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

    def test_connection(self):
        print(f"[SYSTEM] Sending test prompt to {self.model_name}...")
        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=256,
                temperature=0.1, 
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": "Write a tiny 1-bit Verilog half-adder module. Output nothing but the raw Verilog code."}
                ]
            )
            return response.content[0].text
        except Exception as e:
            return f"❌ ERROR: An unexpected error occurred: {e}"

    def generate_spec(self, user_request: str):
        """
        Translates a natural language hardware request into a strict JSON architecture specification.
        """
        print(f"[SYSTEM] Translating request to JSON Spec using {self.model_name}...")
        
        json_schema = """
        {
            "module_name": "string (lowercase_with_underscores)",
            "description": "string (brief behavioral description)",
            "parameters": [
                {"name": "string", "default_value": "integer/string"}
            ],
            "inputs": [
                {"name": "string", "width": "integer (e.g., 1, 8, 32)"}
            ],
            "outputs": [
                {"name": "string", "width": "integer"}
            ]
        }
        """
        
        prompt = f"""
        You are a systems architect. Convert the following user request into a strict JSON architecture specification.
        You must match this exact schema:
        {json_schema}
        
        User Request: "{user_request}"
        
        CRITICAL: Output ONLY valid JSON. Do not wrap it in ```json blocks. Do not explain your thought process.
        """
        
        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=512,
                temperature=0.1, 
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_output = response.content[0].text.strip()
            
            spec_dict = json.loads(raw_output)
            print("✅ SUCCESS: Valid JSON specification generated.")
            return spec_dict
            
        except json.JSONDecodeError as e:
            return f"❌ ERROR: LLM failed to output valid JSON. Raw output was:\n{raw_output}\nError details: {e}"
        except Exception as e:
            return f"❌ ERROR: An unexpected error occurred: {e}"

    def generate_variations(self, spec_dict: dict, num_variations: int = 3):
        """
        Takes a strict JSON spec and generates N distinct SystemVerilog architectural variations.
        """
        print(f"\n[SYSTEM] Generating {num_variations} RTL variations using {self.model_name}...")
        variations = []
        
        # Variation seeds to force architectural diversity
        variation_seeds = [
            "Implementation Strategy: Write standard, highly readable behavioral RTL using always_comb and case statements.",
            "Implementation Strategy: Focus on lowest possible gate count and area utilization. Share logic where possible.",
            "Implementation Strategy: Focus on maximum performance and minimum gate-delay latency, even if it costs more area."
        ]
        
        for i in range(num_variations):
            seed = variation_seeds[i] if i < len(variation_seeds) else "Implementation Strategy: Generate a unique structural variation."
            print(f"  -> Generating Variation {i+1}...")
            
            prompt = f"""
            You are a master ASIC RTL designer. Implement the following module based STRICTLY on this JSON specification:
            {json.dumps(spec_dict, indent=2)}

            {seed}

            CRITICAL RULES:
            1. This design must be PURELY COMBINATIONAL. Do NOT use clk, rst, or any sequential logic.
            2. Use always_comb with logic type variables, or pure assign statements. Never use always @(posedge clk).
            3. For Verilator compatibility: variables assigned inside always_comb MUST be declared as 'logic', NOT 'wire'.
            4. The module must have ONLY these ports: a, b, opcode, result. No extra ports (no carry_out, no zero_flag, no clk, no rst_n).
            5. Output ONLY the raw code. Do not explain anything.
            """
            
            try:
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=1024,
                    temperature=0.8, # High temperature forces creativity
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                raw_text = response.content[0].text
                
                # Regex Extraction to strip away accidental markdown tags
                match = re.search(r"```(?:verilog|systemverilog)?(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
                if match:
                    clean_verilog = match.group(1).strip()
                else:
                    clean_verilog = raw_text.strip()
                
                variations.append(clean_verilog)
                
            except Exception as e:
                print(f"❌ ERROR on variation {i}: {e}")
                variations.append(f"// Generation Failed: {e}")
                
        return variations

    def fix_design(self, broken_code: str, error_log: str, testbench_code: str = "") -> str:
        """
        Takes broken SystemVerilog code, its simulator error log, and optionally
        the testbench, then returns a corrected version of the code.
        """
        print(f"[SYSTEM] Attempting auto-fix using {self.model_name}...")

        fix_system_prompt = (
            "You are a Senior Design Verification Engineer. "
            "Your job is to analyze failed SystemVerilog code and the corresponding EDA simulator error log. "
            "You must output ONLY the fully corrected raw SystemVerilog code. "
            "Do not include markdown formatting, explanations, or conversational text.\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. The design must be PURELY COMBINATIONAL. No clk, rst_n, or sequential logic.\n"
            "2. Use always_comb or assign statements ONLY.\n"
            "3. VERILATOR RULE: Any variable assigned inside always_comb MUST be declared as 'logic', NOT 'wire'. "
            "Verilator will reject procedural assignments to wire (PROCASSWIRE error).\n"
            "4. The module must have ONLY the ports the testbench uses. Do NOT add extra ports like carry_out or zero_flag "
            "unless the testbench explicitly references them.\n"
            "5. Do NOT use parameters unless the testbench uses them."
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
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=2048,
                temperature=0.2,
                system=fix_system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )

            raw_text = response.content[0].text

            match = re.search(r"```(?:verilog|systemverilog)?(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
            if match:
                fixed_code = match.group(1).strip()
            else:
                fixed_code = raw_text.strip()

            print("✅ SUCCESS: Corrected code generated.")
            return fixed_code

        except Exception as e:
            print(f"❌ ERROR: Auto-fix failed: {e}")
            return broken_code

def setup_workspaces(variations: list, base_dir: str = "workspace"):
    """
    Takes a list of Verilog code strings, creates isolated sandbox directories,
    and saves each string as `design.sv` in its respective folder.
    """
    print(f"\n[SYSTEM] Setting up isolated EDA workspaces in './{base_dir}'...")
    
    base_path = Path(base_dir)
    
    # Clean up old runs so we don't clutter the Codespace
    if base_path.exists():
        shutil.rmtree(base_path)
    base_path.mkdir(parents=True)
    
    # Loop through the variations and save them
    saved_paths = []
    for idx, rtl_code in enumerate(variations):
        # Create a folder like: workspace/run_0
        run_folder = base_path / f"run_{idx}"
        run_folder.mkdir()
        
        # Save the Verilog file
        file_path = run_folder / "design.sv"
        with open(file_path, "w") as f:
            f.write(rtl_code)
            
        saved_paths.append(str(run_folder))
        print(f"  -> Saved Variation {idx+1} to {file_path}")
        
    return saved_paths

# =============================================================================
# Execution block for testing
# =============================================================================
if __name__ == "__main__":
    ai_client = EDA_LLM_Client()
    
    # 1. Ask for a 4-bit ALU
    test_request = "Design a 4-bit ALU that can do addition, subtraction, AND, and OR operations. It needs a 2-bit opcode selector."
    
    # 2. Get the JSON Spec
    spec = ai_client.generate_spec(test_request)
    
    # 3. Generate hardware variations
    if isinstance(spec, dict):
        rtl_variations = ai_client.generate_variations(spec, num_variations=3)
        
        # 4. Save them to isolated folders
        if rtl_variations:
            sandbox_dirs = setup_workspaces(rtl_variations)
            print("\n✅ SUCCESS: Week 2 Pipeline Complete. Variations are isolated and ready for Ray.")
        else:
            print("❌ ERROR: Variations list is empty.")
    else:
        print("\nAborting hardware generation due to JSON failure.")
        
    # # 3. If JSON generation is successful, generate hardware variations
    # if isinstance(spec, dict):
    #     # We will generate 3 variations to save time, but your Ray cluster can handle 5 later
    #     rtl_variations = ai_client.generate_variations(spec, num_variations=3)
        
    #     print("\n================ FINAL RESULTS ================")
    #     for idx, rtl in enumerate(rtl_variations):
    #         print(f"\n--- VARIATION {idx + 1} ---")
    #         print(rtl)
    # else:
    #     print("\nAborting hardware generation due to JSON failure.")
# import os
# import json
# import anthropic
# from dotenv import load_dotenv

# # Load local .env file if it exists (for local testing outside Codespaces)
# load_dotenv()

# class EDA_LLM_Client:
#     def __init__(self):
#         """
#         Initializes the Anthropic client securely using the injected environment variable.
#         """
#         self.api_key = os.getenv("ANTHROPIC_API_KEY")
#         if not self.api_key:
#             raise ValueError("CRITICAL: ANTHROPIC_API_KEY environment variable is not set.")
        
#         # Initialize the official Anthropic client
#         self.client = anthropic.Anthropic(api_key=self.api_key)
        
#         # Using Haiku to minimize API token costs during pipeline testing
#         self.model_name = "claude-haiku-4-5-20251001" 

#         # -----------------------------------------------------------------------------
#         # THE PERSONA (SYSTEM PROMPT)
#         # -----------------------------------------------------------------------------
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
#         """
#         A simple ping test to verify the Anthropic API is reachable.
#         """
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
            
#         except anthropic.AuthenticationError:
#             return "❌ ERROR: Authentication failed. Check your API key."
#         except anthropic.RateLimitError:
#             return "❌ ERROR: Rate limit exceeded or account out of credits."
#         except Exception as e:
#             return f"❌ ERROR: An unexpected error occurred: {e}"

#     def generate_spec(self, user_request: str):
#         """
#         Translates a natural language hardware request into a strict JSON architecture specification.
#         """
#         print(f"[SYSTEM] Translating request to JSON Spec using {self.model_name}...")
        
#         # Step 1: Define the strict JSON schema
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
        
#         # Step 2: Formulate the prompt forcing the JSON constraint
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
#                 messages=[
#                     {"role": "user", "content": prompt}
#                 ]
#             )
            
#             raw_output = response.content[0].text.strip()
            
#             # Step 3: Python Validation Hook
#             spec_dict = json.loads(raw_output)
#             print("✅ SUCCESS: Valid JSON specification generated.")
#             return spec_dict
            
#         except json.JSONDecodeError as e:
#             return f"❌ ERROR: LLM failed to output valid JSON. Raw output was:\n{raw_output}\nError details: {e}"
#         except Exception as e:
#             return f"❌ ERROR: An unexpected error occurred: {e}"

# def generate_variations(self, spec_dict: dict, num_variations: int = 3):
#         """
#         Takes a strict JSON spec and generates N distinct SystemVerilog architectural variations.
#         """
#         print(f"\n[SYSTEM] Generating {num_variations} RTL variations using {self.model_name}...")
#         variations = []
        
#         # We define "seeds" to force the LLM to think differently for each variation.
#         # This mimics having 3 different human engineers write the code.
#         variation_seeds = [
#             "Implementation Strategy: Write standard, highly readable behavioral RTL using always_comb and case statements.",
#             "Implementation Strategy: Focus on lowest possible gate count and area utilization. Share logic where possible.",
#             "Implementation Strategy: Focus on maximum performance and minimum gate-delay latency, even if it costs more area."
#         ]
        
#         for i in range(num_variations):
#             # Fallback to a generic seed if num_variations > 3
#             seed = variation_seeds[i] if i < len(variation_seeds) else "Implementation Strategy: Generate a unique structural variation."
#             print(f"  -> Generating Variation {i+1} ({seed.split(':')[1].strip()[:30]}...)")
            
#             prompt = f"""
#             You are a master ASIC RTL designer. Implement the following module based STRICTLY on this JSON specification:
#             {json.dumps(spec_dict, indent=2)}
            
#             {seed}
            
#             CRITICAL RULES:
#             1. Use SystemVerilog (Verilog-2001 acceptable).
#             2. Match the module name, input, and output ports EXACTLY as defined in the JSON.
#             3. Output ONLY the raw code.
#             """
            
#             try:
#                 response = self.client.messages.create(
#                     model=self.model_name,
#                     max_tokens=1024,
#                     temperature=0.8, # HIGHER TEMPERATURE (0.8) encourages different architectural choices
#                     system=self.system_prompt,
#                     messages=[{"role": "user", "content": prompt}]
#                 )
                
#                 raw_text = response.content[0].text
                
#                 # Regex Extraction: 
#                 # Sometimes LLMs ignore the rule and wrap code in ```verilog ... ``` anyway.
#                 # This Regex looks for code blocks and extracts only what is inside them.
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

# # =============================================================================
# # Execution block for testing
# # =============================================================================
# if __name__ == "__main__":
#     ai_client = EDA_LLM_Client()
    
#     # 1. Ask for a 4-bit ALU
#     test_request = "Design a 4-bit ALU that can do addition, subtraction, AND, and OR operations. It needs a 2-bit opcode selector."
    
#     # 2. Get the JSON Spec
#     spec = ai_client.generate_spec(test_request)
    
#     # 3. If the JSON generation was successful, generate 3 hardware variations
#     if isinstance(spec, dict):
#         rtl_variations = ai_client.generate_variations(spec, num_variations=3)
        
#         print("\n================ FINAL RESULTS ================")
#         for idx, rtl in enumerate(rtl_variations):
#             print(f"\n--- VARIATION {idx + 1} ---")
#             print(rtl)
#     else:
#         print("\nAborting hardware generation due to JSON failure.")