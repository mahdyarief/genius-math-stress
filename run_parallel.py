#!/usr/bin/env python3
"""
Parallel runner for take_quiz.py - runs multiple instances concurrently.
Each instance runs independently with its own browser context.
"""

import asyncio
import subprocess
import sys
from datetime import datetime

TOTAL_PARALLEL = 50

async def run_instance(instance_num):
    """Run a single instance of take_quiz.py."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [Instance {instance_num}] Starting...")

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "take_quiz.py", "--instance", str(instance_num),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()

    ts = datetime.now().strftime("%H:%M:%S")
    if proc.returncode == 0:
        print(f"[{ts}] [Instance {instance_num}] Completed successfully")
    else:
        print(f"[{ts}] [Instance {instance_num}] Failed with code {proc.returncode}")
        if stderr:
            print(f"[{ts}] [Instance {instance_num}] Error: {stderr.decode()[:200]}")

    return proc.returncode == 0

async def main():
    print(f"{'='*60}")
    print(f"  Parallel Quiz Runner")
    print(f"  Total parallel instances: {TOTAL_PARALLEL}")
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print()

    start_time = datetime.now()

    # Launch all instances in parallel
    tasks = [run_instance(i+1) for i in range(TOTAL_PARALLEL)]
    results = await asyncio.gather(*tasks)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    success_count = sum(1 for r in results if r)

    print()
    print(f"{'='*60}")
    print(f"  ALL INSTANCES COMPLETED")
    print(f"  Success: {success_count}/{TOTAL_PARALLEL}")
    print(f"  Total time: {duration:.1f}s")
    print(f"  Finished at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
