#V2:
import os
import shutil
import subprocess
import re
import time
from pathlib import Path

def run_verification(workspace_dir: str, fallback_module_name: str) -> dict:
    target_path = Path(workspace_dir)
    
    # AUTO-DETECT MODULE NAME VIA REGEX
    verilog_file = target_path / "design.sv"
    actual_name = fallback_module_name
    if verilog_file.exists():
        with open(verilog_file, "r") as f:
            match = re.search(r"module\s+([a-zA-Z0-9_]+)", f.read())
            if match:
                actual_name = match.group(1)

    shutil.copy("templates/Makefile", target_path / "Makefile")
    shutil.copy("templates/test_alu.py", target_path / "test_alu.py")
    
    start_time = time.time()
        
    # Clear Verilator build cache to force fresh compilation
    sim_build = target_path / "sim_build"
    if sim_build.exists():
        shutil.rmtree(sim_build)

    # Pass the AUTO-DETECTED name to the Makefile
    result = subprocess.run(
        ["make", f"TOPLEVEL={actual_name}"],
        cwd=target_path,
        capture_output=True,
        text=True
    )
    
    execution_time = time.time() - start_time
    log_output = result.stdout + result.stderr

    # After capturing log_output in verifier.py
    lines = log_output.splitlines()

    # Extract lines that actually describe failures
    error_lines = [l for l in lines if any(kw in l.lower() for kw in 
        ["error", "assert", "fail", "mismatch", "expected"])]

    # Combine: meaningful errors first, then tail context
    if error_lines:
        focused_log = "[...KEY ERRORS EXTRACTED...]\n" + "\n".join(error_lines[-30:])
        focused_log += "\n\n[...LAST 20 LINES...]\n" + "\n".join(lines[-20:])
        log_output = focused_log
    elif len(lines) > 50:
        log_output = "[...TRUNCATED LOG...]\n" + "\n".join(lines[-50:])
    
    status = "PASS" if "PASS=1" in log_output and result.returncode == 0 else "FAIL"
        
    return {
        "workspace": workspace_dir,
        "status": status,
        "execution_time": execution_time,
        "module_name": actual_name, # Return the real name to the dispatcher!
        "log": log_output 
    }
# import os
# import shutil
# import subprocess
# from pathlib import Path
# import time

# def run_verification(workspace_dir: str, module_name: str) -> dict:
#     """
#     Copies templates to the isolated workspace, runs Verilator via Cocotb, 
#     and parses the output for success or syntax errors.
#     """
#     target_path = Path(workspace_dir)
    
#     # 1. Copy the testing templates into the isolated workspace
#     shutil.copy("templates/Makefile", target_path / "Makefile")
#     shutil.copy("templates/test_alu.py", target_path / "test_alu.py")
    
#     print(f"[{target_path.name}] Triggering Verilator Compilation & Cocotb...")
#     start_time = time.time()
    
#     # 2. Execute the 'make' command in the hidden terminal
#     # We pass TOPLEVEL dynamically so the Makefile knows the exact LLM module name
#     result = subprocess.run(
#         ["make", f"TOPLEVEL={module_name}"],
#         cwd=target_path,
#         capture_output=True,
#         text=True
#     )
    
#     execution_time = time.time() - start_time
#     log_output = result.stdout + result.stderr
    
#     # 3. Parse the output to declare Pass/Fail
#     # Cocotb prints "TESTS=1 PASS=1" on absolute success.
#     if "PASS=1" in log_output and result.returncode == 0:
#         status = "PASS"
#     else:
#         status = "FAIL"
        
#     return {
#         "workspace": workspace_dir,
#         "status": status,
#         "execution_time": execution_time,
#         # We save the log in case the Critic Agent needs to read the syntax error later
#         "log": log_output 
#     }