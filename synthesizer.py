import os
import subprocess
import re
import time
from pathlib import Path

def run_synthesis(workspace_dir: str, module_name: str) -> dict:
    """
    Dynamically generates a Yosys synthesis script, compiles the Verilog into 
    generic CMOS gates, and extracts the physical area (gate count).
    """
    target_path = Path(workspace_dir)
    verilog_file = "design.sv"
    script_file = target_path / "synth.ys"
    
    # 1. Dynamically write the Yosys Tcl script
    # We use 'abc -g cmos2' to map the design to basic CMOS logic gates (NAND, NOR, etc.)
    # This gives us a highly accurate Area metric without needing a massive 20GB PDK yet.
    ys_script = f"""
read_verilog -sv {verilog_file}
hierarchy -check -top {module_name}
proc; opt; fsm; opt; memory; opt
techmap; opt
abc -g cmos2
opt; clean
stat
"""
    with open(script_file, "w") as f:
        f.write(ys_script)
        
    print(f"[{target_path.name}] Triggering Yosys Logic Synthesis...")
    start_time = time.time()
    
    # 2. Execute Yosys in headless batch mode
    result = subprocess.run(
        ["yosys", "-s", "synth.ys"],
        cwd=target_path,
        capture_output=True,
        text=True
    )
    
    execution_time = time.time() - start_time
    log_output = result.stdout + result.stderr
    
    # 3. Regex Parsing for PPA Metrics
    # We are looking for the exact line in the Yosys log: "Number of cells:   <number>"
    gate_count = None
    match = re.search(r"Number of cells:\s+(\d+)", log_output)
    if match:
        gate_count = int(match.group(1))
        
    # Check for synthesis success
    status = "PASS" if result.returncode == 0 and gate_count is not None else "FAIL"

    return {
        "status": status,
        "execution_time": execution_time,
        "gate_count": gate_count,
        "log_snippet": log_output.splitlines()[-10:] if status == "FAIL" else []
    }

# Quick test block
if __name__ == "__main__":
    print("Testing synthesizer directly...")
    # Assuming run_1 was your winner from last time
    res = run_synthesis("workspace/run_1", "alu_4bit")
    print(res)