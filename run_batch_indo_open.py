#!/usr/bin/env python3
"""
Batch runner for Indonesia Open quiz - runs take_quiz_indo_open.py in parallel batches.
Usage: python run_batch_indo_open.py --target 100000 --parallel 5 --duration 24
"""

import argparse
import asyncio
import hashlib
import os
import re
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


def _load_secret_values():
    """Read all key=value pairs from .secret (project dir first, then parent dir)."""
    for p in (os.path.join(SCRIPT_DIR, ".secret"), os.path.join(SCRIPT_DIR, "..", ".secret")):
        try:
            with open(p, encoding="utf-8") as f:
                return dict(line.strip().split("=", 1) for line in f if "=" in line)
        except OSError:
            continue
    return {}


# Solver providers this runner propagates to child instances:
# provider name -> (.secret key file, env var). Mirror of SOLVER_PROVIDERS in
# take_quiz_indo_open.py; SOLVER_PRIORITY mirrors its try order.
SOLVER_PROVIDERS = {
    "solvegate": ("solvegate_key", "SOLVEGATE_API_KEY"),
    "solvercf": ("solvercf_key", "SOLVERCF_API_KEY"),
    "nslsolver": ("nslsolver_key", "NSLSOLVER_API_KEY"),
}
SOLVER_PRIORITY = ["solvercf", "nslsolver", "solvegate"]

# Solver keys that reported "no balance", tracked across instances so a dead key
# is not re-probed by every child. A restart clears this, which is what you want
# after topping a key back up.
EXHAUSTED_KEY_IDS = set()
_KEY_EXHAUSTED_RE = re.compile(r"SOLVER_KEY_EXHAUSTED=([0-9a-f]{12})(?: \[([^\]]+)\])?")
_KEY_USED_RE = re.compile(r"Solved using key ([0-9a-f]{12})(?: \[([^\]]+)\])?")


def _key_id(key):
    """Short fingerprint matching take_quiz_indo_open.py's marker (not reversible)."""
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def _collect_keys(secrets, key_file):
    """All keys for a provider: `<key_file>s=k1,k2` (multi) or legacy single `<key_file>=k`."""
    plural = secrets.get(f"{key_file}s", "").strip()
    if plural:
        return [k.strip() for k in plural.split(",") if k.strip()]
    single = secrets.get(key_file, "").strip()
    return [single] if single else []


def _active_solver_provider():
    """Provider the child will use: SOLVER_PROVIDER env, then .secret, else "auto"."""
    p = os.environ.get("SOLVER_PROVIDER", "").strip().lower()
    if p in SOLVER_PROVIDERS:
        return p
    p = _load_secret_values().get("solver_provider", "").strip().lower()
    return p if p in SOLVER_PROVIDERS else "auto"


def _provider_keys(secrets, name):
    """Configured keys for one provider. A set env var wins over .secret."""
    key_file, key_env = SOLVER_PROVIDERS[name]
    env_val = os.environ.get(key_env)
    if env_val is not None:
        # Set-but-empty means every key was already filtered out for the child.
        return [k.strip() for k in env_val.split(",") if k.strip()]
    return _collect_keys(secrets, key_file)


def _solver_key_status():
    """Return (configured, usable, other_usable) for the providers the child tries.

    configured    keys present at all for the provider(s) that will be attempted
    usable        those not yet retired for lack of credit
    other_usable  usable keys on providers that will NOT be attempted (pinned
                  provider is narrower than "auto")
    """
    secrets = _load_secret_values()
    provider = _active_solver_provider()
    order = SOLVER_PRIORITY if provider == "auto" else [provider]
    configured = usable = 0
    for name in order:
        keys = _provider_keys(secrets, name)
        configured += len(keys)
        usable += sum(1 for k in keys if _key_id(k) not in EXHAUSTED_KEY_IDS)
    other_usable = 0
    for name in SOLVER_PROVIDERS:
        if name in order:
            continue
        keys = _provider_keys(secrets, name)
        other_usable += sum(1 for k in keys if _key_id(k) not in EXHAUSTED_KEY_IDS)
    return configured, usable, other_usable


EMAIL_DOMAIN = None  # set from --email-domain in main()


