# Genius Math Challenge — Controlled Load-Test Harness

Stress-test terkontrol untuk endpoint kompetisi **Genius Math Challenge**
(`hrsmile2025.techconnect.co.id/c/genius-math-challenge`). Dibuat untuk
pemilik/operator situs guna mengukur ketahanan backend di bawah lalu lintas
bersamaan. Bukan bot pemenang kompetisi dan bukan credential harvester.

## Endpoint yang diuji (rekonstruksi dari client JS + observasi prod)

| Method | Path | Keterangan |
|--------|------|------------|
| GET  | `/api/c/{slug}/quiz` | Ambil state attempt / soal. Anonim → `{"status":"not_entered"}`; tanpa cookie → `{"requiresLogin":true}`. |
| POST | `/api/c/{slug}/enter` | Daftar identitas. Body: `{fullName,email,phone,province,city,ageRange,wonMathCompetition,interestedInCompetition}`. `province` = nama provinsi (bukan code), `ageRange` = enum `age_6_12|age_13_17|age_18_25|age_26_35|age_36_plus`. |
| POST | `/api/competitions/45/answers` | Simpan jawaban. Body `{questionId, answer}`. |
| POST | `/api/competitions/45/submit` | Finalisasi attempt. Body kosong (content-length 0). |
| POST | `/api/competitions/45/violations` | Sinyal kecurangan. |

- `slug` = `genius-math-challenge`
- Competition id = `45`
- Auth **cookie-based**: `amo_session=...` (didapat setelah login di browser).

## Keamanan

- Cookie session = akses penuh ke akun. **Jangan bagi/commit ke VCS.** Rotate
  (logout / ganti password) setelah selesai testing.
- Script tidak menyimpan cookie ke disk saat dijalankan dengan `--amo-session`.
- Endpoint write (enter/answers/submit) **mengonsumsi attempt** (maks 3/akun).
  Jangan jalankan terhadap akun produksi yang ingin dipertahankan skornya.

## Cara jalanin

Butuh Python 3 (stdlib only, tidak ada dependency):

```bash
# Dry-run: cetak rencana tanpa menyentuh network
python3 stress_genius_math.py --dry-run --endpoint submit

# Read-only: GET /quiz dengan cookie (aman, tidak mengubah state)
python3 stress_genius_math.py --endpoint quiz \
  --amo-session "PASTE_AMO_SESSION_HERE" \
  --max-requests 1

# Stress endpoint enter (write — butuh akun test khusus!)
python3 stress_genius_math.py --endpoint enter \
  --amo-session "PASTE_AMO_SESSION_HERE" \
  --concurrency 4 --rps 2 --max-requests 50 --verbose

# Gunakan cookie jar dari curl (-c) sebagai ganti --amo-session
curl -c jar.txt -b ... '.../login'
python3 stress_genius_math.py --endpoint answers --cookies jar.txt
```

## Parameter

| Flag | Default | Fungsi |
|------|---------|--------|
| `--endpoint` | `enter` | `enter` / `quiz` / `answers` / `submit` |
| `--amo-session` | – | Nilai `amo_session` (atau via env `AMO_SESSION`) |
| `--cookies` | – | File cookie jar Netscape (curl -c) |
| `--concurrency` | 4 | Thread paralel maksimum |
| `--rps` | 1.0 | Batas request/detik |
| `--max-requests` | 10 | Hard stop total request |
| `--timeout` | 15.0 | Timeout per request (detik) |
| `--verbose` | off | Cetak respons tiap request |
| `--dry-run` | off | Cetak rencana, tanpa network |

## Safety built-in

- RPS cap + hard stop `--max-requests`.
- Menghormati HTTP 429 + header `Retry-After` (cetak peringatan).
- Default sangat pelan (conc 4, rps 1, max 10) — naikkan bertahap.

## Catatan reverse-engineering

- `GET /quiz` tanpa/auth → `{"status":"not_entered"}`; dengan cookie tapi belum
  main → bentuk soal; sudah main → state attempt (skor, tier, attemptsUsed).
- `enter` wajib field lengkap; `province` harus **nama** ("Aceh", "Daerah
  Khusus Ibukota Jakarta", dst), `ageRange` enum `age_*`.
- `/api/competitions/{id}/...` pakai **competition id numerik** (45), bukan slug.
