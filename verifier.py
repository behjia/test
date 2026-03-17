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

_COMPONENT_CLASS_JINJA_ROUTES = {
    "FSM": "FSM_Assertions.jinja",
    "DATAPATH": "Math_Equivalence.jinja",
    "TOP_LEVEL": "cpu_integration_test.py.jinja",
}

def _testbench_template_name(component_class: str | None) -> str:
    if not component_class:
        return "testbench.py.jinja"
    return _COMPONENT_CLASS_JINJA_ROUTES.get(component_class.upper(), "testbench.py.jinja")

_ERROR_TAG_PATTERN = re.compile(r"%Error[-:]\s*([A-Z][A-Z0-9_]+)", re.IGNORECASE)
_DIAGNOSTIC_RAG: HardwareRAG | None = None
def generate_templates(spec_dict: dict, workspace_dir: Path):
    """Dynamically generates testbench, AXI wrappers, and C drivers."""
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)))
    mod_name = spec_dict.get("module_name", "design")
    component_class = spec_dict.get("component_class")

    def _ensure_body(body: str, fallback: str) -> str:
        cleaned = body.strip()
        if not cleaned:
            cleaned = fallback.strip()
        normalized = []
        for line in cleaned.splitlines():
            if not line.strip():
                normalized.append("")
                continue
            normalized.append(line if line.startswith("    ") else f"    {line}")
        return "\n".join(normalized)

    test_body = spec_dict.get("test_vector_body")
    golden_body = spec_dict.get("golden_model_body")

    if test_body and golden_body:
        normalized_test = _ensure_body(
            test_body, "    test_vectors = []\n    return test_vectors"
        )
        normalized_golden = _ensure_body(
            golden_body,
            "    expected_output = {}\n    return model_state, expected_output",
        )
        final_python_code = f"""
import random
import math
# Add any other required standard libraries here

def generate_test_vectors():
{normalized_test}

def golden_model(model_state, inputs):
{normalized_golden}
"""
    else:
        final_python_code = spec_dict.get(
            "golden_model_python",
            "def golden_model(state, inputs):\n    return state, {}\n",
        )

    golden_path = workspace_dir / "golden_model.py"
    golden_path.write_text(final_python_code, encoding="utf-8")

    # 1. RENDER TESTBENCH
    tb_template_name = _testbench_template_name(component_class)
    print(f"[DEBUG] Using testbench template: {tb_template_name} for class {component_class}")
    tb_template = env.get_template(tb_template_name)
    tb_rendered = tb_template.render(
        module_name=mod_name,
        inputs=spec_dict.get("inputs", []),
        outputs=spec_dict.get("outputs", []),
        component_class=component_class,
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


def _ensure_trailing_double_newline(design_path: Path) -> None:
    if not design_path.exists():
        return
    content = design_path.read_text(encoding="utf-8")
    if not content.endswith("\n\n"):
        content = content.rstrip("\n") + "\n\n"
        design_path.write_text(content, encoding="utf-8")

def run_verification(workspace_dir: str, fallback_module_name: str, spec_dict: dict | None = None) -> dict:
    target_path = Path(workspace_dir)
    design_file = target_path / "design.sv"
    actual_name = spec_dict.get("module_name", fallback_module_name) if spec_dict else fallback_module_name

    # ---------------------------------------------------------
    # 1. CLEAN AND WRAP THE RAW LOGIC (ONCE!)
    # ---------------------------------------------------------
    if design_file.exists() and spec_dict:
        raw_logic = design_file.read_text(encoding="utf-8")
        
        # Scrubber: extract internal logic if already wrapped (from a Critic retry)
        if "// --- AI GENERATED INTERNAL LOGIC ---" in raw_logic:
            parts = raw_logic.split("// --- AI GENERATED INTERNAL LOGIC ---")
            if len(parts) > 1:
                raw_logic = parts[1].split("// -----------------------------------")[0]
        
        raw_logic = raw_logic.replace("initial begin", "// KILLED INITIAL").replace("`ifndef SYNTHESIS", "// KILLED MACRO")

        import jinja2
        env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))
        template = env.get_template("hardware_wrapper.sv.jinja")
        
        wrapped_code = template.render(
            module_name=actual_name,
            inputs=spec_dict.get("inputs", []),
            outputs=spec_dict.get("outputs", []),
            internal_logic=raw_logic.strip()
        )
        
        # VCD Hack: Inject wave dumping safely before the endmodule
        vcd_injection = f"""
`ifndef SYNTHESIS
initial begin
    $dumpfile("sim_build/dump.vcd");
    $dumpvars(0, {actual_name});
end
`endif
"""
        wrapped_code = wrapped_code.replace("endmodule", vcd_injection + "\nendmodule")
        design_file.write_text(wrapped_code, encoding="utf-8")

    # ---------------------------------------------------------
    # 2. PRE-FLIGHT LINTER
    # ---------------------------------------------------------
    _ensure_trailing_double_newline(design_file)
    lint_cmd = [
        "verilator", "--lint-only", "-Wall", 
        "-Werror-LATCH", "-Werror-MULTIDRIVEN", 
        "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL", "-Wno-EOFNEWLINE", "-Wno-BADVLTPRAGMA",
        "-DSYNTHESIS", "-sv", "design.sv"
    ]
    lint_result = subprocess.run(lint_cmd, cwd=target_path, capture_output=True, text=True)
    if lint_result.returncode != 0:
        return {
            "workspace": workspace_dir,
            "status": "FAIL_LINT",
            "execution_time": 0.0,
            "log": "[PRE-FLIGHT LINT ERROR]\n" + lint_result.stderr,
            "vcd_snapshot": None,
            "error_tags": [],
            "diagnostic_context": None,
            "error_type": "PHYSICAL",
        }

    # ---------------------------------------------------------
    # 3. SETUP TESTBENCH & IP LIBRARY
    # ---------------------------------------------------------
    if spec_dict is not None:
        spec_dict.setdefault("module_name", actual_name)
        generate_templates(spec_dict, target_path)
    else:
        static_tb = _TEMPLATES_DIR / "test_alu.py"
        if static_tb.exists():
            shutil.copy(static_tb, target_path / "test_alu.py")
            
    shutil.copy(_TEMPLATES_DIR / "Makefile", target_path / "Makefile")
    
    ip_library = Path("ip_library")
    if ip_library.exists():
        for sv_file in ip_library.glob("*.sv"):
            shutil.copy(sv_file, target_path / sv_file.name)

    # 4. RUN COCOTB SIMULATION
    # ---------------------------------------------------------
    sim_build = target_path / "sim_build"
    if sim_build.exists():
        shutil.rmtree(sim_build)
        
    start_time = time.time()
    
    # Secure Verilog Sources using ABSOLUTE paths so Make can find them
    ip_files = [str((target_path / f.name).resolve()) for f in target_path.glob("*.sv") if f.name != "design.sv"]
    verilog_sources = f"{str((target_path / 'design.sv').resolve())}" + ((" " + " ".join(ip_files)) if ip_files else "")
    
    result = subprocess.run(
        ["make", f"TOPLEVEL={actual_name}", f"VERILOG_SOURCES={verilog_sources}"],
        cwd=target_path, capture_output=True, text=True
    )
    
    execution_time = time.time() - start_time
    
    # ---------------------------------------------------------
    # 5. LOG DISTILLATION
    # ---------------------------------------------------------
    raw_log = result.stdout + result.stderr
    lines = raw_log.splitlines()
    distilled_entries = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("%Error:") or line.startswith("%Warning:"):
            distilled_entries.append(line)
        if "AssertionError:" in line or "FAILED" in line:
            distilled_entries.append(line)
            for j in range(1, 4):
                if i + j < len(lines):
                    distilled_entries.append(lines[i + j])
            i += 3
        if "SyntaxError:" in line or "Traceback" in line:
            distilled_entries.append(line)
        i += 1

    assertion_snippet = []
    for idx, line in enumerate(lines):
        if "AssertionError" in line:
            assertion_snippet.append(line)
            for j in range(idx + 1, len(lines)):
                if lines[j].startswith("Hardware Output:") or lines[j].startswith("Golden Model Expected:"):
                    assertion_snippet.append(lines[j])
                elif lines[j].strip() == "":
                    break
            break

    if assertion_snippet:
        log_output = "\n".join(assertion_snippet)
    else:
        distilled_log = "\n".join(distilled_entries).strip()
        if not distilled_log:
            distilled_log = "\n".join(lines[-20:])
        log_output = distilled_log[:2000]
    
    status = (
        "PASS"
        # Check the raw_log, not the truncated log_output!
        if "PASS=1" in raw_log and result.returncode == 0
        else "FAIL"
    )

    # ---------------------------------------------------------
    # 6. VCD TEMPORAL SLICER & ERROR TAGS
    # ---------------------------------------------------------
    vcd_data_for_test = None
    if status == "FAIL":
        timestamp_ns = None
        time_match = re.search(r"at time (\d+(?:\.\d+)?)\s*ns", log_output)
        if time_match:
            timestamp_ns = float(time_match.group(1))
        else:
            for line in log_output.splitlines():
                if "CRV FAIL" in line or "AssertionError" in line:
                    prefix_match = re.search(r"^\s*(\d+(?:\.\d+)?)\s*ns", line)
                    if prefix_match:
                        timestamp_ns = float(prefix_match.group(1))
                        break
        
        if timestamp_ns is not None:
            vcd_path = target_path / "sim_build" / "dump.vcd" 
            if vcd_path.exists():
                try:
                    from vcd_snapshot import snapshot_signal_states
                    import json
                    snapshot = snapshot_signal_states(vcd_path, timestamp_ns)
                    vcd_json_str = json.dumps(snapshot, indent=2)
                    log_output += f"\n\n[...VCD SNAPSHOT AT {timestamp_ns}ns...]\n{vcd_json_str}"
                    vcd_data_for_test = snapshot
                except Exception as e:
                    log_output += f"\n\n[VCD Slicer Failed: {e}]"

    error_tags = _extract_verilator_error_tags(log_output)
    diagnostic_context = _build_diagnostic_context(error_tags) if (status == "FAIL" and error_tags) else None

    error_type_out = None if status == "PASS" else "LOGIC"
    return {
        "workspace": workspace_dir,
        "status": status,
        "execution_time": execution_time,
        "module_name": actual_name,
        "log": log_output,
        "vcd_snapshot": vcd_data_for_test,
        "error_tags": error_tags,
        "diagnostic_context": diagnostic_context,
        "error_type": error_type_out,
    }