import os
import subprocess
import json
import time
from pathlib import Path
import re

def run_openlane(workspace_dir: str, module_name: str, gate_count: int = 100) -> dict:
    target_path = Path(workspace_dir).resolve()
    
    # THE FIX: Point to the REAL OpenLane directory at the root of your repository
    repo_root = Path(__file__).resolve().parent
    openlane_dir = repo_root / "OpenLane"
    
    # We still want the output designs to go into the workspace folder, not the root
    project_dir = target_path / "openlane_runs"
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # -------------------------------------------------------------------------
    # SYNTHESIS SANITIZATION (The Fix)
    # -------------------------------------------------------------------------
    # OpenLane strict linting fails if it sees ANY timing constructs (like #1).
    # Even if the AI forgot the `ifndef SYNTHESIS, we strip them out via regex
    # before OpenLane touches the file.
    verilog_file = target_path / "design.sv"
    if verilog_file.exists():
        code = verilog_file.read_text(encoding="utf-8")
        # Remove any 'initial begin #1; end' or similar blocks
        clean_code = re.sub(r"initial\s+begin\s+#1;\s+end", "", code, flags=re.IGNORECASE)
        # Catch any stray standalone delays
        clean_code = re.sub(r"#\d+;", ";", clean_code)
        verilog_file.write_text(clean_code, encoding="utf-8")
    # -------------------------------------------------------------------------
    # 1. DYNAMIC SCALING LOGIC
    config = {
        "DESIGN_NAME": module_name,
        "VERILOG_FILES": ["/project/design.sv"],
        "PDK": "sky130A",
        "STD_CELL_LIBRARY": "sky130_fd_sc_hd",
        "CLOCK_PORT": None, 
        "CLOCK_NET": None,
        "RUN_CTS": False,   
        "DIODE_INSERTION_STRATEGY": 4,
        "RUN_LINTER": True
    }
    # If the design is tiny (like an ALU or Adder), force a massive 50x50 area
    # to guarantee the PDN router has enough room to draw power lines.
    if gate_count <= 200:
        utilization = "Fixed Area"
        config["FP_SIZING"] = "absolute"
        config["DIE_AREA"] = "0 0 50 50"
    else:
        # For large designs (Multipliers/SoCs), let OpenLane calculate it based on density
        utilization = 35 if gate_count > 500 else 45
        config["FP_SIZING"] = "relative"
        config["FP_CORE_UTIL"] = utilization
        config["PL_TARGET_DENSITY"] = (utilization / 100.0) + 0.05
    
    config_file = target_path / "config.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)
        
    print(f"[PHYSICAL DESIGN] Triggering OpenLane RTL-to-GDSII flow for {module_name}...")
    print(f"                  -> Dynamic Scaling: Gate Count={gate_count}, Utilization={utilization}%")
    
    start_time = time.time()
    
    try:
        # Define the exact path to the hidden PDK folder
        pdk_host_path = "/home/vscode/.ciel/ciel/sky130/versions/0fe599b2afb6708d281543108caf8310912f54af"
        
        docker_command = [
            "docker", "run", "--rm",
            # Mount the OpenLane scripts
            "-v", f"{openlane_dir}:/openlane",
            
            # Mount the REAL PDK directory into the container
            "-v", f"{pdk_host_path}:/openlane/pdks",
            
            # Mount the Verilog workspace
            "-v", f"{target_path}:/project",
            
            "-u", f"{os.getuid()}:{os.getgid()}",
            "-e", "PDK_ROOT=/openlane/pdks",
            "-e", "PWD=/openlane",  # <-- Inject the missing variable OpenLane is looking for
            "-w", "/openlane",
            
            "ghcr.io/the-openroad-project/openlane:ff5509f65b17bfa4068d5336495ab1718987ff69", 
            
            "./flow.tcl", "-design", "/project"
        ]
        
        result = subprocess.run(
            docker_command,
            cwd=str(target_path),
            capture_output=True,
            text=True
        )
    except Exception as e:
         return {"status": "FAIL", "log": str(e)}

    execution_time = time.time() - start_time
    log_output = result.stdout + result.stderr
    
    if "Flow complete" in log_output or "Routing completed" in log_output:
        status = "PASS"
        print("✅ OPENLANE PHYSICAL DESIGN SUCCESS!")
        print(f"⏱️ Time taken: {execution_time:.2f} seconds.")
    else:
        status = "FAIL"
        print("❌ OPENLANE FAILED!")
        print("\n".join(log_output.splitlines()[-20:]))

    return {
        "status": status,
        "execution_time": execution_time,
        "log": log_output
    }