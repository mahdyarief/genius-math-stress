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
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = "https://hrsmile2025.techconnect.co.id/c/genius-math-challenge"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "results")
TOTAL_RUNS = 1

# Parse args for instance ID (used by parallel runner)
parser = argparse.ArgumentParser()
parser.add_argument("--instance", type=int, default=0, help="Instance number for parallel runs")
args, _ = parser.parse_known_args()
INSTANCE_ID = args.instance
LOG_FILE = os.path.join(SCRIPT_DIR, f"quiz_log_{INSTANCE_ID:02d}.txt" if INSTANCE_ID else "quiz_log.txt")

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

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

def random_email(name):
    clean = name.lower().replace(" ", "").replace(".", "")
    # Short human-like suffix: 2-4 digit number
    num = random.randint(1, 9999)
    domains = ["gmail.com", "yahoo.com", "outlook.com", "mail.com"]
    return f"{clean}{num}@{random.choice(domains)}"

def random_phone():
    prefixes = ["0812", "0813", "0821", "0822", "0852", "0853", "0856", "0857", "0878", "0895", "0896"]
    return f"{random.choice(prefixes)}{''.join(random.choices(string.digits, k=8))}"

async def run_once(browser, run_num):
    log(f"{'='*60}")
    log(f"  RUN #{run_num} START")
    log(f"{'='*60}")

    # Create a fresh context for each run
    context = await browser.new_context(viewport={"width": 1280, "height": 1024})
    page = await context.new_page()

    try:
        # Step 1: Navigate
        log(f"[Step 1] Navigating to {BASE_URL}")
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        log(f"[Step 1] Page loaded. URL: {page.url}")

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
        test_email = random_email(test_name)
        test_phone = random_phone()
        log(f"[Step 3] Generated data:")
        log(f"         Name:  {test_name}")
        log(f"         Email: {test_email}")
        log(f"         Phone: {test_phone}")

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

        # Step 4: Submit form
        log(f"[Step 4] Looking for submit button 'Simpan & Lanjut'...")
        submit_btn = page.locator("button[type='submit']:has-text('Simpan & Lanjut')")
        if await submit_btn.count() > 0:
            log(f"[Step 4] Found submit button -> Clicking...")
            await submit_btn.click()
            log(f"[Step 4] Clicked 'Simpan & Lanjut'. Waiting 3s for quiz page...")
        else:
            log(f"[Step 4] ERROR: No submit button found!")
            return False

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
                log(f"[Step 6] Clicked 'Selesai'. Waiting 8s for result page...")
                await page.wait_for_timeout(8000)
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
                    log(f"[Step 6] Clicked 'Selesai'. Waiting 8s for result page...")
                    await page.wait_for_timeout(8000)
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
        log(f"Launching browser (headless, no-sandbox)...")
        log(f"[Step 1] Launching lightweight browser...")
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-sync",
                "--disable-translate",
                "--mute-audio",
                "--no-first-run",
                "--single-process",
            ]
        )
        log(f"Browser launched.")

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
