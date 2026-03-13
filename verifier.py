import os
import shutil
import subprocess
import re
import time
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
# ---------------------------------------------------------------------------
# Resolve the templates directory relative to this file so it works
# regardless of the caller's working directory.
# ---------------------------------------------------------------------------
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
def generate_testbench(spec_dict: dict, workspace_dir: Path) -> Path:
    """Render templates/testbench.py.jinja into *workspace_dir*/test_design.py.
    Parameters
    ----------
    spec_dict : dict
        Must contain at minimum:
            - module_name  : str
            - inputs       : list[dict]   – each dict has at least a "name" key
            - outputs      : list[dict]   – each dict has at least a "name" key
        Optionally:
            - test_vectors : list[tuple]  – each tuple is
              (input1_val, input2_val, …, expected)
    workspace_dir : Path
        The worker's run directory (e.g. workspace/run_0/).
    Returns
    -------
    Path
        The absolute path to the rendered test_design.py file.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        keep_trailing_newline=True,
    )
    template = env.get_template("testbench.py.jinja")
    # Pull the first output name for the assertion target.
    # Fall back to "result" if the spec doesn't list outputs.
    outputs = spec_dict.get("outputs", [])
    output_name = outputs[0]["name"] if outputs else "result"
    # --- SANITIZE THE GOLDEN MODEL ---
    golden = spec_dict.get("golden_model_python", "def golden_model(inputs):\n    return 0")
    if "```" in golden:
        match = re.search(r"```(?:python)?\s*(.*?)\s*```", golden, re.DOTALL | re.IGNORECASE)
        if match:
            golden = match.group(1)
        else:
            golden = golden.replace("```", "")
    
    # Ensure it's passed safely to Jinja
    outputs = spec_dict.get("outputs", [])
    output_name = outputs[0]["name"] if outputs else "result"
    
    rendered = template.render(
        module_name=spec_dict.get("module_name", "design"),
        inputs=spec_dict.get("inputs", []),
        output_name=output_name,
        test_vectors=spec_dict.get("test_vectors", []),
        is_sequential=spec_dict.get("is_sequential", False),
        golden_model_python=golden  # <--- PASS SANITIZED CODE HERE
    )

    workspace_dir = Path(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    out_path = workspace_dir / "test_design.py"
    out_path.write_text(rendered, encoding="utf-8")
    return out_path
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
            match = re.search(r"module\s+([a-zA-Z0-9_]+)", f.read())
            if match:
                actual_name = match.group(1)
    # ----- GENERATE TESTBENCH FROM JINJA2 TEMPLATE -----
    if spec_dict is not None:
        # Ensure the spec knows the real module name
        spec_dict.setdefault("module_name", actual_name)
        generate_testbench(spec_dict, target_path)
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
    status = (
        "PASS"
        if "PASS=1" in log_output and result.returncode == 0
        else "FAIL"
    )
    return {
        "workspace": workspace_dir,
        "status": status,
        "execution_time": execution_time,
        "module_name": actual_name,
        "log": log_output,
    }

# import os
# import shutil
# import subprocess
# import re
# import time
# from pathlib import Path

# def run_verification(workspace_dir: str, fallback_module_name: str) -> dict:
#     target_path = Path(workspace_dir)
    
#     # AUTO-DETECT MODULE NAME VIA REGEX
#     verilog_file = target_path / "design.sv"
#     actual_name = fallback_module_name
#     if verilog_file.exists():
#         with open(verilog_file, "r") as f:
#             match = re.search(r"module\s+([a-zA-Z0-9_]+)", f.read())
#             if match:
#                 actual_name = match.group(1)

#     shutil.copy("templates/Makefile", target_path / "Makefile")
#     shutil.copy("templates/test_alu.py", target_path / "test_alu.py")
    
#     start_time = time.time()
        
#     # Clear Verilator build cache to force fresh compilation
#     sim_build = target_path / "sim_build"
#     if sim_build.exists():
#         shutil.rmtree(sim_build)

#     # Pass the AUTO-DETECTED name to the Makefile
#     result = subprocess.run(
#         ["make", f"TOPLEVEL={actual_name}"],
#         cwd=target_path,
#         capture_output=True,
#         text=True
#     )
    
#     execution_time = time.time() - start_time
#     log_output = result.stdout + result.stderr

#     # After capturing log_output in verifier.py
#     lines = log_output.splitlines()

#     # Extract lines that actually describe failures
#     error_lines = [l for l in lines if any(kw in l.lower() for kw in 
#         ["error", "assert", "fail", "mismatch", "expected"])]

#     # Combine: meaningful errors first, then tail context
#     if error_lines:
#         focused_log = "[...KEY ERRORS EXTRACTED...]\n" + "\n".join(error_lines[-30:])
#         focused_log += "\n\n[...LAST 20 LINES...]\n" + "\n".join(lines[-20:])
#         log_output = focused_log
#     elif len(lines) > 50:
#         log_output = "[...TRUNCATED LOG...]\n" + "\n".join(lines[-50:])
    
#     status = "PASS" if "PASS=1" in log_output and result.returncode == 0 else "FAIL"
        
#     return {
#         "workspace": workspace_dir,
#         "status": status,
#         "execution_time": execution_time,
#         "module_name": actual_name, # Return the real name to the dispatcher!
#         "log": log_output 
#     }