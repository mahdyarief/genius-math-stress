# Genius Math Stress — Load-Test Harness (Indonesia Open)

Automated quiz submission harness for the **Genius Math Challenge (Indonesia Open)** competition at `https://geniusmath.techconnect.co.id/c/indonesiaopen`.

It registers a disposable identity per run (via cfmail `kvc.my.id`), solves the Cloudflare Turnstile challenge via **2captcha**, answers the quiz, submits, and captures a screenshot of the result. Designed to run long batches in parallel on both **Linux** and **Windows**.

> This is a load-test harness for the site owner/operator to measure backend resilience under concurrent traffic. It is not a prize-winning bot or a credential harvester.

## How it works

1. Generate a random Indonesian name (from a large pool in `names.json`, no repeated first names across parallel processes).
2. Create a disposable email `<username>@kvc.my.id` via cfmail.
3. Fill the registration form and solve Cloudflare Turnstile via 2captcha (`TurnstileTaskProxyless`).
4. Submit directly to the API, answer the quiz, then keep clicking "Main Lagi" until all 3 chances are used.
5. Screenshot the result page to `results_indo_open/YYYY-MM-DD/<username>.png`.

## Requirements

- **Python 3.10+** (Linux or Windows)
- A **2captcha** API key (https://2captcha.com) — used to solve Turnstile
- Internet access to `kvc.my.id` (cfmail) and the competition site

Everything else (patchright, Playwright Chromium) is installed automatically by the setup script.

## Setup

### Linux / macOS

```bash
./setup.sh
```

### Windows (PowerShell or CMD)

```
setup.bat
```

Both scripts:
- create a `.venv` virtual environment
- install `requirements.txt` (pins `patchright==1.62.1`)
- install the Chromium browser for patchright

### Configure the 2captcha key

Copy the template and fill in your real key:

```bash
cp .secret.example .secret
# then edit .secret:
#   2captcha_key=YOUR_REAL_KEY_HERE
```

On Windows:

```
copy .secret.example .secret
```

The runner reads the key in this order:
1. `CAPTCHA_API_KEY` environment variable
2. `2CAPTCHA_KEY` environment variable
3. `.secret` file in the project folder (or parent folder)

`.secret` is gitignored and never committed.

## Running

### Linux / macOS

The runner automatically writes a log file `batch_output_<target>.log`
(e.g. `batch_output_1000.log`) while still printing progress to the console,
so no manual redirect is needed.

```bash
# Run 1,000 submissions, 10 in parallel (foreground)
./run.sh --target 1000 --parallel 10

# Background (like nohup) — log is still auto-generated
nohup ./run.sh --target 1000 --parallel 10 >/dev/null 2>&1 &
```

### Windows

```powershell
# Foreground (blocks the terminal until done) — log is auto-generated
.\run.bat --target 1000 --parallel 10

# Background (terminal is not blocked, window hidden) — log is auto-generated
Start-Process -WindowStyle Hidden -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-u run_batch_indo_open.py --target 1000 --parallel 10"
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--target` | 14300 | Total successful runs to reach |
| `--parallel` | 5 | Instances running at once per batch (10 is fine) |
| `--duration` | 0 | Max runtime in hours (0 = run until target reached) |

Example: 6679 runs at parallel 10:

```bash
./run.sh --target 6679 --parallel 10
```

## Output

- Screenshots of result pages: `results_indo_open/YYYY-MM-DD/<username>.png`
- Diagnostic screenshots on failure: `results_indo_open/YYYY-MM-DD/errors/<username>_<tag>.png`
- Batch progress log: `batch_output_<target>.log`
- Per-instance logs: `quiz_log_XX.txt`

## Project structure

| File | Purpose |
|------|---------|
| `take_quiz_indo_open.py` | Per-account automation (register, solve captcha, answer, submit, screenshot) |
| `run_batch_indo_open.py` | Batch runner — spawns parallel instances, counts success |
| `run.sh` / `run.bat` | Launchers that always boot under the project venv |
| `setup.sh` / `setup.bat` | One-shot setup (venv + deps + browser) |
| `names.json` | Name pool data source (first/last names) |
| `.secret.example` | Template for the 2captcha key file |

## Troubleshooting

- **"venv python not found"** — run `./setup.sh` (or `setup.bat`) first; the venv must exist.
- **Batch fails 0/10 instantly** — make sure you launched via `./run.sh` (not plain `python3`), so child processes use the venv interpreter that has patchright.
- **Captcha rate-limit** — 2captcha can be overwhelmed by many simultaneous Turnstile requests; drop `--parallel` if you see whole batches fail.
- **Screenshots show loading state** — the harness waits for the result page before capturing; if you still see this, the result page took longer than the 60s poll window.
