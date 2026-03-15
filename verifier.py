from __future__ import annotations

import os
import shutil
import subprocess
import re
import time
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader
from rag_agent import HardwareRAG
# ---------------------------------------------------------------------------
# Resolve the templates directory relative to this file so it works
# regardless of the caller's working directory.
# ---------------------------------------------------------------------------
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_ERROR_TAG_PATTERN = re.compile(r"%Error[-:]\s*([A-Z][A-Z0-9_]+)", re.IGNORECASE)
_DIAGNOSTIC_RAG: HardwareRAG | None = None
def generate_templates(spec_dict: dict, workspace_dir: Path):
    """Dynamically generates testbench, AXI wrappers, and C drivers."""
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)))
    mod_name = spec_dict.get("module_name", "design")

    # ---> NEW: ISOLATE THE PYTHON GOLDEN MODEL AND TEST GENERATOR <---
    # Extract both python functions from the Pydantic spec
    golden_code = spec_dict.get("golden_model_python", "def golden_model(state, inputs):\n    return state, {}")
    test_gen_code = spec_dict.get("test_vector_generator_python", "def generate_test_vectors():\n    return []")
    
    # Combine them into a single Python file so the testbench can import both
    combined_python = f"{golden_code}\n\n{test_gen_code}"
    
    golden_path = workspace_dir / "golden_model.py"
    golden_path.write_text(combined_python, encoding="utf-8")

    # 1. RENDER TESTBENCH
    tb_template = env.get_template("testbench.py.jinja")
    tb_rendered = tb_template.render(
        module_name=mod_name,
        inputs=spec_dict.get("inputs", []),
        outputs=spec_dict.get("outputs", []),
        test_vectors=spec_dict.get("test_vectors", []),
        is_sequential=spec_dict.get("is_sequential", False)
        # Note: We deleted the golden_model_python injection here!
    )
    out_path = workspace_dir / "test_design.py"
    out_path.write_text(tb_rendered, encoding="utf-8")
    
    # 2. RENDER AXI4-LITE WRAPPER (For FPGA Deployment)
    axi_template = env.get_template("axi4_lite_wrapper.sv.jinja")
    axi_rendered = axi_template.render(
        module_name=mod_name,
        inputs=spec_dict.get("inputs", []),
        outputs=spec_dict.get("outputs", []),
        is_sequential=spec_dict.get("is_sequential", False)
    )
    axi_path = workspace_dir / f"{mod_name}_axi.sv"
    axi_path.write_text(axi_rendered, encoding="utf-8")

    # 3. RENDER BARE-METAL C FIRMWARE DRIVER
    c_template_path = _TEMPLATES_DIR / "c_driver.h.jinja"
    if c_template_path.exists():
        c_template = env.get_template("c_driver.h.jinja")
        c_rendered = c_template.render(
            module_name=mod_name,
            inputs=spec_dict.get("inputs", []),
            outputs=spec_dict.get("outputs", [])
        )
        c_path = workspace_dir / f"{mod_name}_driver.h"
        c_path.write_text(c_rendered, encoding="utf-8")
    
    return out_path


def _extract_verilator_error_tags(log: str) -> List[str]:
    """Return unique Verilator error tags (e.g., PROCASSWIRE) from the log."""
    tags = {_match.group(1).upper() for _match in _ERROR_TAG_PATTERN.finditer(log)}
    return sorted(tags)


def _diagnostic_rag_client() -> HardwareRAG | None:
    """Lazily initialise the eda_diagnostics collection."""
    global _DIAGNOSTIC_RAG
    if _DIAGNOSTIC_RAG is None:
        try:
            _DIAGNOSTIC_RAG = HardwareRAG(collections=["eda_diagnostics"])
        except Exception as exc:
            print(f"[RAG] ⚠️  Unable to open eda_diagnostics collection: {exc}")
            return None
    return _DIAGNOSTIC_RAG


def _build_diagnostic_context(tags: List[str]) -> str:
    """Retrieve vector-context for each tag from the eda_diagnostics collection."""
    rag = _diagnostic_rag_client()
    if rag is None or not tags:
        return ""

    contexts: List[str] = []
    for tag in tags:
        try:
            ctx = rag.retrieve_context(tag, n_results=3, collection_name="eda_diagnostics")
        except Exception as exc:
            print(f"[RAG] ⚠️  Diagnostic retrieval failed for '{tag}': {exc}")
            continue
        if ctx.strip():
            contexts.append(f"--- Diagnostic for {tag} ---\n{ctx.strip()}")
    return "\n\n".join(contexts)

