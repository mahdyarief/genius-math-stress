#!/usr/bin/env python3
"""
Controlled load-test harness -- Genius Math Challenge (hrsmile2025.techconnect.co.id)

PURPOSE (owner/operator only)
    Replay the real browser network flow against the live API to measure how the
    backend holds up under concurrent traffic. Built from the client JS + observed
    prod requests for slug "genius-math-challenge" (competition id 45).

FLOW (cookie-authenticated)
    GET  /api/c/<slug>/quiz             -> attempt state / questions
    POST /api/c/<slug>/enter             -> register identity (requiresLogin if no cookie)
    POST /api/competitions/45/answers    -> {questionId, answer}
    POST /api/competitions/45/submit     -> finalize
    POST /api/competitions/45/violations -> {cheat signal}

SAFETY (default gentle, never blind)
    --concurrency 4  --rps 1  --max-requests 10
    Honors HTTP 429 + Retry-After. Hard stop at --max-requests.
    --dry-run prints the plan without touching the network.

AUTH
    Cookie-based. Pass a Netscape cookie jar (-c from curl) or paste the
    amo_session value via --amo-session or env AMO_SESSION.
    Treat that cookie as a secret: rotate it after testing (logout / change pw).
"""

import argparse
import json
import os
import random
import sys
import threading
import time
from collections import Counter
from urllib import request, error

BASE = "https://hrsmile2025.techconnect.co.id"
SLUG = "genius-math-challenge"
COMPETITION_ID = "45"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0")

PROVINCES = ["Aceh", "Sumatera Utara", "Daerah Khusus Ibukota Jakarta", "Jawa Barat",
             "Jawa Tengah", "Jawa Timur", "Banten", "Bali", "Sulawesi Selatan", "Papua"]
AGE_RANGES = ["age_6_12", "age_13_17", "age_18_25", "age_26_35", "age_36_plus"]

_lock = threading.Lock()
_stats = {"sent": 0, "done": 0, "codes": Counter(), "retry_after": None}


def build_cookie_header(args):
    if args.amo_session:
        return "amo_session=" + args.amo_session
    if args.cookies:
        for line in open(args.cookies, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and len(line.split()) >= 7:
                parts = line.split()
                if parts[-2] == "amo_session":
                    return "amo_session=" + parts[-1]
        # fallback: join name=value pairs
        return line
    env = os.environ.get("AMO_SESSION")
    if env:
        return env if env.startswith("amo_session=") else "amo_session=" + env
    return ""


def headers(args, cookie_hdr):
    h = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": BASE,
        "referer": f"{BASE}/c/{SLUG}",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": UA,
    }
    if cookie_hdr:
        h["cookie"] = cookie_hdr
    return h


def make_payload(i):
    return {
        "fullName": f"LoadTest User {i}",
        "email": f"loadtest{i:05d}@example.com",
        "phone": f"0812{random.randint(10000000, 99999999)}",
        "province": random.choice(PROVINCES),
        "city": "Jakarta",
        "ageRange": random.choice(AGE_RANGES),
        "wonMathCompetition": random.choice([True, False]),
        "interestedInCompetition": random.choice([True, False]),
    }


def fire(method, url, body, h, args):
    data = json.dumps(body).encode() if body is not None else None
    req = request.Request(url, data=data, method=method, headers=h)
    try:
        with request.urlopen(req, timeout=args.timeout) as r:
            code = r.status
            txt = r.read().decode("utf-8", "replace")
    except error.HTTPError as e:
        code = e.code
        txt = e.read().decode("utf-8", "replace")
        if code == 429:
            with _lock:
                _stats["retry_after"] = e.headers.get("Retry-After")
    except Exception as e:  # noqa
        code = ("err:" + type(e).__name__)
        txt = str(e)[:120]

    with _lock:
        _stats["codes"][code] += 1
        _stats["done"] += 1
        if args.verbose and _stats["done"] <= 12:
            print(f"  [{code}] {method} {url.split(BASE)[1]} -> {txt[:140]}")


def build_flow(args):
    e = args.endpoint
    if e == "enter":
        return [("POST", f"{BASE}/api/c/{SLUG}/enter", None, "form")]
    if e == "quiz":
        return [("GET", f"{BASE}/api/c/{SLUG}/quiz", None, "get")]
    if e == "answers":
        return [("POST", f"{BASE}/api/competitions/{COMPETITION_ID}/answers",
                 {"questionId": random.randint(1, 5), "answer": random.choice("ABCD")}, "ans")]
    if e == "submit":
        return [("POST", f"{BASE}/api/competitions/{COMPETITION_ID}/submit", {}, "sub")]
    return []


def worker(args, cookie_hdr, flow, idx):
    h = headers(args, cookie_hdr)
    for method, url, body, kind in flow:
        b = make_payload(idx) if (kind == "form" and body is None) else body
        fire(method, url, b, h, args)
    with _lock:
        _stats["sent"] += 1
    # RPS pacing
    time.sleep(1.0 / max(args.rps, 0.01))


def run(args):
    cookie_hdr = build_cookie_header(args)
    flow = build_flow(args)

    if args.dry_run:
        print("== DRY RUN (no network) ==")
        print("cookie:", ("present:" + cookie_hdr[:24] + "...") if cookie_hdr else "(none -> will get requiresLogin)")
        print("flow:")
        for m, u, b, k in flow:
            print(f"   {m} {u.split(BASE)[1]}")
        print("sample body:", json.dumps(make_payload(0), indent=2))
        print("planned: concurrency=%d rps=%.2f max_requests=%d" %
              (args.concurrency, args.rps, args.max_requests))
        return

    if not cookie_hdr:
        print("[!] No cookie supplied. Endpoints require auth -> you'll likely get {\"requiresLogin\":true}. "
              "Run with --amo-session <value> or --cookies <jar>.")
        return

    threads = []
    start = time.time()
    for i in range(args.max_requests):
        t = threading.Thread(target=worker, args=(args, cookie_hdr, flow, i))
        threads.append(t)
    # rate-limited start: launch with concurrency cap
    running = []
    for t in threads:
        while len(running) >= args.concurrency:
            running = [r for r in running if r.is_alive()]
            time.sleep(0.05)
        t.start()
        running.append(t)
        time.sleep(1.0 / max(args.rps, 0.01))
    for t in threads:
        t.join()
    elapsed = time.time() - start

    print("\n==== RESULTS ====")
    print(f"endpoint      : {args.endpoint}")
    print(f"concurrency   : {args.concurrency}")
    print(f"target rps    : {args.rps:.2f}")
    print(f"requests sent : {_stats['sent']} / max {args.max_requests}")
    print(f"elapsed(s)    : {elapsed:.1f}")
    print(f"actual rps    : {_stats['done']/elapsed:.2f}" if elapsed > 0 else "n/a")
    print(f"status codes  : {dict(sorted(_stats['codes'].items(), key=lambda x: str(x[0])))}")
    if _stats["retry_after"]:
        print(f"[!] Server returned 429 with Retry-After={_stats['retry_after']} -> honor it, lower --rps.")


def main():
    p = argparse.ArgumentParser(description="Controlled load test -- Genius Math Challenge")
    p.add_argument("--amo-session", help="amo_session cookie value (keep secret; rotate after)")
    p.add_argument("--cookies", help="Netscape cookie jar file (curl -c)")
    p.add_argument("--endpoint", choices=["enter", "quiz", "answers", "submit"], default="enter")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--rps", type=float, default=1.0, help="requests/sec cap")
    p.add_argument("--max-requests", type=int, default=10)
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
