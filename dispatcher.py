import ray
import os
import time
import requests
from telemetry import log_pipeline_run 
from verifier import run_verification
from llm_client import EDA_LLM_Client, setup_workspaces
from models import HardwareSpec

# Note: Adjust these imports if your actual file names differ
from synthesizer import run_synthesis
from openlane_wrapper import run_openlane
from quartus_wrapper import run_fpga_compilation

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
    global_start_time = time.time() # <-- ADD START TIMER
    cores = initialize_dispatcher()
    ai_client = EDA_LLM_Client()
    
    print("\n================ PHASE 1: DYNAMIC GENERATION ================")
    # 1. Ask for a sequential memory unit
    # The Real Target: 1-bit MAC
    test_request = (
        "Design a 16-word by 32-bit synchronous FIFO buffer. "
        "It must include clk, rst_n, write_en, read_en, data_in [31:0], data_out [31:0], full, and empty flags. "
        "CRITICAL ARCHITECTURE RULE: This is a Standard FIFO, NOT a First-Word Fall-Through (FWFT) FIFO. "
        "The 'data_out' port must output 0 if 'read_en' is 0. Data should only appear on 'data_out' on the clock cycle AFTER 'read_en' is asserted."
    )
    
    # 2. Get the validated Pydantic HardwareSpec
    spec = ai_client.generate_spec(test_request)
    if not isinstance(spec, HardwareSpec):
        print(f"❌ Aborting pipeline due to Pydantic spec failure:\n{spec}")
        exit(1)

    # ---> NEW: RUN THE REVIEWER AGENT <---
    spec = ai_client.review_and_fix_spec(spec)

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
    MAX_RETRIES = 4
    winner = None
    final_attempts = 0 # <-- Track for telemetry

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

            # ---> FIX: Pass retry_count=attempt to the Critic <---
            is_seq_flag = spec_dict.get("is_sequential", False)
            fixed_code = ai_client.fix_design(broken_code, best_failure["log"], testbench_code, is_seq_flag, retry_count=attempt)

            # Patch all workspaces for the next race
            for folder in run_folders:
                with open(os.path.join(folder, "design.sv"), "w", encoding="utf-8") as f:
                    f.write(fixed_code)
        else:
            print("\n💀 MAX RETRIES REACHED. Pipeline failed to generate working RTL.")
    
    # ---> NEW: TELEMETRY LOGGING <---
    total_time = time.time() - global_start_time
    final_status = "SUCCESS" if winner else "FAILED"
    winner_path = winner['workspace'] if winner else "None"
    
    log_pipeline_run(
        module_name=module_name, 
        spec_model=ai_client.spec_model, 
        is_sequential=spec_dict.get("is_sequential", False),
        winner_workspace=winner_path,
        attempts=final_attempts,
        total_time=total_time,
        final_status=final_status
    )
    
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

            # # ---------------------------------------------------------- #
            # # PHASE 4: PHYSICAL FPGA DEPLOYMENT (REMOTE API)             #
            # # ---------------------------------------------------------- #

            # print(f"\n================ PHASE 4: PHYSICAL FPGA DEPLOYMENT ================")
            # print(f"[PHYSICAL DEPLOYMENT] Sending winner to Remote Windows Quartus Server...")
            
            # # Read the winning Verilog code
            # design_path = os.path.join(winner['workspace'], "design.sv")
            # with open(design_path, "r", encoding="utf-8") as f:
            #     sv_code = f.read()

            # # PASTE YOUR NGROK URL HERE:
            # NGROK_URL = "https://unsegregable-uncorrelatedly-sheryl.ngrok-free.dev"

            # payload = {
            #     "module_name": module_name,
            #     "systemverilog_code": sv_code
            # }

            # try:
            #     # Send the POST request to the Windows API
            #     response = requests.post(f"{NGROK_URL}/compile", json=payload)
                
            #     if response.status_code == 200:
            #         quartus_result = response.json()
            #         if quartus_result["status"] == "success":
            #             print(f"\n✅ REMOTE QUARTUS SUCCESS — Synthesis Complete!")
            #             print(f"   Compile time : {quartus_result['execution_time']} seconds")
            #         else:
            #             print(f"\n❌ REMOTE QUARTUS FAILED.")
            #             print(f"   Compile time : {quartus_result['execution_time']} seconds")
            #             print(f"   Error tail   :\n{quartus_result.get('error_tail', 'No log provided')}")
            #     else:
            #         print(f"❌ Server Error {response.status_code}: {response.text}")
            # except Exception as e:
            #     print(f"❌ Connection failed! Is the Windows server and Ngrok running? Error: {e}")