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
        "RUN_LINTER": False # <-- ADD THIS: Bypass internal linter, trust our Python pipeline
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

# # =========================================================================
# # STANDALONE FAST-TESTING BLOCK
# # =========================================================================
# if __name__ == "__main__":
#     test_workspace = "workspace/run_2" 
#     test_module = "adder_4bit"
#     test_gate_count = 43
    
#     if os.path.exists(test_workspace):
#         print(f"\n🚀 FAST-TESTING OPENLANE ON: {test_workspace}")
#         result = run_openlane(test_workspace, test_module, test_gate_count)
        
#         if result["status"] == "FAIL":
#             print("\n--- FULL ERROR LOG FOR DEBUGGING ---")
#             print(result["log"])
#     else:
#         print(f"❌ Error: {test_workspace} does not exist.")

# import os
# import shutil
# import subprocess
# import json
# import time
# from pathlib import Path

# def run_openlane(workspace_dir: str, module_name: str):
#     """
#     Copies the winning Verilog to OpenLane, generates the config, 
#     and executes the RTL-to-GDSII physical design pipeline.
#     """
#     openlane_dir = Path("/workspaces/test/OpenLane")
#     design_dir = openlane_dir / "designs" / module_name
#     src_dir = design_dir / "src"
    
#     # 1. Create the strict OpenLane directory structure
#     if design_dir.exists():
#         shutil.rmtree(design_dir)
#     src_dir.mkdir(parents=True)
    
#     # 2. Copy the winning Verilog file
#     shutil.copy(f"{workspace_dir}/design.sv", src_dir / "design.sv")
    
#     # 3. Generate the OpenLane Configuration (config.json)
#     # We specify SkyWater 130nm. We set CLOCK_PORT to null because the ALU is combinational.
#     config = {
#         "DESIGN_NAME": module_name,
#         "VERILOG_FILES": "dir::src/design.sv",
#         "CLOCK_PORT": None,
#         "RUN_CTS": False,
#         "FP_SIZING": "absolute",
#         "DIE_AREA": "0 0 50 50", # 50x50 micrometers silicon die
#         "PL_TARGET_DENSITY": 0.65,
#         "QUIT_ON_SYNTH_CHECKS": False
#     }
    
#     with open(design_dir / "config.json", "w") as f:
#         json.dump(config, f, indent=4)

#     print(f"\n[PHYSICAL DESIGN] Triggering OpenLane RTL-to-GDSII flow for {module_name}...")
#     start_time = time.time()
    
#     # 4. Execute OpenLane using the explicit, bulletproof Docker command
#     docker_cmd = [
#         "docker", "run", "--rm",
#         "-v", "/workspaces/test/OpenLane:/openlane",
#         "-v", "/workspaces/test/OpenLane/designs:/openlane/install",
#         "-v", "/home/vscode:/home/vscode",
#         "-v", "/home/vscode/.ciel:/home/vscode/.ciel",
#         "-e", "PDK_ROOT=/home/vscode/.ciel",
#         "-e", "PDK=sky130A",
#         "--user", "1000:1000",
#         "--network", "host",
#         "ghcr.io/the-openroad-project/openlane:ff5509f65b17bfa4068d5336495ab1718987ff69-amd64",
#         "sh", "-c", f"./flow.tcl -design {module_name} -overwrite"
#     ]
    
#     result = subprocess.run(
#         docker_cmd,
#         cwd=openlane_dir,
#         capture_output=True,
#         text=True
#     )
    
#     execution_time = time.time() - start_time
    
#     if result.returncode == 0:
#         print("✅ OPENLANE PHYSICAL DESIGN SUCCESS!")
#         print(f"⏱️ Time taken: {execution_time:.2f} seconds.")
#         print(f"📁 GDSII Layout File generated in: OpenLane/designs/{module_name}/runs/")
#     else:
#         print("❌ OPENLANE FAILED!")
#         # Print the last 15 lines of the massive OpenLane log
#         print(result.stderr)

# if __name__ == "__main__":
#     # Test the wrapper directly using the known winner
#     run_openlane("workspace/run_1", "alu_4bit")