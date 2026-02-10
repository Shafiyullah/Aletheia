import asyncio
import time
import os
import sys

# Add root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.async_utils import async_manager

def cpu_bound_task(n: int) -> int:
    """Simulates a heavy CPU task (e.g. PDF parsing)"""
    print(f"[CPU] Starting heavy task {n} on PID {os.getpid()}")
    time.sleep(1) # Block the process
    return n * n

async def io_bound_task(n: int) -> str:
    """Simulates an I/O task (e.g. API call)"""
    print(f"[I/O] Starting API call {n}")
    await asyncio.sleep(0.5) # Non-blocking sleep
    return f"Result {n}"

async def test_async_utils():
    print("--- Testing AsyncUtils ---\n")
    
    start_time = time.time()

    # 1. Test CPU Offloading (Should be fast if parallel)
    print("1. Launching 4 CPU tasks...")
    cpu_futures = [async_manager.run_cpu_job(cpu_bound_task, i) for i in range(4)]
    cpu_results = await asyncio.gather(*cpu_futures)
    print(f"CPU Results: {cpu_results}")
    
    # 2. Test I/O Concurrency
    print("\n2. Launching 10 I/O tasks...")
    io_tasks = [io_bound_task(i) for i in range(10)]
    io_results = await async_manager.run_batched_io_jobs(io_tasks)
    print(f"I/O Results: {len(io_results)} items completed.")

    duration = time.time() - start_time
    print(f"\nTotal Duration: {duration:.2f}s")
    
    # If sequential: CPU(1s)*4 + IO(0.5s)*10 = 9s
    # If parallel: CPU(1s) (approx) + IO(0.5s) = ~1.5s - 2s
    if duration < 5:
        print("✅ PASS: Execution was parallel!")
    else:
        print("❌ FAIL: Execution seemd sequential.")

    # Cleanup
    async_manager.shutdown()

if __name__ == "__main__":
    if os.name == 'nt':
         # Windows process support fix
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_async_utils())
