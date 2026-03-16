from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


def generate_sby_config(workspace_dir: Path, top_module: str) -> Path:
    """Create a SymbiYosys config that reads the design/formal properties."""
    sby_path = workspace_dir / "build.sby"
    sby_content = f"""[options]
mode prove
depth 15

[engines]
smtbmc

[script]
read -formal design.sv formal_properties.sv
prep -top {top_module}
"""
    sby_path.write_text(sby_content, encoding="utf-8")
    return sby_path


def _locate_vcd(workspace_dir: Path) -> Optional[Path]:
    """Return the first .vcd file SymbiYosys produced (if any)."""
    candidates = sorted(workspace_dir.glob("build/**/*.vcd"))
    if candidates:
        return candidates[0]
    candidates = sorted(workspace_dir.glob("**/*.vcd"))
    return candidates[0] if candidates else None


def run_formal_verification(workspace_dir: str, top_module: str) -> dict:
    """
    Execute SymbiYosys against the provided workspace.

    Parameters
    ----------
    workspace_dir:
        Path that contains design.sv, formal_properties.sv, and where the SBY
        run will be executed.
    top_module:
        Top-level module name passed to the `prep -top` stage.
    """
    workspace = Path(workspace_dir)
    if not workspace.is_dir():
        raise FileNotFoundError(f"Workspace not found: {workspace}")

    generate_sby_config(workspace, top_module)
    cmd = ["sby", "-f", "build.sby"]
    try:
        result = subprocess.run(
            cmd,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=60,
        )
        log = result.stdout + result.stderr
    except subprocess.TimeoutExpired as exc:
        print(f"[FORMAL] SymbiYosys timed out after 60s: {exc}")
        return {
            "status": "FAILED",
            "log": f"Formal Verification timed out due to state space explosion.\n{exc}",
            "counterexample_vcd": None,
            "returncode": None,
        }
    status = "UNKNOWN"
    if "Status: PASSED" in log:
        status = "PASSED"
    elif "Status: FAILED" in log:
        status = "FAILED"

    counterexample_vcd: Optional[Path] = None
    if status == "FAILED":
        counterexample_vcd = _locate_vcd(workspace)

    output = {
        "status": status,
        "log": log,
        "counterexample_vcd": str(counterexample_vcd) if counterexample_vcd else None,
        "returncode": result.returncode,
    }
    return output


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        raise SystemExit("Usage: python formal_verifier.py <workspace_dir> <top_module>")
    workspace_arg = sys.argv[1]
    module_arg = sys.argv[2]
    summary = run_formal_verification(workspace_arg, module_arg)
    print(f"Formal run status: {summary['status']}")
    if summary["counterexample_vcd"]:
        print(f"Counter-example VCD: {summary['counterexample_vcd']}")
