import os
import shutil
import subprocess
from pathlib import Path
import time

def run_verification(workspace_dir: str, module_name: str) -> dict:
    """
    Copies templates to the isolated workspace, runs Verilator via Cocotb, 
    and parses the output for success or syntax errors.
    """
    target_path = Path(workspace_dir)
    
    # 1. Copy the testing templates into the isolated workspace
    shutil.copy("templates/Makefile", target_path / "Makefile")
    shutil.copy("templates/test_alu.py", target_path / "test_alu.py")
    
    print(f"[{target_path.name}] Triggering Verilator Compilation & Cocotb...")
    start_time = time.time()
    
    # 2. Execute the 'make' command in the hidden terminal
    # We pass TOPLEVEL dynamically so the Makefile knows the exact LLM module name
    result = subprocess.run(
        ["make", f"TOPLEVEL={module_name}"],
        cwd=target_path,
        capture_output=True,
        text=True
    )
    
    execution_time = time.time() - start_time
    log_output = result.stdout + result.stderr
    
    # 3. Parse the output to declare Pass/Fail
    # Cocotb prints "TESTS=1 PASS=1" on absolute success.
    if "PASS=1" in log_output and result.returncode == 0:
        status = "PASS"
    else:
        status = "FAIL"
        
    return {
        "workspace": workspace_dir,
        "status": status,
        "execution_time": execution_time,
        # We save the log in case the Critic Agent needs to read the syntax error later
        "log": log_output 
    }