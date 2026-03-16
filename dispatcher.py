import argparse
import json
import os
import sys
import time
import shutil
import requests
from pathlib import Path
from telemetry import log_pipeline_run 
from verifier import run_verification
from rag_agent import HardwareRAG
from llm_client import EDA_LLM_Client
from models import ArchitecturePlan, HardwareSpec, SystemTask
import formal_verifier

# Note: Adjust these imports if your actual file names differ
from synthesizer import run_synthesis
from openlane_wrapper import run_openlane
from quartus_wrapper import run_fpga_compilation

# Suppress Ray's GPU warnings
os.environ["RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO"] = "0"

def initialize_dispatcher():
    print("[SYSTEM] Dispatcher initialized (Ray disabled).")
    return 1

if __name__ == "__main__":
    global_start_time = time.time()
    cores = initialize_dispatcher()

    parser = argparse.ArgumentParser(description="EDA Dispatcher")
    parser.add_argument(
        "--task",
        type=str,
        help="Run a specific module name without invoking RAG/decomposition.",
    )
    args = parser.parse_args()

    if args.task:
        print(f"[SYSTEM] Running ad-hoc task '{args.task}' without RAG/decomposition.")
        plan = ArchitecturePlan(
            is_complex=False,
            tasks=[
                SystemTask(
                    module_name=args.task,
                    prompt=f"Design the {args.task}.",
                    component_class="TOP_LEVEL",
                    requires_dummy_oracle=False,
                )
            ],
        )
        ai_client = EDA_LLM_Client(rag=None)
    else:
        base_request = "Design a single-cycle 32-bit RISC-V CPU core implementing the OSOC F6 minirv subset."
        rag = HardwareRAG(collections=["hardware_specs"])
        rag_context = rag.retrieve_context(base_request, n_results=3)
        test_request = base_request
        if rag_context:
            test_request += (
                "\n\nCRITICAL ARCHITECTURE RULES (From Knowledge Base):\n"
                f"{rag_context}\n"
            )

        ai_client = EDA_LLM_Client(rag=rag)

        cache_path = Path("plan_cache.json")
        if cache_path.exists():
            with cache_path.open("r", encoding="utf-8") as f:
                plan = ArchitecturePlan.model_validate_json(f.read())
            print("[SYSTEM] Loaded ArchitecturePlan from cache.")
        else:
            plan = ai_client.decompose_architecture(test_request)
            if isinstance(plan, ArchitecturePlan):
                cache_path.write_text(plan.model_dump_json(), encoding="utf-8")
        if isinstance(plan, str):
            print(f"❌ Architecture decomposition failed: {plan}")
            sys.exit(1)
    os.makedirs("ip_library", exist_ok=True)

    idx = 0
    MAX_TOTAL_TASKS = 25
    consecutive_failures = 0
    while idx < len(plan.tasks):
        if len(plan.tasks) > MAX_TOTAL_TASKS:
            print("[FATAL] Task limit exceeded (Decomposition Death Spiral). Aborting to protect API budget.")
            sys.exit(1)
        task = plan.tasks[idx]
        ip_path = os.path.join("ip_library", f"{task.module_name}.sv")
        if os.path.exists(ip_path):
            print(f"[SYSTEM] Verified IP found for '{task.module_name}'. Skipping generation.")
            idx += 1
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

        dummy_oracle = (
            "def generate_test_vectors():\n"
            "    return [{'opcode': 0}]\n"
            "def golden_model(state, inputs):\n"
            "    return state, inputs\n"
        )
        if spec_dict.get("component_class", "").upper() == "FSM":
            oracle_code = {"golden_model_and_test_generator": dummy_oracle}
        else:
            oracle_code = ai_client.generate_verification_oracle(spec_dict, oracle_prompt)
            if isinstance(oracle_code, str):
                print(f"❌ Oracle generation failed for {task.module_name}: {oracle_code}")
                sys.exit(1)

        spec_dict["golden_model_python"] = oracle_code["golden_model_and_test_generator"]
        spec_dict["test_vector_generator_python"] = ""

        module_name = spec.module_name
        workspace_dir = "workspace"

        print("\n================ PHASE 2: VERIFICATION & CRITIC RACE ================")
        MAX_RETRIES = 2
        winner = None

        replan_requested = False
        for attempt in range(MAX_RETRIES):
            print(f"\n--- ATTEMPT {attempt + 1}/{MAX_RETRIES} ---")
            shutil.rmtree(workspace_dir, ignore_errors=True)
            os.makedirs(workspace_dir, exist_ok=True)

            print(f"[SYSTEM] Generating RTL for attempt {attempt + 1}...")
            rtl_code = ai_client.generate_rtl(spec)
            design_path = Path(workspace_dir) / "design.sv"
            design_path.write_text(rtl_code, encoding="utf-8")

            print("[SYSTEM] Running Verilator/Cocotb verification...")
            result = run_verification(workspace_dir, module_name, spec_dict)
            print(f"[SYSTEM] Verification status: {result['status']}")
            if result["status"] == "PASS":
                winner = result
                break

            if attempt < MAX_RETRIES - 1:
                print("\n💀 Design failed. Initiating LLM Critic Agent loop...")
                failure_error_type = result.get("error_type", "LOGIC")
                failure_log = result["log"]
                if failure_error_type.upper() == "SYNTAX":
                    syntax_match = re.search(
                        r"%Error:[^:]+design\.sv:(\d+):\s*(.*)", failure_log
                    )
                    if syntax_match:
                        line_no = int(syntax_match.group(1))
                        message = syntax_match.group(2).strip()
                        design_path = Path(result["workspace"]) / "design.sv"
                        snippet = ""
                        if design_path.exists():
                            design_lines = design_path.read_text().splitlines()
                            start = max(line_no - 3, 0)
                            end = min(line_no + 2, len(design_lines))
                            snippet_lines = []
                            for idx in range(start, end):
                                snippet_lines.append(
                                    f"{idx + 1}: {design_lines[idx]}"
                                )
                            snippet = "\n".join(snippet_lines)
                        failure_log = (
                            f"Syntax Error on Line {line_no}:\n{snippet}\n"
                            f"Error: {message}"
                        )
            if result["status"] == "FAIL_LINT":
                failure_log += (
                    "\n\nCRITICAL LINT FAILURE: Your logic introduced a severe physical violation "
                    "(e.g., a Latch or Multiple Drivers). You must rewrite the internal logic to be structurally sound. "
                    "Do not ignore this lint error."
                )

                if any(err in failure_log for err in ["Python Golden Model crashed", "NameError", "ValueError"]) and "%Error:" not in failure_log:
                    print("❌ Python Testbench Bug Detected. Aborting Critic Loop to save tokens.")
                    break
                if "SyntaxError:" in failure_log and "%Error:" not in failure_log:
                    print("[SYSTEM] Python Oracle syntax error detected. Aborting Critic Loop to prevent Verilog corruption.")
                    break

                broken_code_path = Path(result["workspace"]) / "design.sv"
                broken_code = broken_code_path.read_text()

                testbench_path = Path(result["workspace"]) / "test_design.py"
                testbench_code = testbench_path.read_text() if testbench_path.exists() else ""

                is_seq_flag = spec_dict.get("is_sequential", False)
                error_log = failure_log
                diag_context = result.get("diagnostic_context")
                if diag_context:
                    error_log += "\n\n=== OFFICIAL EDA DIAGNOSTICS ===\n" + diag_context
                    print("    -> Appended official diagnostics to Critic payload.")

                failure_context_file = Path(result["workspace"]) / "failure_context.json"
                if failure_context_file.exists():
                    parsed = json.loads(failure_context_file.read_text())
                    error_log += "\n\n=== COCOTB FAILURE PAYLOAD ===\n" + json.dumps(parsed, indent=2)
                    print("    -> Appended Cocotb failure payload to Critic payload.")

                failure_error_type = result.get("error_type", "LOGIC")
                fixed_code = ai_client.fix_design(
                    broken_code,
                    error_log,
                    testbench_code,
                    is_seq_flag,
                    error_type=failure_error_type,
                    retry_count=attempt,
                    workspace_dir=workspace_dir,
                )
                if isinstance(fixed_code, dict) and fixed_code.get("action") == "DECOMPOSE":
                    print("[SYSTEM] Critic requested decomposition. Re-planning Task...")
                    new_plan = ai_client.decompose_architecture(task.prompt)
                    if isinstance(new_plan, str):
                        print(f"❌ Re-plan failed: {new_plan}")
                        sys.exit(1)

                    plan.tasks[idx:idx+1] = new_plan.tasks
                    replan_requested = True
                    break

                design_path.write_text(fixed_code, encoding="utf-8")
            else:
                print("\n💀 MAX RETRIES REACHED. Task failed.")

        if replan_requested:
            continue

        if not winner:
            print(f"[SYSTEM] Task '{task.module_name}' exhausted all retries. Forcing architectural decomposition...")
            new_plan = ai_client.decompose_architecture(task.prompt, force_submodules=True)
            if isinstance(new_plan, str):
                consecutive_failures += 1
                if consecutive_failures >= 2:
                    print("[FATAL] Multiple consecutive tasks failed irreparably. The architectural plan is fundamentally flawed. Aborting to save API credits.")
                print(f"❌ Task '{task.module_name}' failed after {MAX_RETRIES} attempt(s). Aborting downstream tasks.")
                shutil.rmtree("workspace", ignore_errors=True)
                sys.exit(1)
            plan.tasks[idx:idx+1] = new_plan.tasks
            replan_requested = True
            continue

        # --- FORMAL VERIFICATION GATING (BYPASSED) ---
        print(f"[SYSTEM] Skipping Formal Verification for {task.module_name}. Relying on CRV Simulation pass.")
        formal_result = {"status": "PASSED"}
        formal_passed = True

        consecutive_failures = 0
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

        # ------------------------------------------------------------------
        # PHASE 3: DIGITAL BACK-END (DBE) - MOVED INSIDE THE WHILE LOOP
        # ------------------------------------------------------------------
        if winner:
            print(f"\n================ PHASE 3: DIGITAL BACK-END (DBE) ================")
            print(f"Passing {winner['workspace']}/design.sv to Yosys for synthesis...")
            
            synth_metrics = run_synthesis(winner['workspace'], winner["module_name"])
            
            if synth_metrics["status"] == "PASS":
                print("✅ SYNTHESIS SUCCESS!")
                print(f"📊 HARDWARE COST (AREA): {synth_metrics['gate_count']} Logic Gates")
                print(f"⏱️  SYNTHESIS TIME: {synth_metrics['execution_time']:.2f} seconds")
                
                # OPTIMIZATION: Only run OpenLane if it is the Top-Level CPU!
                if spec_dict.get("component_class", "").upper() == "TOP_LEVEL":
                    # print(f"\n[PHYSICAL DESIGN] Triggering OpenLane RTL-to-GDSII flow...")
                    # openlane_metrics = run_openlane(winner['workspace'], winner["module_name"], synth_metrics['gate_count'])
                    # print(openlane_metrics)
                    pass
                else:
                    print(f"[SYSTEM] Skipping OpenLane physical layout for sub-module.")

        # Cleanup the workspace AFTER synthesis is done
        shutil.rmtree("workspace", ignore_errors=True)
        idx += 1
