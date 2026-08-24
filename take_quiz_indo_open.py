#!/usr/bin/env python3
"""
Loop automation for Genius Math Challenge - runs 10 times with random data.
Each run fills the form, answers quiz, clicks Selesai, and saves a screenshot.
Full logging at every step so nothing is blind.
"""

import argparse
import asyncio
import json
import os
import random
import string
import time
import urllib.request
import urllib.error
from datetime import datetime
from patchright.async_api import async_playwright

# Cloudflare bypass: stealth mode settings
STEALTH_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--disable-features=IsolateOrigins,site-per-process',
    '--disable-site-isolation-trials',
    '--disable-web-security',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--disable-popup-blocking',
    '--disable-translate',
    '--disable-background-timer-throttling',
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',
]

BASE_URL = "https://geniusmath.techconnect.co.id/c/indonesiaopen"
CFMAIL_API = "https://cfmail.solution.qzz.io/api"
CFMAIL_DOMAIN = "kvc.my.id"

# Captcha solver (2captcha — accepts card/PayPal) — set CAPTCHA_API_KEY in env
CAPTCHA_API_KEY = os.environ.get("CAPTCHA_API_KEY", "")
CAPTCHA_ENDPOINT = os.environ.get("CAPTCHA_ENDPOINT", "https://api.2captcha.com")
TURNSTILE_SITEKEY = "0x4AAAAAAEYhltGARvbbIjE4"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "results_indo_open", datetime.now().strftime("%Y-%m-%d"))
TOTAL_RUNS = 1

# Parse args for instance ID (used by parallel runner)
parser = argparse.ArgumentParser()
parser.add_argument("--instance", type=int, default=0, help="Instance number for parallel runs")
parser.add_argument("--output-dir", type=str, default=None, help="Override output directory for screenshots")
args, _ = parser.parse_known_args()
INSTANCE_ID = args.instance
if args.output_dir:
    OUTPUT_DIR = args.output_dir
LOG_FILE = os.path.join(SCRIPT_DIR, f"quiz_log_{INSTANCE_ID:02d}.txt" if INSTANCE_ID else "quiz_log.txt")

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

