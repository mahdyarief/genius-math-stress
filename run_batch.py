#!/usr/bin/env python3
"""
Batch runner - runs take_quiz.py in parallel batches until target is reached.
Usage: python run_batch.py --target 100000 --parallel 50
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")

async def run_instance(instance_id):
    """Run a single instance of take_quiz.py."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, os.path.join(SCRIPT_DIR, "take_quiz.py"),
        "--instance", str(instance_id),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=SCRIPT_DIR
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode == 0

async def run_batch(batch_num, parallel_count, counter):
    """Run a batch of parallel instances."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Batch #{batch_num}: launching {parallel_count} instances...")

    tasks = [run_instance(i + 1) for i in range(parallel_count)]
    results = await asyncio.gather(*tasks)

    success = sum(1 for r in results if r)
    counter["total"] += parallel_count
    counter["success"] += success

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Batch #{batch_num} done: {success}/{parallel_count} success | Total: {counter['success']}/{counter['target']}")
    return success

async def main():
    parser = argparse.ArgumentParser(description="Batch runner for quiz automation")
    parser.add_argument("--target", type=int, default=14300, help="Total runs target (default: 14300 = 100K/week)")
    parser.add_argument("--parallel", type=int, default=5, help="Parallel instances per batch (default: 5, safe for long-running)")
    parser.add_argument("--duration", type=float, default=0, help="Max duration in hours (0 = run until target reached)")
    args = parser.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)

    duration_limit = args.duration * 3600 if args.duration > 0 else None

    print(f"{'='*60}")
    print(f"  Batch Quiz Runner")
    print(f"  Target: {args.target:,} runs")
    print(f"  Parallel per batch: {args.parallel}")
    if duration_limit:
        print(f"  Duration limit: {args.duration} hours")
    print(f"  Est. batches: {(args.target + args.parallel - 1) // args.parallel}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print()

    counter = {"total": 0, "success": 0, "target": args.target}
    batch_num = 0
    start_time = time.time()

    while counter["success"] < args.target:
        # Check duration limit
        if duration_limit and (time.time() - start_time) >= duration_limit:
            print(f"\n[Duration limit reached: {args.duration} hours]")
            break

        batch_num += 1
        remaining = args.target - counter["success"]
        current_batch = min(args.parallel, remaining)

        await run_batch(batch_num, current_batch, counter)

        # Small delay between batches to avoid resource exhaustion
        await asyncio.sleep(1)

    elapsed = time.time() - start_time
    rate = counter["success"] / elapsed if elapsed > 0 else 0
    rate_per_hour = rate * 3600

    print()
    print(f"{'='*60}")
    if counter["success"] >= args.target:
        print(f"  TARGET REACHED!")
    else:
        print(f"  DURATION LIMIT REACHED")
    print(f"  Total success: {counter['success']:,}")
    print(f"  Total time: {elapsed:.0f}s ({elapsed/3600:.1f}h)")
    print(f"  Rate: {rate:.2f} runs/sec ({rate_per_hour:.0f} runs/hour)")
    if elapsed > 0:
        est_24h = int(rate_per_hour * 24)
        print(f"  Est. 24h capacity: ~{est_24h:,} runs")
    print(f"  Results: {RESULTS_DIR}/")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
