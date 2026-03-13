import ray
import os
import time
from verifier import run_verification
from llm_client import EDA_LLM_Client, setup_workspaces
from models import HardwareSpec

# Note: Adjust these imports if your actual file names differ
from synthesizer import run_synthesis
from openlane_wrapper import run_openlane

# Suppress Ray's GPU warnings
os.environ["RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO"] = "0"

def initialize_dispatcher():
    num_cores = os.cpu_count()
    if not ray.is_initialized():
        ray.init(num_cpus=num_cores, log_to_driver=False)
    print(f"[SYSTEM] Ray cluster active. Cores available: {num_cores}\n")
    return num_cores

@ray.remote(num_cpus=1)
def verify_design_worker(workspace_dir: str, fallback_module_name: str, spec_dict: dict):
    return run_verification(workspace_dir, fallback_module_name, spec_dict)

if __name__ == "__main__":
    cores = initialize_dispatcher()
    ai_client = EDA_LLM_Client()
    
    print("\n================ PHASE 1: DYNAMIC GENERATION ================")
    # 1. Ask for SEQUENTIAL LOGIC
    test_request = "Design an 8-bit combinational multiplier. Inputs are 'a' and 'b' (8-bit). Output is 'p' (16-bit). Do not use a clock."
    
    # 2. Get the validated Pydantic HardwareSpec
    spec = ai_client.generate_spec(test_request)
    if not isinstance(spec, HardwareSpec):
        print(f"❌ Aborting pipeline due to Pydantic spec failure:\n{spec}")
        exit(1)
        
    spec_dict = spec.model_dump()
    print(f"[{spec_dict['module_name']}] Sequential Mode: {spec_dict['is_sequential']}")
    
    # 3. Generate RTL and isolate to workspaces
    rtl_variations = ai_client.generate_variations(spec, num_variations=3)
    if not rtl_variations:
        print("❌ ERROR: Variations list is empty.")
        exit(1)
        
    # THIS is the line that was missing! It creates the folders.
    run_folders = setup_workspaces(rtl_variations)
    module_name = spec.module_name

    print("\n================ PHASE 2: VERIFICATION & CRITIC RACE ================")
    MAX_RETRIES = 3
    winner = None

    for attempt in range(MAX_RETRIES):
        print(f"\n--- ATTEMPT {attempt + 1}/{MAX_RETRIES} ---")
        print(f"[RACE STARTED] Dispatching {len(run_folders)} Verilog architectures to Ray...")
        
        # Dispatch with the spec_dict so Jinja2 can build test_design.py
        futures = [verify_design_worker.remote(folder, module_name, spec_dict) for folder in run_folders]
        results = ray.get(futures)
        
        passed_designs = [res for res in results if res["status"] == "PASS"]
        
        print("\n[VERIFICATION RESULTS]")
        for res in results:
            icon = "✅" if res["status"] == "PASS" else "❌"
            print(f"{icon} {res['workspace']} | Time: {res['execution_time']:.2f}s")
            if res["status"] == "FAIL":
                print(f"    -> Extracted Errors:")
                # Print the FIRST 10 lines of the focused log, which contains the real errors
                for line in res['log'].splitlines()[:10]:
                    print(f"         {line}")
        if passed_designs:
            # Sort the passed designs by execution time
            winner = sorted(passed_designs, key=lambda x: x["execution_time"])[0]
            print(f"\n🏆 WINNER DECLARED: {winner['workspace']}")
            print(f"🏆 METRIC: Passed Verilator/Cocotb tests in {winner['execution_time']:.2f} seconds.")
            break  # Exit the retry loop!
            
        if attempt < MAX_RETRIES - 1:
            print("\n💀 ALL DESIGNS FAILED. Initiating LLM Critic Agent loop...")
            best_failure = sorted(results, key=lambda x: x["execution_time"])[0]

            # Read broken code
            design_path = os.path.join(best_failure["workspace"], "design.sv")
            with open(design_path, "r", encoding="utf-8") as f:
                broken_code = f.read()
                
            # Read dynamic Jinja2 testbench code to give to the Critic
            tb_path = os.path.join(best_failure["workspace"], "test_design.py")
            testbench_code = ""
            if os.path.exists(tb_path):
                with open(tb_path, "r", encoding="utf-8") as f:
                    testbench_code = f.read()

            # LLM auto-fix (Passes the code, the log, AND the testbench)
            is_seq_flag = spec_dict.get("is_sequential", False)
            fixed_code = ai_client.fix_design(broken_code, best_failure["log"], testbench_code, is_seq_flag)

            # Patch all workspaces for the next race
            for folder in run_folders:
                with open(os.path.join(folder, "design.sv"), "w", encoding="utf-8") as f:
                    f.write(fixed_code)
        else:
            print("\n💀 MAX RETRIES REACHED. Pipeline failed to generate working RTL.")

    # Only proceed to Back-End if we have a winner
    if winner:
        print(f"\n================ PHASE 3: DIGITAL BACK-END (DBE) ================")
        print(f"Passing {winner['workspace']}/design.sv to Yosys for synthesis...")
        
        synth_metrics = run_synthesis(winner['workspace'], winner["module_name"])
        
        if synth_metrics["status"] == "PASS":
            print("✅ SYNTHESIS SUCCESS!")
            print(f"📊 HARDWARE COST (AREA): {synth_metrics['gate_count']} Logic Gates")
            print(f"⏱️  SYNTHESIS TIME: {synth_metrics['execution_time']:.2f} seconds")
            
            print(f"\n[PHYSICAL DESIGN] Triggering OpenLane RTL-to-GDSII flow for {winner['module_name']}...")
            openlane_metrics = run_openlane(winner['workspace'], winner["module_name"], synth_metrics['gate_count'])
            print(openlane_metrics)
        else:
            print("❌ SYNTHESIS FAILED!")
            print(f"Error Snippet: {synth_metrics['log_snippet']}")
