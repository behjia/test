import requests
import json
import os

# 1. Update this to the winning folder from your last run (e.g., run_2)
WINNING_WORKSPACE = "workspace/run_2" 
MODULE_NAME = "sync_fifo_16x32"

# 2. Update with your active Ngrok URL
NGROK_URL = "https://unsegregable-uncorrelatedly-sheryl.ngrok-free.dev"

with open(os.path.join(WINNING_WORKSPACE, "design.sv"), "r", encoding="utf-8") as f:
    sv_code = f.read()

payload = {
    "module_name": MODULE_NAME,
    "systemverilog_code": sv_code
}

print("Sending payload to Windows...")
response = requests.post(f"{NGROK_URL}/compile", json=payload)
print(f"Status Code: {response.status_code}")

if response.status_code == 200:
    print("SUCCESS:\n")
    print(json.dumps(response.json(), indent=2))
else:
    print(response.text)