"""
quartus_wrapper.py
==================
Headless FPGA compilation driver for the EDA pipeline.

Wraps Quartus Prime's ``quartus_sh --flow compile`` command, dynamically
writes the required .qsf project file, and parses the build artefacts to
return a structured result dictionary back to the pipeline orchestrator.
"""

import subprocess
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Quartus installation path
# ---------------------------------------------------------------------------
QUARTUS_SH_PATH = r"C:\altera\13.0sp1\quartus\bin64\quartus_sh.exe"

# How many lines to capture from the tail of the error log on failure
_ERROR_TAIL_LINES = 40

def _write_project_files(build_dir: Path, top_module: str):
    """Dynamically generate both the .qsf and .qpf files required by older Quartus versions."""
    
    # 1. Write the Settings File (.qsf)
    qsf_content = (
        f'set_global_assignment -name FAMILY "Cyclone V"\n'
        f"set_global_assignment -name DEVICE 5CSEMA5F31C6\n"
        f"set_global_assignment -name TOP_LEVEL_ENTITY {top_module}\n"
        f"set_global_assignment -name SYSTEMVERILOG_FILE ../design.sv\n"
        f"set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files\n"
    )
    qsf_path = build_dir / f"{top_module}.qsf"
    qsf_path.write_text(qsf_content, encoding="utf-8")
    print(f"  [Quartus] Wrote QSF → {qsf_path}")

    # 2. Write the Project File (.qpf) to prevent Error 132005 in v13.0
    qpf_content = (
        f'QUARTUS_VERSION = "13.0"\n'
        f'PROJECT_REVISION = "{top_module}"\n'
    )
    qpf_path = build_dir / f"{top_module}.qpf"
    qpf_path.write_text(qpf_content, encoding="utf-8")
    print(f"  [Quartus] Wrote QPF → {qpf_path}")


def _tail(text: str, n: int = _ERROR_TAIL_LINES) -> str:
    """Return the last *n* non-empty lines of *text*."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[-n:])


def run_fpga_compilation(workspace_dir: str, top_module: str) -> dict:
    """Run a headless Quartus Prime compilation for a single design.

    Workflow
    --------
    1. Create ``<workspace_dir>/quartus_build/``.
    2. Write ``{top_module}.qsf`` referencing ``../design.sv``.
    3. Execute ``quartus_sh --flow compile {top_module}`` inside the build dir.
    4. Check for a generated ``.sof`` artefact in ``output_files/``.
    5. Return a structured result dictionary.

    Parameters
    ----------
    workspace_dir:
        Path to the isolated EDA workspace that contains ``design.sv``.
        Corresponds to one of the ``run_<N>`` directories created by
        :func:`llm_client.setup_workspaces`.
    top_module:
        The top-level entity name.  Must match the ``module`` declaration
        inside ``design.sv``.

    Returns
    -------
    dict
        On **success**::

            {
                "status":        "success",
                "sof_path":      "/abs/path/to/output_files/foo.sof",
                "execution_time": 42.7,          # seconds (float)
                "stdout":        "...",
                "stderr":        "...",
            }

        On **failure**::

            {
                "status":        "failure",
                "error_tail":    "last 40 lines of combined output",
                "execution_time": 17.3,
                "stdout":        "...",
                "stderr":        "...",
            }
    """
    workspace_path = Path(workspace_dir).resolve()
    design_sv = workspace_path / "design.sv"

    # ------------------------------------------------------------------ #
    # Pre-flight checks                                                    #
    # ------------------------------------------------------------------ #
    if not Path(QUARTUS_SH_PATH).is_file():
        return {
            "status": "failure",
            "error_tail": (
                f"quartus_sh binary not found at:\n  {QUARTUS_SH_PATH}\n"
                "Check QUARTUS_SH_PATH in quartus_wrapper.py."
            ),
            "execution_time": 0.0,
            "stdout": "",
            "stderr": "",
        }

    if not design_sv.is_file():
        return {
            "status": "failure",
            "error_tail": f"design.sv not found in workspace:\n  {workspace_path}",
            "execution_time": 0.0,
            "stdout": "",
            "stderr": "",
        }

    # ------------------------------------------------------------------ #
    # Prepare build directory and project file                             #
    # ------------------------------------------------------------------ #
    build_dir = workspace_path / "quartus_build"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # SAFETY PATCH: Pre-create Quartus database folders to prevent permission crashes
    (build_dir / "db").mkdir(exist_ok=True)
    (build_dir / "incremental_db").mkdir(exist_ok=True)
    
    _write_project_files(build_dir, top_module)

    # ------------------------------------------------------------------ #
    # Execute Quartus compilation                                          #
    # ------------------------------------------------------------------ #
    cmd = [QUARTUS_SH_PATH, "--flow", "compile", top_module]
    print(f"  [Quartus] Running: {' '.join(cmd)}")
    print(f"  [Quartus] CWD:     {build_dir}")

    t_start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(build_dir),
            capture_output=True,
            text=True,
            # No timeout — large designs can take many minutes.
        )
    except FileNotFoundError:
        # quartus_sh wasn't accessible even after the pre-flight check
        # (e.g. a path with spaces that subprocess couldn't resolve).
        elapsed = time.monotonic() - t_start
        return {
            "status": "failure",
            "error_tail": (
                f"OS could not launch quartus_sh.\n"
                f"Tried path: {QUARTUS_SH_PATH}"
            ),
            "execution_time": round(elapsed, 2),
            "stdout": "",
            "stderr": "",
        }

    elapsed = round(time.monotonic() - t_start, 2)
    combined_output = result.stdout + result.stderr
    
    # ------------------------------------------------------------------ #
    # Artefact detection — look recursively for .map.rpt                 #
    # ------------------------------------------------------------------ #
    # rglob searches build_dir and all subdirectories (like output_files)
    map_files = list(build_dir.rglob("*.map.rpt"))

    if map_files:
        map_path = map_files[0]
        
        # Safely check if a .sof file was generated (Web Edition might skip it)
        sof_files = list(build_dir.rglob("*.sof"))
        sof_path = str(sof_files[0]) if len(sof_files) > 0 else "Skipped by Web Edition"
        
        print(f"  [Quartus] ✅ SUCCESS — Synthesis Complete! ({elapsed}s)")
        return {
            "status": "success",
            "map_path": str(map_path),
            "sof_path": sof_path,
            "execution_time": elapsed,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    else:
        # ------------------------------------------------------------------ #
        # No .map.rpt found — compilation failed                             #
        # ------------------------------------------------------------------ #
        error_tail = _tail(combined_output)
        print(f"  [Quartus] ❌ FAILURE — no .map.rpt generated  ({elapsed}s)")
        print(f"  [Quartus] Error tail:\n{error_tail}")
        return {
            "status": "failure",
            "error_tail": error_tail,
            "execution_time": elapsed,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python quartus_wrapper.py <workspace_dir> <top_module>")
        print("Example: python quartus_wrapper.py workspace/run_0 alu_4bit")
        sys.exit(1)

    ws_dir, top = sys.argv[1], sys.argv[2]
    print(f"\n[SYSTEM] Starting Quartus compilation")
    print(f"         Workspace : {ws_dir}")
    print(f"         Top module: {top}\n")

    outcome = run_fpga_compilation(ws_dir, top)

    print("\n--- Result ---")
    for k, v in outcome.items():
        if k in ("stdout", "stderr") and len(v) > 200:
            print(f"  {k}: <{len(v)} chars — truncated>")
        else:
            print(f"  {k}: {v}")
