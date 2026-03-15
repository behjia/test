import json
import os
import sys
import time
import shutil
import requests
import ray
from telemetry import log_pipeline_run 
from verifier import run_verification
from rag_agent import HardwareRAG
from llm_client import EDA_LLM_Client, setup_workspaces
from models import ArchitecturePlan, HardwareSpec

# Note: Adjust these imports if your actual file names differ
from synthesizer import run_synthesis
from openlane_wrapper import run_openlane
from quartus_wrapper import run_fpga_compilation

# Suppress Ray's GPU warnings
os.environ["RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO"] = "0"

def initialize_dispatcher():
    num_cores = os.cpu_count()
    if not ray.is_initialized():
        #ray.init(num_cpus=num_cores, log_to_driver=False)
        # FORCE 1 CPU: Prevents Verilator g++ from running out of RAM
        ray.init(num_cpus=1, log_to_driver=False) 
    print(f"[SYSTEM] Ray cluster active. Cores available: {num_cores}. Throttled to 1 Core to prevent OOM.\n")
    return 1

@ray.remote(num_cpus=1)
def verify_design_worker(workspace_dir: str, fallback_module_name: str, spec_dict: dict):
    return run_verification(workspace_dir, fallback_module_name, spec_dict)

if __name__ == "__main__":
    global_start_time = time.time()
    cores = initialize_dispatcher()

    rag_db = HardwareRAG()
    ai_client = EDA_LLM_Client(rag=rag_db)

    os.makedirs("ip_library", exist_ok=True)

    test_request = "Design a single-cycle 32-bit RISC-V CPU core."
    plan = ai_client.decompose_architecture(test_request)
    if isinstance(plan, str):
        print(f"❌ Architecture decomposition failed: {plan}")
        sys.exit(1)

    for idx, task in enumerate(plan.tasks):
        ip_path = os.path.join("ip_library", f"{task.module_name}.sv")
        if os.path.exists(ip_path):
            print(f"[SYSTEM] Verified IP found for '{task.module_name}'. Skipping generation.")
            continue

        print(f"\n=== EXECUTING TASK {idx + 1}/{len(plan.tasks)}: {task.module_name} ===")
        task_start_time = time.time()

        spec = ai_client.generate_spec(task.prompt)
        if not isinstance(spec, HardwareSpec):
            print(f"❌ Aborting: Spec generation failed for {task.module_name}:\n{spec}")
            sys.exit(1)

        spec = ai_client.review_and_fix_spec(spec)
        spec_dict = spec.model_dump()

        oracle_prompt = task.prompt
        if task.requires_dummy_oracle:
            oracle_prompt += (
                " CRITICAL: DO NOT write a cycle-accurate simulator. Write a dummy golden model "
                "that returns the inputs unchanged, and a test vector generator that yields 5 "
                "cycles of basic reset/random toggles."
            )
        oracle_code = ai_client.generate_verification_oracle(spec_dict, oracle_prompt)
        if isinstance(oracle_code, str):
            print(f"❌ Oracle generation failed for {task.module_name}: {oracle_code}")
            sys.exit(1)

        spec_dict["golden_model_python"] = oracle_code["golden_model_and_test_generator"]
        spec_dict["test_vector_generator_python"] = ""

        rtl_variations = ai_client.generate_variations(spec, num_variations=3)
        if not rtl_variations:
            print(f"❌ ERROR: Variations list is empty for {task.module_name}.")
            shutil.rmtree("workspace", ignore_errors=True)
            sys.exit(1)

        run_folders = setup_workspaces(rtl_variations)
        module_name = spec.module_name

        print("\n================ PHASE 2: VERIFICATION & CRITIC RACE ================")
        MAX_RETRIES = 2
        winner = None

        for attempt in range(MAX_RETRIES):
            print(f"\n--- ATTEMPT {attempt + 1}/{MAX_RETRIES} ---")
            print(f"[RACE STARTED] Dispatching {len(run_folders)} Verilog architectures to Ray...")
            futures = [
                verify_design_worker.remote(folder, module_name, spec_dict)
                for folder in run_folders
            ]
            results = ray.get(futures)

            passed_designs = [res for res in results if res["status"] == "PASS"]

            print("\n[VERIFICATION RESULTS]")
            for res in results:
                icon = "✅" if res["status"] == "PASS" else "❌"
                print(f"{icon} {res['workspace']} | Time: {res['execution_time']:.2f}s")
                if res["status"] == "FAIL":
                    print("    -> Extracted Errors:")
                    tags = res.get("error_tags", [])
                    if tags:
                        print(f"    -> Verilator tags: {', '.join(tags)}")
                    for line in res["log"].splitlines()[:10]:
                        print(f"         {line}")
            if passed_designs:
                winner = sorted(passed_designs, key=lambda x: x["execution_time"])[0]
                print(f"\n🏆 WINNER DECLARED: {winner['workspace']}")
                print(f"🏆 METRIC: Passed Verilator/Cocotb tests in {winner['execution_time']:.2f} seconds.")
                break

            if attempt < MAX_RETRIES - 1:
                print("\n💀 ALL DESIGNS FAILED. Initiating LLM Critic Agent loop...")
                best_failure = sorted(results, key=lambda x: x["execution_time"])[0]
                failure_log = best_failure["log"]

                # 1. Circuit Breaker 1
                if any(err in failure_log for err in ["Python Golden Model crashed", "NameError", "ValueError"]) and "%Error:" not in failure_log:
                    print("❌ Python Testbench Bug Detected. Aborting Critic Loop to save tokens.")
                    break
                
                # 2. Circuit Breaker 2
                if "SyntaxError:" in failure_log and "%Error:" not in failure_log:
                    print("[SYSTEM] Python Oracle syntax error detected. Aborting Critic Loop to prevent Verilog corruption.")
                    break

                # 3. Extract the broken code
                design_path = os.path.join(best_failure["workspace"], "design.sv")
                with open(design_path, "r", encoding="utf-8") as f:
                    broken_code = f.read()

                # 4. Extract the testbench code
                tb_path = os.path.join(best_failure["workspace"], "test_design.py")
                testbench_code = ""
                if os.path.exists(tb_path):
                    with open(tb_path, "r", encoding="utf-8") as f:
                        testbench_code = f.read()

                # 5. Append Diagnostics & Payloads
                is_seq_flag = spec_dict.get("is_sequential", False)
                error_log = best_failure["log"]
                diag_context = best_failure.get("diagnostic_context")
                if diag_context:
                    error_log += "\n\n=== OFFICIAL EDA DIAGNOSTICS ===\n" + diag_context
                    print("    -> Appended official diagnostics to Critic payload.")

                failure_file = os.path.join(best_failure["workspace"], "failure_context.json")
                if os.path.exists(failure_file):
                    with open(failure_file, "r", encoding="utf-8") as f:
                        parsed = json.load(f)
                    error_log += "\n\n=== COCOTB FAILURE PAYLOAD ===\n" + json.dumps(parsed, indent=2)
                    print("    -> Appended Cocotb failure payload to Critic payload.")

                # 6. Call the Critic Agent
                fixed_code = ai_client.fix_design(
                    broken_code,
                    error_log,
                    testbench_code,
                    is_seq_flag,
                    retry_count=attempt,
                )

                # 7. Patch workspaces for Attempt 2
                for folder in run_folders:
                    failure_path = os.path.join(folder, "failure_context.json")
                    if os.path.exists(failure_path):
                        os.remove(failure_path)
                    with open(os.path.join(folder, "design.sv"), "w", encoding="utf-8") as f:
                        f.write(fixed_code)
            else:
                print("\n💀 MAX RETRIES REACHED. Task failed.")

        if not winner:
            print(f"❌ Task '{task.module_name}' failed after {MAX_RETRIES} attempt(s). Aborting downstream tasks.")
            shutil.rmtree("workspace", ignore_errors=True)
            sys.exit(1)

        shutil.copy(
            os.path.join(winner["workspace"], "design.sv"),
            os.path.join("ip_library", f"{task.module_name}.sv"),
        )
        with open(os.path.join("ip_library", f"{task.module_name}.json"), "w", encoding="utf-8") as f:
            json.dump(spec_dict, f, indent=2)
            
        log_pipeline_run(
            module_name=module_name,
            spec_model=ai_client.spec_model,
            is_sequential=spec_dict.get("is_sequential", False),
            winner_workspace=winner["workspace"],
            attempts=MAX_RETRIES,
            total_time=time.time() - task_start_time,
            final_status="SUCCESS",
        )

        shutil.rmtree("workspace", ignore_errors=True)
    
    # Only proceed to Back-End if we have a winner
    if winner:
        print(f"\n================ PHASE 3: DIGITAL BACK-END (DBE) ================")
        print(f"Passing {winner['workspace']}/design.sv to Yosys for synthesis...")
        
        synth_metrics = run_synthesis(winner['workspace'], winner["module_name"])
        
        if synth_metrics["status"] == "PASS":
            print("✅ SYNTHESIS SUCCESS!")
            print(f"📊 HARDWARE COST (AREA): {synth_metrics['gate_count']} Logic Gates")
            print(f"⏱️  SYNTHESIS TIME: {synth_metrics['execution_time']:.2f} seconds")
            # Commented out for testing
            # print(f"\n[PHYSICAL DESIGN] Triggering OpenLane RTL-to-GDSII flow for {winner['module_name']}...")
            # openlane_metrics = run_openlane(winner['workspace'], winner["module_name"], synth_metrics['gate_count'])
            # print(openlane_metrics)

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