# import ray
# import os
# import time
# from verifier import run_verification
# from llm_client import EDA_LLM_Client, setup_workspaces
# from models import HardwareSpec

# # Note: Adjust these imports if your actual file names differ
# from synthesizer import run_synthesis
# from openlane_wrapper import run_openlane

# # Suppress Ray's GPU warnings
# os.environ["RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO"] = "0"

# def initialize_dispatcher():
#     num_cores = os.cpu_count()
#     if not ray.is_initialized():
#         ray.init(num_cpus=num_cores, log_to_driver=False)
#     print(f"[SYSTEM] Ray cluster active. Cores available: {num_cores}\n")
#     return num_cores

# # The parallel worker now receives the spec_dict to pass to Jinja2
# @ray.remote(num_cpus=1)
# def verify_design_worker(workspace_dir: str, fallback_module_name: str, spec_dict: dict):
#     return run_verification(workspace_dir, fallback_module_name, spec_dict)

# if __name__ == "__main__":
#     cores = initialize_dispatcher()
#     ai_client = EDA_LLM_Client()
    
#     print("\n================ PHASE 1: DYNAMIC GENERATION ================")
#     # 1. Ask for the hardware. 
#     test_request = "Design a 4-bit ALU that can do addition, subtraction, AND, and OR operations. It needs a 2-bit opcode selector."
    
#     # 2. Get the validated Pydantic HardwareSpec
#     spec = ai_client.generate_spec(test_request)
#     if not isinstance(spec, HardwareSpec):
#         print(f"❌ Aborting pipeline due to Pydantic spec failure:\n{spec}")
#         exit(1)
        
#     # Convert Pydantic model to dict for Jinja2 and add test vectors dynamically
#     spec_dict = spec.model_dump()
#     spec_dict["test_vectors"] = [
#         (5, 3, 0, 8),
#         (5, 3, 1, 2),
#         (5, 3, 2, 1),
#         (5, 3, 3, 7)
#     ]
    
#     # 3. Generate RTL and isolate to workspaces
#     rtl_variations = ai_client.generate_variations(spec, num_variations=3)
#     if not rtl_variations:
#         print("❌ ERROR: Variations list is empty.")
#         exit(1)
        