def run_verification(workspace_dir: str, fallback_module_name: str,
                     spec_dict: dict | None = None) -> dict:
    """Run Verilator/cocotb verification inside *workspace_dir*.
    Parameters
    ----------
    workspace_dir : str
        Path to the worker's run directory (e.g. "workspace/run_0").
    fallback_module_name : str
        Module name to use if auto-detection from design.sv fails.
    spec_dict : dict, optional
        If provided, ``generate_testbench`` is called to render a fresh
        test file from the Jinja2 template before running ``make``.
    """
    target_path = Path(workspace_dir)
    # ----- AUTO-DETECT MODULE NAME VIA REGEX -----
    verilog_file = target_path / "design.sv"
    actual_name = fallback_module_name
    if verilog_file.exists():
        with open(verilog_file, "r", encoding="utf-8") as f:
            verilog_content = f.read()
            match = re.search(r"module\s+([a-zA-Z0-9_]+)", f.read())
            if match:
                actual_name = match.group(1)

        # ----- VCD INJECTION HACK: Force Verilator to dump waves -----
        # We append a non-synthesizable block to the end of the module
        # so Verilator physically writes the dump.vcd file for the Slicer.
        if "dump.vcd" not in verilog_content:
            # Find the last 'endmodule'
            last_endmodule_idx = verilog_content.rfind("endmodule")
            if last_endmodule_idx != -1:
                vcd_injection = f"""
    `ifndef SYNTHESIS
    initial begin
        $dumpfile("sim_build/dump.vcd");
        $dumpvars(0, {actual_name});
    end
    `endif
"""
                # Insert the injection right before 'endmodule'
                new_verilog = verilog_content[:last_endmodule_idx] + vcd_injection + verilog_content[last_endmodule_idx:]
                
                with open(verilog_file, "w", encoding="utf-8") as f:
                    f.write(new_verilog)
            else:
                print(f"⚠️ [VCD INJECTION FAILED] Could not find 'endmodule' in {verilog_file}")

    # ----- GENERATE TESTBENCH FROM JINJA2 TEMPLATE -----
    if spec_dict is not None:
        # Ensure the spec knows the real module name
        spec_dict.setdefault("module_name", actual_name)
        generate_templates(spec_dict, target_path)
    else:
        # Legacy fallback: copy the old static test file if it exists
        static_tb = _TEMPLATES_DIR / "test_alu.py"
        if static_tb.exists():
            shutil.copy(static_tb, target_path / "test_alu.py")
    # Copy the Makefile template
    shutil.copy(_TEMPLATES_DIR / "Makefile", target_path / "Makefile")
    # ----- CLEAR VERILATOR BUILD CACHE -----
    sim_build = target_path / "sim_build"
    if sim_build.exists():
        shutil.rmtree(sim_build)
    start_time = time.time()
    # ----- RUN MAKE -----
    result = subprocess.run(
        ["make", f"TOPLEVEL={actual_name}"],
        cwd=target_path,
        capture_output=True,
        text=True,
    )
    execution_time = time.time() - start_time
    log_output = result.stdout + result.stderr
    # ----- FOCUS THE LOG -----
    lines = log_output.splitlines()
    error_lines = [
        l for l in lines
        if any(kw in l.lower() for kw in
               ["error", "assert", "fail", "mismatch", "expected"])
    ]
    if error_lines:
        focused_log = (
            "[...KEY ERRORS EXTRACTED...]\n"
            + "\n".join(error_lines[-30:])
            + "\n\n[...LAST 20 LINES...]\n"
            + "\n".join(lines[-20:])
        )
        log_output = focused_log
    elif len(lines) > 50:
        log_output = "[...TRUNCATED LOG...]\n" + "\n".join(lines[-50:])
    
    # ----- DETERMINE STATUS -----
    status = (
        "PASS"
        if "PASS=1" in log_output and result.returncode == 0
        else "FAIL"
    )

    # ----- VCD TEMPORAL SLICER (WHITE-BOX DEBUGGING) -----
    vcd_data_for_test = None
    if status == "FAIL":
        timestamp_ns = None
        
        # 1. Try to find standard AssertionError format (e.g., "... at time 123 ns")
        time_match = re.search(r"at time (\d+(?:\.\d+)?)\s*ns", log_output)
        if time_match:
            timestamp_ns = float(time_match.group(1))
        else:
            # 2. Fallback: Try to find Cocotb 2.0 log prefix format (e.g., "1.00ns WARNING")
            for line in log_output.splitlines():
                if "CRV FAIL" in line or "AssertionError" in line:
                    prefix_match = re.search(r"^\s*(\d+(?:\.\d+)?)\s*ns", line)
                    if prefix_match:
                        timestamp_ns = float(prefix_match.group(1))
                        break
        
        # 3. If we found the exact nanosecond of the crash, slice the VCD!
        if timestamp_ns is not None:
            # Cocotb/Verilator usually dumps to sim_build/dump.vcd
            vcd_path = target_path / "sim_build" / "dump.vcd" 
            
            if vcd_path.exists():
                try:
                    from vcd_snapshot import snapshot_signal_states
                    import json
                    
                    # Extract the binary states of all signals at the crash timestamp
                    snapshot = snapshot_signal_states(vcd_path, timestamp_ns)
                    vcd_json_str = json.dumps(snapshot, indent=2)
                    
                    # Append the JSON to the log so the Critic Agent can read it
                    log_output += f"\n\n[...VCD SNAPSHOT AT {timestamp_ns}ns...]\n{vcd_json_str}"
                    vcd_data_for_test = snapshot
                    
                except Exception as e:
                    log_output += f"\n\n[VCD Slicer Failed: {e}]"
            else:
                log_output += f"\n\n[VCD Slicer Skipped: dump.vcd not found at {vcd_path}]"

    # ----- DIAGNOSTIC CONTEXT FOR CRITIC AGENT -----
    error_tags = _extract_verilator_error_tags(log_output)
    diagnostic_context = ""
    if status == "FAIL" and error_tags:
        diagnostic_context = _build_diagnostic_context(error_tags)

    # ----- RETURN RESULTS -----
    return {
        "workspace": workspace_dir,
        "status": status,
        "execution_time": execution_time,
        "module_name": actual_name,
        "log": log_output,
        "vcd_snapshot": vcd_data_for_test,  # <--- Added for test_vcd.py to verify
        "error_tags": error_tags,
        "diagnostic_context": diagnostic_context or None,
    }