async def wait_for_result(page, timeout_ms=60000):
    """Poll until the score calculation ('Menghitung hasilmu..') finishes."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        try:
            body = await page.inner_text("body")
        except Exception:
            await page.wait_for_timeout(1000)
            continue
        if "Menghitung hasilmu" in body:
            await page.wait_for_timeout(1000)
            continue
        if "Kamu Sudah Selesai" in body or "TINGKAT KEJENIUSAN" in body or "Hasil Kamu" in body:
            return True
        await page.wait_for_timeout(1000)
    return False

def random_name():
    first_names = [
        "Ahmad", "Budi", "Citra", "Dewi", "Eko", "Fajar", "Gita", "Hadi", "Indra", "Joko",
        "Kartika", "Lina", "Maya", "Nina", "Omar", "Putri", "Rina", "Sari", "Tono", "Umar",
        "Agus", "Bambang", "Cahya", "Dimas", "Erik", "Farhan", "Galih", "Hendra", "Irfan", "Jihan",
        "Kevin", "Lukman", "Mira", "Nanda", "Oki", "Putra", "Qori", "Reza", "Sinta", "Taufik",
        "Andi", "Bella", "Cindy", "Dian", "Elisa", "Fitri", "Grace", "Hana", "Ika", "Julia",
        "Andika", "Bayu", "Chandra", "Dani", "Faisal", "Gilang", "Haris", "Ilham", "Kevin", "Luthfi",
        "Aulia", "Bulan", "Cantika", "Della", "Elsa", "Febri", "Gisela", "Hesti", "Indah", "Janet",
        "Arif", "Bagas", "Cahyo", "Deni", "Endra", "Firmansyah", "Ghani", "Hafiz", "Iqbal", "Jefri",
        "Adi", "Bimo", "Candra", "Dwi", "Edi", "Fauzi", "Gunawan", "Heru", "Imam", "Joko",
        "Ani", "Betty", "Clara", "Dina", "Eva", "Flora", "Gina", "Heni", "Ira", "Julie"
    ]
    last_names = [
        "Pratama", "Wijaya", "Santoso", "Hidayat", "Kurniawan", "Saputra", "Permata", "Lestari", "Nugroho", "Susanto",
        "Wibowo", "Handayani", "Kusuma", "Rahman", "Setiawan", "Surya", "Purnama", "Sari", "Dewi", "Anggraini",
        "Firmansyah", "Hakim", "Iskandar", "Jaya", "Kartika", "Lesmana", "Mahendra", "Nugraha", "Oktavia", "Prasetyo",
        "Ramadhan", "Salim", "Tamara", "Utama", "Valentina", "Wulandari", "Yuliana", "Zubaidi", "Arifin", "Bahar",
        "Cahyono", "Darmawan", "Effendi", "Gunawan", "Hartono", "Irawan", "Julianto", "Kurniadi", "Laksono", "Maulana",
        "Nainggolan", "Oktaviano", "Prabowo", "Rizaldi", "Saputro", "Tjahjadi", "Utomo", "Virgianti", "Wicaksono", "Yudhistira",
        "Abdullah", "Bagaskara", "Cakrawala", "Dhanu", "Elang", "Firmanda", "Ghani", "Hermawan", "Ibrahim", "Junaedi"
    ]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def create_cfmail_email(name):
    """Create a real disposable email via cfmail API with static domain."""
    try:
        # Step 1: Create session
        req = urllib.request.Request(f"{CFMAIL_API}/session", method="GET")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            session_data = json.loads(resp.read().decode())
            session_id = session_data["sessionId"]

        # Step 2: Create inbox with static domain
        clean = name.lower().replace(" ", "").replace(".", "")
        num = random.randint(1, 9999)
        address = f"{clean}{num}"

        req = urllib.request.Request(
            f"{CFMAIL_API}/inboxes",
            data=json.dumps({"localPart": address, "domain": CFMAIL_DOMAIN}).encode(),
            headers={"Content-Type": "application/json", "x-session-id": session_id},
            method="POST"
        )
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            inbox_data = json.loads(resp.read().decode())
            email = inbox_data.get("address", "")
            if email:
                log(f"[cfmail] Created email: {email}")
                log(f"[cfmail] Full session ID: {session_id}")
                return email, session_id
    except Exception as e:
        log(f"[cfmail] API failed: {e}")

    return None, None

def random_phone():
    prefixes = ["0812", "0813", "0821", "0822", "0852", "0853", "0856", "0857", "0878", "0895", "0896"]
    return f"{random.choice(prefixes)}{''.join(random.choices(string.digits, k=8))}"

def solve_turnstile():
    """Solve the Turnstile via 2captcha and return the cf-turnstile-response token."""
    if not CAPTCHA_API_KEY:
        log(f"[2captcha] No API key set (CAPTCHA_API_KEY), skipping solver.")
        return None
    try:
        task_payload = {
            "clientKey": CAPTCHA_API_KEY,
            "task": {
                "type": "TurnstileTaskProxyless",
                "websiteURL": BASE_URL,
                "websiteKey": TURNSTILE_SITEKEY,
            },
        }
        req = urllib.request.Request(
            f"{CAPTCHA_ENDPOINT}/createTask",
            data=json.dumps(task_payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            d = json.loads(resp.read().decode())
        if d.get("errorId", 1) != 0:
            log(f"[2captcha] createTask error: {d.get('errorDescription', d)}")
            return None
        task_id = d["taskId"]
        log(f"[2captcha] Task created: {task_id}")

        # Poll getTaskResult
        for _ in range(40):
            time.sleep(3)
            r_req = urllib.request.Request(
                f"{CAPTCHA_ENDPOINT}/getTaskResult",
                data=json.dumps({"clientKey": CAPTCHA_API_KEY, "taskId": task_id}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(r_req, timeout=20) as resp:
                r = json.loads(resp.read().decode())
            if r.get("errorId", 1) != 0:
                log(f"[2captcha] getTaskResult error: {r.get('errorDescription', r)}")
                return None
            if r.get("status") == "ready":
                token = r.get("solution", {}).get("token", "")
                log(f"[2captcha] Token received ({len(token)} chars)")
                return token

        log(f"[2captcha] Timed out waiting for token")
        return None
    except Exception as e:
        log(f"[2captcha] API failed: {e}")
        return None


async def inject_turnstile_token(page, token):
    """Inject a solved cf-turnstile-response token into the form and enable submit."""
    js = """
        (token) => {
            // React-safe value setter: bypasses React's value tracker so the
            // controlled input's change is seen, not just the raw DOM property.
            const nativeInputSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            const nativeTextareaSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            const setVal = (el, v) => {
                if (el.tagName === 'INPUT' && nativeInputSetter) nativeInputSetter.call(el, v);
                else if (el.tagName === 'TEXTAREA' && nativeTextareaSetter) nativeTextareaSetter.call(el, v);
                else el.value = v;
            };

            // Set the token on any recognized Turnstile/recaptcha response field
            const names = ['cf-turnstile-response', 'turnstile-response', 'g-recaptcha-response'];
            let hit = false;
            for (const n of names) {
                document.querySelectorAll(`[name="${n}"]`).forEach(el => {
                    setVal(el, token);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    hit = true;
                });
            }
            // If no such field exists, create one in the first form
            if (!hit) {
                const form = document.querySelector('form');
                if (form) {
                    let el = document.createElement('textarea');
                    el.name = 'cf-turnstile-response';
                    el.style.display = 'none';
                    setVal(el, token);
                    form.appendChild(el);
                }
            }
            // Store it globally for the site's submit handler to read
            window.__cfTurnstileToken = token;
            // Invoke any registered turnstile callback (data-callback global or window.turnstile)
            const cbEl = document.querySelector('[data-callback]');
            const cbName = cbEl && cbEl.getAttribute('data-callback');
            if (cbName) {
                const fn = cbName.split('.').reduce((acc, p) => (acc && acc[p]), window);
                if (typeof fn === 'function') { try { fn(token); } catch (e) {} }
            }
            if (window.turnstile && typeof window.turnstile.callback === 'function') {
                try { window.turnstile.callback(token); } catch (e) {}
            }
            // Force-enable the submit button so the form can be submitted.
            // The server validates the cf-turnstile-response token independently.
            document.querySelectorAll('button[type="submit"]').forEach(b => {
                b.removeAttribute('disabled');
                b.removeAttribute('aria-disabled');
            });
            return true;
        }
    """
    try:
        await page.evaluate(js, token)
        log(f"[2captcha] Token injected into form")
        return True
    except Exception as e:
        log(f"[2captcha] Token injection failed: {e}")
        return False


async def handle_cloudflare_turnstile(page, timeout=25000):
    """Solve Cloudflare Turnstile — 2captcha solver first, then click-and-wait fallback.

    The widget is a checkbox ("Verify you are human"). We click it (inside the
    cross-origin iframe) and then wait for the cf-turnstile-response token, the
    widget to disappear, or the submit button to enable.
    """
    try:
        frames = page.frames
        has_turnstile = any('challenges.cloudflare.com' in f.url for f in frames)
        if not has_turnstile:
            log(f"[Cloudflare] No Turnstile challenge detected, skipping...")
            return True

        # Primary path: solve via 2captcha API and inject the token
        token = solve_turnstile()
        if token:
            ok = await inject_turnstile_token(page, token)
            if ok:
                log(f"[Cloudflare] Turnstile solved via 2captcha")
                return True

        log(f"[Cloudflare] Solver unavailable, falling back to click-and-wait...")

        # 1. Try clicking the checkbox inside the Turnstile iframe
        clicked = False
        for frame in frames:
            if 'challenges.cloudflare.com' not in frame.url:
                continue
            for sel in ["input[type='checkbox']", "#challenge-stage", ".cb-i", "label", "body"]:
                try:
                    el = frame.locator(sel).first
                    if await el.count() > 0:
                        await el.click(timeout=5000)
                        log(f"[Cloudflare] Clicked Turnstile via frame ({sel})")
                        clicked = True
                        break
                except Exception:
                    continue
            if clicked:
                break

        # 2. Fallback: click the iframe element by coordinates (checkbox area)
        if not clicked:
            ts_el = page.locator("iframe[src*='challenges.cloudflare.com']").first
            if await ts_el.count() > 0:
                box = await ts_el.bounding_box()
                if box:
                    x = box['x'] + 25
                    y = box['y'] + box['height'] / 2
                    await page.mouse.click(x, y)
                    log(f"[Cloudflare] Clicked Turnstile at ({x:.0f}, {y:.0f})")
                    clicked = True

        if not clicked:
            log(f"[Cloudflare] WARNING: could not click Turnstile")
            return False

        # 3. Wait for token / widget gone / button enabled
        start = time.time()
        interval = 1000
        while time.time() - start < timeout / 1000:
            token_inputs = [
                "input[name='cf-turnstile-response']",
                "input[name='turnstile-token']",
                "textarea[name='cf-turnstile-response']",
            ]
            for sel in token_inputs:
                el = page.locator(sel).first
                if await el.count() > 0:
                    val = await el.get_attribute("value") or (await el.input_value() if await el.is_editable() else None)
                    if val and len(val) > 10:
                        log(f"[Cloudflare] Turnstile token received ({len(val)} chars)")
                        return True

            submit_btn = page.locator("button[type='submit']").first
            if await submit_btn.count() > 0:
                if not await submit_btn.is_disabled():
                    log(f"[Cloudflare] Submit button enabled (Turnstile passed)")
                    return True

            current_frames = page.frames
            if not any('challenges.cloudflare.com' in f.url for f in current_frames):
                log(f"[Cloudflare] Turnstile challenge disposed (solved)")
                return True

            await page.wait_for_timeout(interval)

        log(f"[Cloudflare] WARNING: Turnstile did not solve after {timeout//1000}s")
        return False

    except Exception as e:
        log(f"[Cloudflare] Error handling Turnstile: {e}")
        return False

async def submit_entry(page, token):
    """POST the entry JSON directly to /api/c/<slug>/enter, bypassing the React form.

    The submit button is gated by React state that only the Turnstile callback can
    set (the token lives in React state `Z`, not in the hidden `cf-turnstile-response`
    input). We replicate the app's own `er()` handler: read the controlled inputs'
    current values from the DOM, then POST the same JSON body with `turnstileToken`.
    """
    slug = BASE_URL.rstrip("/").split("/")[-1]
    js = """
    async (token) => {
        const val = (sel) => { const el = document.querySelector(sel); return el ? el.value : ""; };
        const radio = (name) => {
            const inputs = Array.from(document.querySelectorAll(`input[name="${name}"]`));
            const idx = inputs.findIndex(i => i.checked);
            if (idx === 0) return true;   // first option is the "true"/"Ya"/"Pernah" choice
            if (idx === 1) return false;  // second option is the "false"/"Tidak" choice
            return null;
        };
        // Province select stores the code as its value; the API wants the province NAME.
        const provSel = document.querySelector("#c-province");
        const province = provSel && provSel.selectedOptions[0] ? provSel.selectedOptions[0].textContent.trim() : "";
        const body = {
            fullName: val("#c-name"),
            email: val("#c-email"),
            phone: val("#c-phone"),
            province: province,
            city: val("#c-city"),          // city select value is the city name
            ageRange: val("#c-age"),       // age select value is the raw key (e.g. age_27_33)
            wonMathCompetition: radio("c-juara"),
            interestedInCompetition: radio("c-interested"),
        };
        if (token) body.turnstileToken = token;
        const resp = await fetch(`/api/c/${slug}/enter`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const data = await resp.json().catch(() => ({ }));
        return { ok: resp.ok, status: resp.status, body: data };
    }
    """.replace("${slug}", slug)
    try:
        result = await page.evaluate(js, token)
        log(f"[submit_entry] status={result.get('status')} ok={result.get('ok')} body={result.get('body')}")
        return result
    except Exception as e:
        log(f"[submit_entry] POST failed: {e}")
        return {"ok": False, "status": 0, "body": {"error": str(e)}}


async def run_once(browser, run_num):
    log(f"{'='*60}")
    log(f"  RUN #{run_num} START")
    log(f"{'='*60}")

    # Create a fresh context with stealth settings
    context = await browser.new_context(
        viewport={"width": 1280, "height": 1024},
        locale="id-ID",
        timezone_id="Asia/Jakarta"
    )
    page = await context.new_page()

    # Hide webdriver property + patch mouse event coordinates to bypass Cloudflare
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['id-ID', 'id', 'en']});
        window.chrome = {runtime: {}};

        function getRandomInt(min, max) {
            return Math.floor(Math.random() * (max - min + 1)) + min;
        }
        try {
            Object.defineProperty(MouseEvent.prototype, 'screenX', { get: () => getRandomInt(800, 1200) });
            Object.defineProperty(MouseEvent.prototype, 'screenY', { get: () => getRandomInt(400, 600) });
            Object.defineProperty(PointerEvent.prototype, 'screenX', { get: () => getRandomInt(800, 1200) });
            Object.defineProperty(PointerEvent.prototype, 'screenY', { get: () => getRandomInt(400, 600) });
        } catch (e) {}
    """)

    try:
        # Step 1: Navigate
        log(f"[Step 1] Navigating to {BASE_URL}")
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        log(f"[Step 1] Page loaded. URL: {page.url}")

        # Handle Cloudflare Turnstile if present
        await handle_cloudflare_turnstile(page)

        # Step 2: Click "Lanjut"
        log(f"[Step 2] Waiting for 'Lanjut' button...")
        await page.wait_for_selector("button:has-text('Lanjut'), button:has-text('Mulai')", timeout=10000)
        lanjut_btn = page.locator("button:has-text('Lanjut'), button:has-text('Mulai')").first
        btn_text = await lanjut_btn.inner_text()
        log(f"[Step 2] Found button: '{btn_text}' -> Clicking...")
        await lanjut_btn.click()
        log(f"[Step 2] Clicked. Waiting 2s for form to appear...")
        await page.wait_for_timeout(2000)

        # Step 3: Generate & fill form
        test_name = random_name()
        test_email, cfmail_session = create_cfmail_email(test_name)
        if not test_email:
            log(f"[Step 3] ERROR: Failed to create cfmail email, skipping run")
            return False
        test_phone = random_phone()
        log(f"[Step 3] Generated data:")
        log(f"         Name:    {test_name}")
        log(f"         Email:   {test_email}")
        log(f"         Phone:   {test_phone}")
        log(f"         Session: {cfmail_session[:8]}...")

        log(f"[Step 3] Filling name field (#c-name)...")
        await page.fill("#c-name", test_name)
        log(f"[Step 3] Filling email field (#c-email)...")
        await page.fill("#c-email", test_email)
        log(f"[Step 3] Filling phone field (#c-phone)...")
        await page.fill("#c-phone", test_phone)
        log(f"[Step 3] Name, email, phone filled.")

        # Province
        log(f"[Step 3] Loading province dropdown...")
        province_options = await page.locator("#c-province option").all()
        log(f"[Step 3] Found {len(province_options)} provinces")
        if len(province_options) > 1:
            idx = random.randint(1, len(province_options) - 1)
            prov_text = await province_options[idx].inner_text()
            await page.select_option("#c-province", index=idx)
            log(f"[Step 3] Selected province: '{prov_text}' (index {idx})")
            log(f"[Step 3] Waiting 1s for city dropdown to populate...")
            await page.wait_for_timeout(1000)

        # City
        log(f"[Step 3] Loading city dropdown...")
        await page.wait_for_timeout(1500)
        city_options = await page.locator("#c-city option").all()
        log(f"[Step 3] Found {len(city_options)} cities")
        if len(city_options) > 1:
            idx = random.randint(1, len(city_options) - 1)
            city_text = await city_options[idx].inner_text()
            await page.select_option("#c-city", index=idx)
            log(f"[Step 3] Selected city: '{city_text}' (index {idx})")

        # Age
        log(f"[Step 3] Loading age dropdown...")
        age_options = await page.locator("#c-age option").all()
        log(f"[Step 3] Found {len(age_options)} age options")
        if len(age_options) > 1:
            idx = random.randint(1, len(age_options) - 1)
            age_text = await age_options[idx].inner_text()
            await page.select_option("#c-age", index=idx)
            log(f"[Step 3] Selected age: '{age_text}' (index {idx})")

        # Radio buttons
        log(f"[Step 3] Selecting radio: c-juara...")
        juara_labels = page.locator("label:has(input[name='c-juara'])")
        juara_count = await juara_labels.count()
        if juara_count > 0:
            idx = random.randint(0, juara_count - 1)
            await juara_labels.nth(idx).click()
            log(f"[Step 3] Selected c-juara option #{idx}")

        log(f"[Step 3] Selecting radio: c-interested...")
        interested_labels = page.locator("label:has(input[name='c-interested'])")
        interested_count = await interested_labels.count()
        if interested_count > 0:
            idx = random.randint(0, interested_count - 1)
            await interested_labels.nth(idx).click()
            log(f"[Step 3] Selected c-interested option #{idx}")

        # Step 3.5: Solve Cloudflare Turnstile via 2captcha
        log(f"[Step 3.5] Solving Cloudflare Turnstile via 2captcha...")
        token = solve_turnstile()
        if token:
            log(f"[Step 3.5] Token received ({len(token)} chars)")
        else:
            log(f"[Step 3.5] WARNING: no token from 2captcha, submit may fail")

        # Step 4: Submit entry directly to the backend (bypasses the React-gated button)
        log(f"[Step 4] Posting entry directly to /api/c/indonesiaopen/enter...")
        result = await submit_entry(page, token)
        if not result.get("ok"):
            log(f"[Step 4] ERROR: entry rejected: {result}")
            return False
        log(f"[Step 4] Entry accepted. Reloading page to enter quiz state...")
        await page.reload(wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Step 5: Start quiz
        await page.wait_for_timeout(3000)
        log(f"[Step 5] Current URL: {page.url}")
        log(f"[Step 5] Looking for 'Mulai Kerjakan Soal' button...")
        mulai_btn = page.locator("button:has-text('Mulai Kerjakan Soal')")
        if await mulai_btn.count() > 0:
            log(f"[Step 5] Found 'Mulai Kerjakan Soal' -> Clicking...")
            await mulai_btn.click()
            log(f"[Step 5] Waiting for answer buttons to appear...")
            await page.wait_for_selector("button:has-text('A')", timeout=10000)
            await page.wait_for_timeout(1000)
            log(f"[Step 5] Quiz loaded!")
        else:
            # The quiz may already be in progress (questions visible) without the
            # "Mulai Kerjakan Soal" instruction screen. Detect answer buttons directly.
            answer_probe = page.locator("button:has-text('A'), button:has-text('B'), button:has-text('C'), button:has-text('D')")
            if await answer_probe.count() > 0:
                log(f"[Step 5] No 'Mulai Kerjakan Soal' button, but quiz is already showing questions -> proceeding.")
            else:
                log(f"[Step 5] ERROR: No 'Mulai Kerjakan Soal' button found!")
                # Debug: dump page text
                page_text = await page.inner_text("body")
                log(f"[Step 5] Page text (first 500 chars): {page_text[:500]}")
                return False

        # Step 6: Answer quiz
        log(f"[Step 6] Starting quiz...")
        question_count = 0
        max_questions = 10

        while question_count < max_questions:
            log(f"[Step 6] --- Question {question_count + 1} ---")
            answer_buttons = page.locator("button:has-text('A'), button:has-text('B'), button:has-text('C'), button:has-text('D'), button:has-text('E')")
            answer_count = await answer_buttons.count()
            log(f"[Step 6] Found {answer_count} buttons matching A-E pattern")

            if answer_count == 0:
                log(f"[Step 6] No answer buttons found -> quiz done")
                break

            # Filter valid answers
            valid_answers = []
            for i in range(answer_count):
                btn_text = await answer_buttons.nth(i).inner_text()
                if any(btn_text.strip().startswith(letter) for letter in ['A', 'B', 'C', 'D', 'E']):
                    if 'Selanjutnya' not in btn_text and 'Sebelumnya' not in btn_text and 'Selesai' not in btn_text:
                        valid_answers.append(i)
                        log(f"[Step 6]   Valid answer button #{i}: '{btn_text[:30]}...'")

            if len(valid_answers) == 0:
                log(f"[Step 6] No valid answer buttons -> quiz done")
                break

            # Click random answer
            answer_idx = random.choice(valid_answers)
            chosen_text = await answer_buttons.nth(answer_idx).inner_text()
            log(f"[Step 6] Clicking answer #{answer_idx}: '{chosen_text[:40]}'")
            await answer_buttons.nth(answer_idx).click()
            question_count += 1

            # Random human-like delay before next action (2-6 seconds)
            think_time = random.uniform(2.0, 6.0)
            log(f"[Step 6] Answered. Thinking for {think_time:.1f}s...")
            await page.wait_for_timeout(int(think_time * 1000))

            # Check for "Selesai" button
            selesai_btn = page.locator("button:has-text('Selesai')")
            if await selesai_btn.count() > 0 and await selesai_btn.is_visible():
                log(f"[Step 6] Found 'Selesai' button -> Clicking to submit quiz...")
                await selesai_btn.click()
                log(f"[Step 6] Clicked 'Selesai'. Waiting for result page...")
                await wait_for_result(page)
                log(f"[Step 6] Wait complete. Taking screenshot...")
                break

            # Check for "Selanjutnya" button
            next_btn = page.locator("button:has-text('Selanjutnya')")
            if await next_btn.count() > 0 and await next_btn.is_visible():
                log(f"[Step 6] Found 'Selanjutnya' -> Clicking next...")
                await next_btn.click()
                log(f"[Step 6] Waiting 1.5s for next question...")
                await page.wait_for_timeout(1500)
            else:
                log(f"[Step 6] No 'Selanjutnya' button found")
                if await selesai_btn.count() > 0:
                    log(f"[Step 6] But 'Selesai' exists -> Clicking...")
                    await selesai_btn.click()
                    log(f"[Step 6] Clicked 'Selesai'. Waiting for result page...")
                    await wait_for_result(page)
                    log(f"[Step 6] Wait complete.")
                else:
                    log(f"[Step 6] No 'Selesai' either -> quiz done")
                break

        log(f"[Step 6] Total questions answered: {question_count}")

        # Step 7: Final screenshot
        log(f"[Step 7] Waiting 2s for page to settle...")
        await page.wait_for_timeout(2000)

        # Log page state before screenshot
        page_text = await page.inner_text("body")
        visible_lines = [l.strip() for l in page_text.split('\n') if l.strip()]
        log(f"[Step 7] Page has {len(visible_lines)} visible text lines")
        log(f"[Step 7] First 10 lines:")
        for line in visible_lines[:10]:
            log(f"[Step 7]   | {line}")

        screenshot_path = os.path.join(OUTPUT_DIR, f"{test_email}.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        log(f"[Step 7] Screenshot saved: {screenshot_path}")

        # Log identity info
        log(f"[Step 7] Looking for identity data on page...")
        found_identity = False
        for line in visible_lines:
            if '@' in line or line.startswith('08') or test_name in line:
                log(f"[Step 7]   Found: {line}")
                found_identity = True
        if not found_identity:
            log(f"[Step 7]   No identity data visible on page (expected - login required)")

        log(f"  RUN #{run_num} COMPLETE")
        return True

    except Exception as e:
        log(f"[ERROR] Run #{run_num} exception: {e}")
        # Take error screenshot
        try:
            err_ss = os.path.join(OUTPUT_DIR, f"{test_email}_error.png")
            await page.screenshot(path=err_ss, full_page=True)
            log(f"[ERROR] Error screenshot saved: {err_ss}")
        except:
            pass
        return False
    finally:
        await context.close()

async def main():
    # Clear log file
    with open(LOG_FILE, "w") as f:
        f.write(f"=== Quiz Automation Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log(f"Output dir: {OUTPUT_DIR}")
    log(f"Total runs: {TOTAL_RUNS}")
    log(f"Log file: {LOG_FILE}")

    async with async_playwright() as p:
        log(f"Launching stealth browser (bypass Cloudflare)...")
        log(f"[Step 1] Launching browser with stealth mode...")
        browser = await p.chromium.launch(
            headless=False,  # headless=False required to bypass Cloudflare Turnstile
            channel="chrome",  # use real Google Chrome, not "Chrome for Testing"
            args=STEALTH_ARGS + [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-translate",
                "--mute-audio",
                "--no-first-run",
            ]
        )
        log(f"Browser launched with stealth mode.")

        success = 0
        start_time = time.time()

        for i in range(1, TOTAL_RUNS + 1):
            run_start = time.time()
            try:
                result = await run_once(browser, i)
                elapsed = time.time() - run_start
                if result:
                    success += 1
                    log(f"Run #{i} took {elapsed:.1f}s - OK")
                else:
                    log(f"Run #{i} took {elapsed:.1f}s - FAILED")
            except Exception as e:
                elapsed = time.time() - run_start
                log(f"Run #{i} took {elapsed:.1f}s - EXCEPTION: {e}")

        total_time = time.time() - start_time
        await browser.close()

    log(f"")
    log(f"{'='*60}")
    log(f"  ALL DONE")
    log(f"  Success: {success}/{TOTAL_RUNS}")
    log(f"  Total time: {total_time:.1f}s")
    log(f"  Avg per run: {total_time/TOTAL_RUNS:.1f}s")
    log(f"  Screenshots: {OUTPUT_DIR}/")
    log(f"  Log file: {LOG_FILE}")
    log(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