#     run_folders = setup_workspaces(rtl_variations)
#     module_name = spec.module_name

#     print("\n================ PHASE 2: VERIFICATION & CRITIC RACE ================")
#     MAX_RETRIES = 3
#     winner = None

#     for attempt in range(MAX_RETRIES):
#         print(f"\n--- ATTEMPT {attempt + 1}/{MAX_RETRIES} ---")
#         print(f"[RACE STARTED] Dispatching {len(run_folders)} Verilog architectures to Ray...")
        
#         # Dispatch with the spec_dict so Jinja2 can build test_design.py
#         futures = [verify_design_worker.remote(folder, module_name, spec_dict) for folder in run_folders]
#         results = ray.get(futures)
        
#         passed_designs = [res for res in results if res["status"] == "PASS"]
        
#         print("\n[VERIFICATION RESULTS]")
#         for res in results:
#             icon = "✅" if res["status"] == "PASS" else "❌"
#             print(f"{icon} {res['workspace']} | Time: {res['execution_time']:.2f}s")
#             if res["status"] == "FAIL":
#                 print(f"    -> Error Snippet: {res['log'].splitlines()[-3:]}")

#         if passed_designs:
#             # Sort the passed designs by execution time
#             winner = sorted(passed_designs, key=lambda x: x["execution_time"])[0]
#             print(f"\n🏆 WINNER DECLARED: {winner['workspace']}")
#             print(f"🏆 METRIC: Passed Verilator/Cocotb tests in {winner['execution_time']:.2f} seconds.")
#             break  # Exit the retry loop!
            
#         if attempt < MAX_RETRIES - 1:
#             print("\n💀 ALL DESIGNS FAILED. Initiating LLM Critic Agent loop...")
#             # Select fastest failure as repair candidate
#             best_failure = sorted(results, key=lambda x: x["execution_time"])[0]

#             # Read broken code
#             design_path = os.path.join(best_failure["workspace"], "design.sv")
#             with open(design_path, "r", encoding="utf-8") as f:
#                 broken_code = f.read()
                
#             # Read dynamic Jinja2 testbench code to give to the Critic
#             tb_path = os.path.join(best_failure["workspace"], "test_design.py")
#             testbench_code = ""
#             if os.path.exists(tb_path):
#                 with open(tb_path, "r", encoding="utf-8") as f:
#                     testbench_code = f.read()

#             # LLM auto-fix (Passes the code, the log, AND the testbench)
#             fixed_code = ai_client.fix_design(broken_code, best_failure["log"], testbench_code)

#             # Patch all workspaces for the next race
#             for folder in run_folders:
#                 with open(os.path.join(folder, "design.sv"), "w", encoding="utf-8") as f:
#                     f.write(fixed_code)
#         else:
#             print("\n💀 MAX RETRIES REACHED. Pipeline failed to generate working RTL.")

#     # Only proceed to Back-End if we have a winner
#     if winner:
#         print(f"\n================ PHASE 3: DIGITAL BACK-END (DBE) ================")
#         print(f"Passing {winner['workspace']}/design.sv to Yosys for synthesis...")
        
#         synth_metrics = run_synthesis(winner['workspace'], winner["module_name"])
        
#         if synth_metrics["status"] == "PASS":
#             print("✅ SYNTHESIS SUCCESS!")
#             print(f"📊 HARDWARE COST (AREA): {synth_metrics['gate_count']} Logic Gates")
#             print(f"⏱️  SYNTHESIS TIME: {synth_metrics['execution_time']:.2f} seconds")
            
#             print(f"\n[PHYSICAL DESIGN] Triggering OpenLane RTL-to-GDSII flow for {winner['module_name']}...")
#             openlane_metrics = run_openlane(winner['workspace'], winner["module_name"])
#             print(openlane_metrics)
#         else:
#             print("❌ SYNTHESIS FAILED!")
#             print(f"Error Snippet: {synth_metrics['log_snippet']}")