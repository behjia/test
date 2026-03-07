import ray
import os
import time

# Suppress Ray's future warning regarding GPU masking
os.environ["RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO"] = "0"

def initialize_dispatcher():
    num_cores = os.cpu_count()
    print(f"[SYSTEM] Detected {num_cores} CPU cores.")

    if not ray.is_initialized():
        ray.init(num_cpus=num_cores, log_to_driver=False)
    print("[SYSTEM] Ray cluster initialized successfully.\n")
    return num_cores

@ray.remote(num_cpus=1)
def mock_eda_worker(task_id: int, variation_name: str):
    print(f"--> [Worker {task_id}] Started compiling: {variation_name}")
    time.sleep(3) 
    print(f"<-- [Worker {task_id}] Finished: {variation_name}")
    return {"task_id": task_id, "status": "SUCCESS", "variation": variation_name}

if __name__ == "__main__":
    print("[SYSTEM] Dispatcher module loaded. Run this via the main CLI.")
    
    # cores = initialize_dispatcher()
    # designs = ["Ripple-Carry", "Carry-Lookahead", "Kogge-Stone", "Brent-Kung", "Sklansky"]
    
    # print(f"Dispatching {len(designs)} tasks to {cores} available cores...")
    # start_time = time.time()
    
    # futures = [mock_eda_worker.remote(i, design) for i, design in enumerate(designs)]
    # results = ray.get(futures)
    
    # end_time = time.time()
    
    # print("\n[RESULTS] All tasks completed:")
    # for res in results:
    #     print(res)
        
    # print(f"\nTotal Execution Time: {end_time - start_time:.2f} seconds")
# #V1:
# import ray
# import os
# import time

# def initialize_dispatcher():
#     # Detect available CPU cores in the Codespace
#     num_cores = os.cpu_count()
#     print(f"[SYSTEM] Detected {num_cores} CPU cores.")

#     # Initialize Ray, restricting it to available cores so it doesn't crash the VM
#     if not ray.is_initialized():
#         ray.init(num_cpus=num_cores, log_to_driver=False)
#     print("[SYSTEM] Ray cluster initialized successfully.\n")
#     return num_cores

# # The @ray.remote decorator converts this function into an asynchronous worker task.
# # We specify num_cpus=1 to tell Ray each task consumes exactly 1 CPU core.
# @ray.remote(num_cpus=1)
# def mock_eda_worker(task_id: int, variation_name: str):
#     print(f"--> [Worker {task_id}] Started compiling: {variation_name}")
    
#     # Simulate a heavy CPU-bound task (like Verilator compiling RTL)
#     time.sleep(3) 
    
#     print(f"<-- [Worker {task_id}] Finished: {variation_name}")
#     return {"task_id": task_id, "status": "SUCCESS", "variation": variation_name}

# if __name__ == "__main__":
#     cores = initialize_dispatcher()
    
#     # Define 5 mock Verilog architectural variations (Week 2 preview)
#     designs = ["Ripple-Carry", "Carry-Lookahead", "Kogge-Stone", "Brent-Kung", "Sklansky"]
    
#     print(f"Dispatching {len(designs)} tasks to {cores} available cores...")
#     start_time = time.time()

#     # Dispatch the tasks asynchronously. This creates a list of "ObjectRefs" (futures).
#     futures = [mock_eda_worker.remote(i, design) for i, design in enumerate(designs)]

#     # ray.get() acts as a barrier, blocking execution until ALL workers finish.
#     results = ray.get(futures)

#     end_time = time.time()
    
#     print("\n[RESULTS] All tasks completed:")
#     for res in results:
#         print(res)
        
#     print(f"\nTotal Execution Time: {end_time - start_time:.2f} seconds")