import os
from llm_client import EDA_LLM_Client
from dotenv import load_dotenv

load_dotenv()

client = EDA_LLM_Client()

# This is the exact prompt the Dispatcher sends to the Decomposer when Control Unit fails
test_prompt = "Design a single-cycle RISC-V control unit for the OSOC F6 minirv subset."

print("[SYSTEM] Testing Forced Decomposition...")
plan = client.decompose_architecture(test_prompt, force_submodules=True)

if isinstance(plan, str):
    print(f"❌ Failed: {plan}")
else:
    print(f"✅ Success! Generated {len(plan.tasks)} tasks:")
    for i, t in enumerate(plan.tasks):
        print(f"  Task {i+1}: {t.module_name} (Class: {t.component_class})")