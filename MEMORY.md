# Genius Math Stress — Project Memory

## Architecture

Load-test harness for Genius Math Challenge (Indonesia Open) at `geniusmath.techconnect.co.id/c/indonesiaopen`. Automates quiz submissions using:
- **patchright** (Playwright fork) for browser automation
- **2captcha** `TurnstileTaskProxyless` for Cloudflare Turnstile solving
- **cfmail** (`kvc.my.id`) for disposable email accounts per run
- Direct JSON POST to `/api/c/indonesiaopen/enter` to bypass React controlled components

## Key Files

- `take_quiz_indo_open.py` — Per-account automation script (form fill, quiz answer, submit, screenshot)
- `run_batch_indo_open.py` — Batch runner that spawns parallel instances
- `run.sh` / `run.bat` — Linux/Windows launchers that ensure venv python is used

## Key Decisions

- **Venv-only patchright**: patchright only installed in `.venv`, not system python. Batch runner re-execs itself under venv via `os.execv` (Linux) or `subprocess.call` (Windows).
- **Headless default**: Turnstile solved externally via 2captcha, so headless is acceptable and saves CPU/RAM.
- **Honest exit codes**: `main()` returns 0 if all runs succeed, 1 otherwise. Batch counts success via `proc.returncode == 0`.
- **Screenshot filename**: Uses username only (e.g., `rezasusanto738.png`) not full email, to avoid filesystem issues with `@` in filenames on Windows.

## Recent Sessions

- 2026-08-26: Batch 990 completed: 990/990 success in 2.3h (parallel 10, 422 runs/hour). Screenshot filenames changed from full email to username only.