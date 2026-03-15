import json
import os
from pathlib import Path
from verifier import run_verification

def test_vcd_slicer():
    print("🚀 Starting VCD Chaos Monkey Test...")
    
    workspace = "workspace/sabotage_test"
    
    # 1. Load the mock spec
    with open("mock_spec.json", "r") as f:
        spec_dict = json.load(f)
        
    # 2. Run the Verification (This WILL fail the Cocotb assertion)
    print("⏳ Running Verilator/Cocotb...")
    result = run_verification(
        workspace_dir=workspace, 
        fallback_module_name="alu",  # <--- ADD THIS PARAMETER
        spec_dict=spec_dict
    )
    
# 3. Analyze the Results
    print("\n================ TEST RESULTS ================")
    print(f"Status: {result['status']} (Expected: FAIL)")
    
    if result['status'] == "FAIL":
        print("\n🔍 1. Error Tags Extracted by verifier.py:")
        tags = result.get('error_tags', [])
        if tags:
            print(f"   {', '.join(tags)}")
        else:
            print("   ❌ ERROR: No tags found! The Regex failed to catch %Error:")

        print("\n🔍 2. Diagnostic RAG Context Injected:")
        diag_context = result.get('diagnostic_context')
        if diag_context:
            print("--------------------------------------------------")
            print(diag_context)
            print("--------------------------------------------------")
            print("✅ SUCCESS: The RAG Database successfully retrieved the manual for the Critic Agent!")
        else:
            print("❌ ERROR: Diagnostic context is empty. The RAG query failed.")
            print("\nRaw Log:")
            print(result['log'])
            
if __name__ == "__main__":
    test_vcd_slicer()