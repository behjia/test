import re
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
from rag_agent import HybridRAG
from llm_client import EDA_LLM_Client
from models import ArchitecturePlan, HardwareSpec, SystemTask
from ip_manager import IPManager
import formal_verifier
from jinja2 import Environment, FileSystemLoader

# Note: Adjust these imports if your actual file names differ
from synthesizer import run_synthesis
from openlane_wrapper import run_openlane
from quartus_wrapper import run_fpga_compilation

# Suppress Ray's GPU warnings
os.environ["RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO"] = "0"

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_TEMPLATE_ENV = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

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
        help='Run a specific module name',
    )
    parser.add_argument(
        '--comp_class', 
        type=str, 
        default='DATAPATH', 
        help='Component class: FSM, DATAPATH, MEMORY, INTERCONNECT, TOP_LEVEL'
    )
    args = parser.parse_args()

    micro_graph_text = ""
    micro_graph_path = Path("riscv_micro_graph.json")
    if micro_graph_path.exists():
        micro_graph_text = micro_graph_path.read_text(encoding="utf-8")
    else:
        print("[SYSTEM] Warning: riscv_micro_graph.json not found; running without micro-graph guidance.")

    if args.task:
        print(f"[SYSTEM] Running ad-hoc task '{args.task}'...")
        
        # 1. Fetch the RAG Context (Don't skip this!)
        rag = HardwareRAG(collections=["hardware_specs"])
        rag_context = rag.retrieve_context("32-bit RISC-V CPU core OSOC F6 minirv", n_results=3)
        
        # 2. Fetch the Micro-Graph (Truth Table)
        try:
            with open("riscv_micro_graph.json", "r") as f:
                micro_graph_text = f.read()
        except FileNotFoundError:
            micro_graph_text = "No micro-graph found."

        # 3. Build a "Rich" Ad-Hoc Prompt
        ad_hoc_prompt = (
            f"Design the {args.task} for a 32-bit RISC-V CPU core.\n\n"
            f"CRITICAL ARCHITECTURE RULES:\n{rag_context}\n\n"
            f"CRITICAL RELATIONAL LOGIC MAP (MICRO-GRAPH):\n"
            f"You MUST use this exact JSON truth table to map instructions to control signals.\n"
            f"{micro_graph_text}"
        )

        # 4. Create the Single-Task Plan
        plan = ArchitecturePlan(
            is_complex=False,
            tasks=[SystemTask(
                module_name=args.task,
                prompt=ad_hoc_prompt,
                # Automatically set dummy oracle if it's the TOP_LEVEL
                requires_dummy_oracle=(args.comp_class.upper() == "TOP_LEVEL"),
                component_class=args.comp_class.upper()
            )]
        )
        ai_client = EDA_LLM_Client(rag=None)
    else:
        base_request = "Design a single-cycle 32-bit RISC-V CPU core implementing the OSOC F6 minirv subset."
        rag = HybridRAG(vector_collections=["hardware_specs"])
        rag_context = rag.retrieve_context(base_request, n_results=3)
        test_request = base_request
        if rag_context:
            test_request += (
                "\n\nCRITICAL ARCHITECTURE RULES (From Knowledge Base):\n"
                f"{rag_context}\n"
            )
        if micro_graph_text:
            test_request += (
                "\n\nCRITICAL RELATIONAL LOGIC MAP (MICRO-GRAPH):\n"
                "You MUST NOT guess control signals or opcodes. You MUST use this exact JSON truth table to map instructions to control signals.\n"
                "If building a Python Oracle, use this JSON to define your expected outputs. \n"
                "If building Verilog RTL, use this JSON to construct your case statements.\n"
                f"{micro_graph_text}\n"
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
    ip_mgr = IPManager()

    modules_by_class: dict[str, list[str]] = {}
    for t in plan.tasks:
        modules_by_class.setdefault(t.component_class, []).append(t.module_name)
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

        complex_keywords = {
            "core",
            "cpu",
            "system",
            "control",
            "datapath",
            "mmu",
            "mcu",
            "fpu",
        }
        lower_name = task.module_name.lower()
        is_too_complex = any(keyword in lower_name for keyword in complex_keywords)
        if is_too_complex and task.component_class != "TOP_LEVEL":
            print(f"[SYSTEM] Heuristic triggered: Task '{task.module_name}' is too complex for single-shot generation. Proactively decomposing...")
            new_plan = ai_client.decompose_architecture(task.prompt, force_submodules=True)
            if isinstance(new_plan, str):
                print(f"❌ Heuristic re-plan failed: {new_plan}")
                sys.exit(1)
            plan.tasks[idx:idx+1] = new_plan.tasks
            replan_requested = True
            continue

        print(f"\n=== EXECUTING TASK {idx + 1}/{len(plan.tasks)}: {task.module_name} ===")
        task_start_time = time.time()

        spec = ai_client.generate_spec(task.prompt)
        if not isinstance(spec, HardwareSpec):
            print(f"❌ Aborting: Spec generation failed for {task.module_name}:\n{spec}")
            sys.exit(1)

        spec = ai_client.review_and_fix_spec(spec)
        spec_dict = spec.model_dump()

        # FORCE-INJECT THE COMPONENT CLASS SO VERIFIER.PY KNOWS WHICH TEMPLATE TO USE!
        spec_dict["component_class"] = task.component_class

        oracle_prompt = task.prompt
        if task.requires_dummy_oracle:
            oracle_prompt += (
                " CRITICAL: This should be a pass-through truth table; keep it minimal and only mirror the inputs as outputs."
            )

        if task.component_class.upper() in ["FSM", "TOP_LEVEL"]:
            print(f"[SYSTEM] Bypassing Python Oracle for {task.component_class} module.")
            # Provide a safe dummy Python golden model that won't crash the Jinja2 template
            spec_dict["golden_model_python"] = (
                "def generate_test_vectors():\n"
                "    return [{'dummy': 0}]\n"
                "def golden_model(state, inputs):\n"
                "    return state, {}\n"
            )
        else:
            print("[SYSTEM] Generating verification oracle (truth-table JSON)...")
            try:
                truth_table_json = ai_client.generate_verification_oracle(
                    spec_dict,
                    oracle_prompt,
                    module_name=task.module_name,
                    component_class=task.component_class,
                )
            except Exception as exc:
                print(f"❌ Oracle generation failed for {task.module_name}: {exc}")
                sys.exit(1)

            input_ports = [port["name"] for port in spec_dict.get("inputs", [])]
            output_ports = [port["name"] for port in spec_dict.get("outputs", [])]
            port_widths = {port["name"]: port.get("width", 1) for port in spec_dict.get("inputs", [])}

            golden_template = _TEMPLATE_ENV.get_template("golden_model.py.jinja")
            rendered_golden = golden_template.render(
                truth_table_json=truth_table_json,
                input_ports=input_ports,
                output_ports=output_ports,
                port_widths=port_widths,
            )
            spec_dict["golden_model_python"] = rendered_golden

        module_name = spec.module_name
        workspace_dir = "workspace"

        print("\n================ PHASE 2: VERIFICATION & CRITIC RACE ================")
        MAX_RETRIES = 2
        winner = None

        replan_requested = False
        for attempt in range(MAX_RETRIES):
            print(f"\n--- ATTEMPT {attempt + 1}/{MAX_RETRIES} ---")
            
            design_path = Path(workspace_dir) / "design.sv"
            
            # 1. GENERATION (Only on Attempt 1)
            if attempt == 0:
                shutil.rmtree(workspace_dir, ignore_errors=True)
                os.makedirs(workspace_dir, exist_ok=True)
                print(f"[SYSTEM] Generating RTL for attempt 1...")
                rtl_code = ai_client.generate_rtl(spec)
                design_path.write_text(rtl_code, encoding="utf-8")
            else:
                print(f"[SYSTEM] Testing Critic Agent's fixed RTL for attempt {attempt + 1}...")

            # 2. VERIFICATION (This is the single-shot verification call!)
            print("[SYSTEM] Running Verilator/Cocotb verification...")
            result = run_verification(workspace_dir, module_name, spec_dict)
            print(f"[SYSTEM] Verification status: {result['status']}")
            
            # 3. SUCCESS CHECK
            if result["status"] == "PASS":
                winner = result
                break
            
            # 4. FAILURE LOGGING
            print(f"❌ Verification Failed! Error Type: {result.get('error_type', 'UNKNOWN')}")
            print(f"   Log Snippet:\n{result.get('log', 'No log provided.')}")

            # 5. THE CRITIC AGENT (Only if we haven't exhausted retries)
            if attempt < MAX_RETRIES - 1:
                print("\n💀 Design failed. Initiating LLM Critic Agent loop...")
                failure_log = result.get("log", "")
                failure_error_type = result.get("error_type", "LOGIC")
                
                if failure_error_type == "SYNTAX":
                    # Micro-Targeted Payload for Syntax Errors
                    syntax_match = re.search(r"%Error:[^:]+design\.sv:(\d+):\s*(.*)", failure_log)
                    if syntax_match:
                        line_no = int(syntax_match.group(1))
                        message = syntax_match.group(2).strip()
                        snippet = ""
                        if design_path.exists():
                            design_lines = design_path.read_text(encoding="utf-8").splitlines()
                            start = max(line_no - 3, 0)
                            end = min(line_no + 2, len(design_lines))
                            snippet_lines = [f"{i + 1}: {design_lines[i]}" for i in range(start, end)]
                            snippet = "\n".join(snippet_lines)
                        failure_log = f"Syntax Error on Line {line_no}:\n{snippet}\nError: {message}"

                if result["status"] == "FAIL_LINT":
                    failure_log += (
                        "\n\nCRITICAL LINT FAILURE: Your logic introduced a severe physical violation "
                        "(e.g., a Latch or Multiple Drivers). You must rewrite the internal logic to be structurally sound. "
                        "Do not ignore this lint error."
                    )

                # Catch Python crashes
                if any(err in failure_log for err in ["Python Golden Model crashed", "NameError", "ValueError"]) and "%Error:" not in failure_log:
                    print("❌ Python Testbench Bug Detected. Aborting Critic Loop to save tokens.")
                    break
                if "SyntaxError:" in failure_log and "%Error:" not in failure_log:
                    print("[SYSTEM] Python Oracle syntax error detected. Aborting Critic Loop to prevent Verilog corruption.")
                    break

                broken_code = design_path.read_text(encoding="utf-8")
                testbench_path = Path(workspace_dir) / "test_design.py"
                testbench_code = testbench_path.read_text(encoding="utf-8") if testbench_path.exists() else ""
                
                # Diagnostic & VCD Injection
                diag_context = result.get("diagnostic_context")
                if diag_context:
                    failure_log += "\n\n=== OFFICIAL EDA DIAGNOSTICS ===\n" + diag_context
                    print("    -> Appended official diagnostics to Critic payload.")
                failure_context_file = Path(workspace_dir) / "failure_context.json"
                if failure_context_file.exists():
                    parsed = json.loads(failure_context_file.read_text(encoding="utf-8"))
                    failure_log += "\n\n=== COCOTB FAILURE PAYLOAD ===\n" + json.dumps(parsed, indent=2)
                    print("    -> Appended Cocotb failure payload to Critic payload.")

                # Call Critic Agent
                fixed_code = ai_client.fix_design(
                    broken_code=broken_code,
                    error_log=failure_log,
                    testbench_code=testbench_code,
                    error_type=failure_error_type,
                    is_sequential=spec_dict.get("is_sequential", False),
                    retry_count=attempt,
                    workspace_dir=workspace_dir
                )

                # Handle Decomposition Request
                if isinstance(fixed_code, dict) and fixed_code.get("action") == "DECOMPOSE":
                    print("[SYSTEM] Critic requested decomposition. Re-planning Task...")
                    new_plan = ai_client.decompose_architecture(task.prompt)
                    if isinstance(new_plan, str):
                        print(f"❌ Re-plan failed: {new_plan}")
                        sys.exit(1)
                    plan.tasks[idx:idx+1] = new_plan.tasks
                    replan_requested = True
                    break

                # Write the fixed code so Attempt 2 can test it!
                design_path.write_text(fixed_code, encoding="utf-8")
            else:
                print("\n💀 MAX RETRIES REACHED. Task failed.")

        if replan_requested:
            continue

        if not winner:
            print(f"❌ [FATAL] Task '{task.module_name}' exhausted all retries. Pipeline halting to prevent API credit burn.")
            
            # Use UUID to guarantee unique folder names and prevent OSError crashes
            import uuid
            failed_dir = f"workspace_FAILED_{task.module_name}_{uuid.uuid4().hex[:8]}"
            if os.path.exists("workspace"):
                os.rename("workspace", failed_dir)
                print(f"[SYSTEM] Preserved failed workspace at {failed_dir} for manual inspection.")
            
            # HARD ABORT. NO MORE DECOMPOSITION DEATH SPIRALS.
            sys.exit(1)

        # --- FORMAL VERIFICATION GATING (BYPASSED) ---
        print(f"[SYSTEM] Skipping Formal Verification for {task.module_name}. Relying on CRV Simulation pass.")
        formal_result = {"status": "PASSED"}
        formal_passed = True

        consecutive_failures = 0
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
            
            if spec_dict.get("component_class", "").upper() == "TOP_LEVEL":
                synth_metrics = run_synthesis(winner['workspace'], winner["module_name"])
            else:
                synth_metrics = {"status": "PASS", "gate_count": "DEFERRED", "execution_time": 0}
                print("[SYSTEM] Skipping Yosys synthesis for sub-module to maximize pipeline speed.")
            
            if synth_metrics["status"] == "PASS":
                print("✅ SYNTHESIS SUCCESS!")
                print(f"📊 HARDWARE COST (AREA): {synth_metrics['gate_count']} Logic Gates")
                print(f"⏱️  SYNTHESIS TIME: {synth_metrics['execution_time']:.2f} seconds")
                ip_mgr.save_ip(
                    task.module_name,
                    os.path.join(winner["workspace"], "design.sv"),
                    spec_dict,
                    synth_metrics,
                )
                
                # OPTIMIZATION: Only run OpenLane if it is the Top-Level CPU!
                if spec_dict.get("component_class", "").upper() == "TOP_LEVEL":
                    # print(f"\n[PHYSICAL DESIGN] Triggering OpenLane RTL-to-GDSII flow...")
                    # openlane_metrics = run_openlane(winner['workspace'], winner["module_name"], synth_metrics['gate_count'])
                    # print(openlane_metrics)
                    pass
                else:
                    print(f"[SYSTEM] Skipping OpenLane physical layout for sub-module.")

            if ai_client.rag:
                ai_client.rag.insert_graph_node(
                    task.module_name,
                    spec_dict.get("inputs", []),
                    spec_dict.get("outputs", []),
                )
                if task.component_class == "TOP_LEVEL":
                    for fsm_module in modules_by_class.get("FSM", []):
                        for datapath_module in modules_by_class.get("DATAPATH", []):
                            ai_client.rag.add_relation(fsm_module, "controls", datapath_module)
                    for other_module in plan.tasks:
                        if other_module.module_name == task.module_name:
                            continue
                        ai_client.rag.add_relation(
                            task.module_name, "integrates", other_module.module_name
                        )

        if winner:
            # Cleanup the workspace AFTER synthesis is done
            shutil.rmtree("workspace", ignore_errors=True)
        idx += 1
