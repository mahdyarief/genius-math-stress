#!/usr/bin/env python3
"""
Batch runner for Indonesia Open quiz - runs take_quiz_indo_open.py in parallel batches.
Usage: python run_batch_indo_open.py --target 100000 --parallel 5 --duration 24
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime

# Re-exec under the project venv (which has patchright) so child instances
# spawned via sys.executable inherit the correct interpreter.
_BASE = os.path.dirname(os.path.abspath(__file__))
_VENV_PY = os.path.join(_BASE, ".venv", "Scripts", "python.exe") if os.name == "nt" else os.path.join(_BASE, ".venv", "bin", "python")
if os.path.exists(_VENV_PY) and os.path.realpath(sys.executable) != os.path.realpath(_VENV_PY):
    if os.name == "nt":
        # os.execv is unavailable on Windows; re-launch as a child process.
        import subprocess
        raise SystemExit(subprocess.call([_VENV_PY, os.path.abspath(__file__)] + sys.argv[1:]))
    os.execv(_VENV_PY, [_VENV_PY, os.path.abspath(__file__)] + sys.argv[1:])

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results_indo_open")

# Create date-based subfolder: results_indo_open/YYYY-MM-DD/
BATCH_DATE = datetime.now().strftime("%Y-%m-%d")
BATCH_DIR = os.path.join(RESULTS_DIR, BATCH_DATE)


class _Tee:
    """Duplicates writes to multiple streams (console + log file)."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def _load_captcha_key():
    key = os.environ.get("CAPTCHA_API_KEY", "")
    if key:
        return key
    key = os.environ.get("2CAPTCHA_KEY", "")
    if key:
        return key
    for p in (os.path.join(SCRIPT_DIR, ".secret"), os.path.join(SCRIPT_DIR, "..", ".secret")):
        try:
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("2captcha_key="):
                        return line.split("=", 1)[1]
        except OSError:
            continue
    return ""


async def run_instance(instance_id):
    """Run a single instance of take_quiz_indo_open.py."""
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":99")
    if not env.get("CAPTCHA_API_KEY"):
        env["CAPTCHA_API_KEY"] = _load_captcha_key()
    proc = await asyncio.create_subprocess_exec(
        sys.executable, os.path.join(SCRIPT_DIR, "take_quiz_indo_open.py"),
        "--instance", str(instance_id),
        "--output-dir", BATCH_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=SCRIPT_DIR,
        env=env,
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
    parser = argparse.ArgumentParser(description="Batch runner for Indonesia Open quiz automation")
    parser.add_argument("--target", type=int, default=14300, help="Total runs target (default: 14300 = 100K/week)")
    parser.add_argument("--parallel", type=int, default=5, help="Parallel instances per batch (default: 5, safe for long-running)")
    parser.add_argument("--duration", type=float, default=0, help="Max duration in hours (0 = run until target reached)")
    args = parser.parse_args()

    # Auto-generate batch_output_<target>.log (tee: console + file), so no
    # manual `> batch_output_N.log 2>&1` redirect is needed.
    log_path = os.path.join(SCRIPT_DIR, f"batch_output_{args.target}.log")
    log_file = open(log_path, "w", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.__stdout__, log_file)
    sys.stderr = _Tee(sys.__stderr__, log_file)

    os.makedirs(BATCH_DIR, exist_ok=True)

    duration_limit = args.duration * 3600 if args.duration > 0 else None

    print(f"{'='*60}")
    print(f"  Batch Quiz Runner - Indonesia Open")
    print(f"  URL: https://geniusmath.techconnect.co.id/c/indonesiaopen")
    print(f"  Target: {args.target:,} runs")
    print(f"  Parallel per batch: {args.parallel}")
    if duration_limit:
        print(f"  Duration limit: {args.duration} hours")
    print(f"  Est. batches: {(args.target + args.parallel - 1) // args.parallel}")
    print(f"  Log file: {log_path}")
    print(f"  Output folder: {BATCH_DIR}")
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
    print(f"  Results: {BATCH_DIR}/")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
