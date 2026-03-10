import os
import shutil
import subprocess
import json
import time
from pathlib import Path

def run_openlane(workspace_dir: str, module_name: str):
    """
    Copies the winning Verilog to OpenLane, generates the config, 
    and executes the RTL-to-GDSII physical design pipeline.
    """
    openlane_dir = Path("/workspaces/test/OpenLane")
    design_dir = openlane_dir / "designs" / module_name
    src_dir = design_dir / "src"
    
    # 1. Create the strict OpenLane directory structure
    if design_dir.exists():
        shutil.rmtree(design_dir)
    src_dir.mkdir(parents=True)
    
    # 2. Copy the winning Verilog file
    shutil.copy(f"{workspace_dir}/design.sv", src_dir / "design.sv")
    
    # 3. Generate the OpenLane Configuration (config.json)
    # We specify SkyWater 130nm. We set CLOCK_PORT to null because the ALU is combinational.
    config = {
        "DESIGN_NAME": module_name,
        "VERILOG_FILES": "dir::src/design.sv",
        "CLOCK_PORT": None,
        "RUN_CTS": False,
        "FP_SIZING": "absolute",
        "DIE_AREA": "0 0 50 50", # 50x50 micrometers silicon die
        "PL_TARGET_DENSITY": 0.65,
        "QUIT_ON_SYNTH_CHECKS": False
    }
    
    with open(design_dir / "config.json", "w") as f:
        json.dump(config, f, indent=4)

    print(f"\n[PHYSICAL DESIGN] Triggering OpenLane RTL-to-GDSII flow for {module_name}...")
    start_time = time.time()
    
    # 4. Execute OpenLane using the explicit, bulletproof Docker command
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", "/workspaces/test/OpenLane:/openlane",
        "-v", "/workspaces/test/OpenLane/designs:/openlane/install",
        "-v", "/home/vscode:/home/vscode",
        "-v", "/home/vscode/.ciel:/home/vscode/.ciel",
        "-e", "PDK_ROOT=/home/vscode/.ciel",
        "-e", "PDK=sky130A",
        "--user", "1000:1000",
        "--network", "host",
        "ghcr.io/the-openroad-project/openlane:ff5509f65b17bfa4068d5336495ab1718987ff69-amd64",
        "sh", "-c", f"./flow.tcl -design {module_name} -overwrite"
    ]
    
    result = subprocess.run(
        docker_cmd,
        cwd=openlane_dir,
        capture_output=True,
        text=True
    )
    
    execution_time = time.time() - start_time

    # print(f"\n[PHYSICAL DESIGN] Triggering OpenLane RTL-to-GDSII flow for {module_name}...")
    # start_time = time.time()
    
    # # 4. Execute OpenLane via its Docker wrapper script
    # result = subprocess.run(
    #     ["./flow.tcl", "-design", module_name],
    #     cwd=openlane_dir,
    #     capture_output=True,
    #     text=True
    # )
    
    # execution_time = time.time() - start_time
    
    if result.returncode == 0:
        print("✅ OPENLANE PHYSICAL DESIGN SUCCESS!")
        print(f"⏱️ Time taken: {execution_time:.2f} seconds.")
        print(f"📁 GDSII Layout File generated in: OpenLane/designs/{module_name}/runs/")
    else:
        print("❌ OPENLANE FAILED!")
        # Print the last 15 lines of the massive OpenLane log
        print(result.stderr)
        # OLD: print("\n".join(result.stdout.splitlines()[-15:]))

if __name__ == "__main__":
    # Test the wrapper directly using the known winner
    run_openlane("workspace/run_1", "alu_4bit")