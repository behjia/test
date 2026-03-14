import json
import time
import os
from pathlib import Path

LOG_FILE = Path("telemetry.jsonl")

def log_pipeline_run(module_name: str, spec_model: str, is_sequential: bool, 
                     winner_workspace: str, attempts: int, 
                     total_time: float, final_status: str):
    """Logs pipeline metrics to a JSON Lines file for PowerBI/Data Analysis."""
    data = {
        "timestamp": time.time(),
        "module_name": module_name,
        "spec_model": spec_model,
        "is_sequential": is_sequential,
        "winner_workspace": winner_workspace,
        "critic_attempts_needed": attempts,
        "total_time_seconds": round(total_time, 2),
        "final_status": final_status
    }
    
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(data) + "\n")
    print(f"📊 [TELEMETRY] Run logged to {LOG_FILE}")