async def run_instance(instance_id):
    """Run a single instance of take_quiz_indo_open.py."""
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":99")
    secrets = _load_secret_values()
    for key_file, key_env in SOLVER_PROVIDERS.values():
        if env.get(key_env):
            continue
        keys = [k for k in _collect_keys(secrets, key_file) if _key_id(k) not in EXHAUSTED_KEY_IDS]
        env[key_env] = ",".join(keys)
    if not env.get("SOLVER_PROVIDER") and secrets.get("solver_provider"):
        env["SOLVER_PROVIDER"] = secrets["solver_provider"]
    if EMAIL_DOMAIN:
        env["EMAIL_DOMAIN"] = EMAIL_DOMAIN
    t0 = time.time()
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
    elapsed = time.time() - t0
    ok = proc.returncode == 0

    out_text = stdout.decode("utf-8", errors="replace").strip()
    err_text = stderr.decode("utf-8", errors="replace").strip()

    # Always log a one-line summary per instance
    ts = datetime.now().strftime("%H:%M:%S")

    # Retire any key a child reported as out of credit, so later instances skip it.
    for kid, label in _KEY_EXHAUSTED_RE.findall(out_text) + _KEY_EXHAUSTED_RE.findall(err_text):
        if kid not in EXHAUSTED_KEY_IDS:
            EXHAUSTED_KEY_IDS.add(kid)
            tag = f" [{label}]" if label else ""
            print(f"[{ts}]   Solver key {kid}{tag} out of credit - retired for this run")

    if ok:
        used = _KEY_USED_RE.findall(out_text)
        if used:
            kid, label = used[-1]
            label_note = f" ({label})" if label else ""
            key_note = f" [key {kid}{label_note}]"
        else:
            key_note = ""
        print(f"[{ts}]   Instance #{instance_id}: OK ({elapsed:.0f}s){key_note}")
    else:
        print(f"[{ts}]   Instance #{instance_id}: FAILED ({elapsed:.0f}s, exit={proc.returncode})")
        # Print last 10 lines of stdout to show the error
        if out_text:
            lines = out_text.split("\n")
            tail = lines[-10:] if len(lines) > 10 else lines
            for line in tail:
                stripped = line.strip()
                if stripped:
                    print(f"[{ts}]     | {stripped}")
        if err_text:
            print(f"[{ts}]     STDERR:")
            for line in err_text.strip().split("\n")[-10:]:
                stripped = line.strip()
                if stripped:
                    print(f"[{ts}]     ! {stripped}")

        # Print the tail of the instance's quiz log file — it holds the
        # step-by-step reason for the failure, which stdout does not.
        quiz_log = os.path.join(SCRIPT_DIR, f"quiz_log_{instance_id:02d}.txt")
        try:
            with open(quiz_log, encoding="utf-8") as f:
                qlines = [l.rstrip() for l in f if l.strip()]
            tail = qlines[-15:] if len(qlines) > 15 else qlines
            if tail:
                print(f"[{ts}]     Quiz log tail ({os.path.basename(quiz_log)}):")
                for line in tail:
                    print(f"[{ts}]       {line}")
        except OSError:
            print(f"[{ts}]     (no quiz log found at {quiz_log})")

    return ok

async def run_batch(batch_num, parallel_count, counter):
    """Run a batch of parallel instances."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] Batch #{batch_num}: launching {parallel_count} instances...")

    tasks = []
    for i in range(parallel_count):
        tasks.append(asyncio.create_task(run_instance(i + 1)))
        await asyncio.sleep(1.5)  # stagger: 1.5s between each instance launch
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
    parser.add_argument("--email-domain", type=str, default=None, help="Static email domain (e.g. gmail.com) instead of random cfmail domains")
    args = parser.parse_args()
    global EMAIL_DOMAIN
    EMAIL_DOMAIN = args.email_domain

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
    stop_reason = None

    while counter["success"] < args.target:
        # Check duration limit
        if duration_limit and (time.time() - start_time) >= duration_limit:
            print(f"\n[Duration limit reached: {args.duration} hours]")
            stop_reason = f"duration limit reached ({args.duration} hours)"
            break

        # Stop when the Turnstile can no longer be solved at all: no key is
        # configured (nothing to try) or every configured key is out of credit.
        # Continuing just burns batches that all fail CAPTCHA.
        configured, usable, other_usable = _solver_key_status()
        provider = _active_solver_provider()
        if configured == 0:
            print(f"\n[No solver API key configured for provider '{provider}' - stopping. Add a key in .secret, then rerun.]")
            stop_reason = f"no solver key configured for provider '{provider}'"
            break
        if usable == 0:
            print(f"\n[All {provider} solver keys are out of credit - stopping. Top up a key or add another in .secret, then rerun.]")
            if other_usable:
                print(f"[Note: {other_usable} usable key(s) exist for other providers, but solver_provider={provider} pins this run to {provider}. Set solver_provider=auto in .secret to fail over.]")
            stop_reason = "all solver keys out of credit"
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
        print(f"  STOPPED: {stop_reason or 'duration limit reached'}")
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
