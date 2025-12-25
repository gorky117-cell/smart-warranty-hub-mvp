# Golden Path Test Checklist (SWH MVP)

Pre-deploy manual + automated checklist for Smart Warranty Hub (SWH).

## 0) Preconditions

- Backend running on `http://127.0.0.1:8000`
- Sample inputs:
  - `user_id`: `user-1`
  - `warranty_id`: `wty_55f018de`

## 1) UI Flow Checks (Customer Care)

Open: `http://127.0.0.1:8000/ui/neo-dashboard`

### Step 1: Load Product Details
- Enter `user-1` and `wty_55f018de`
- Click **Load product details**
- Expected (PASS):
  - Summary line shows product label + ID (e.g., `Microwave - Acmeco ZX-100 (wty_55f018de)`)
  - Status chips appear (Status / Health / Time left)
  - No JS errors in console

### Step 2: Details & Care (Summary Toggle)
- Click **See full summary**
- Expected (PASS):
  - ONLY Step 2 expands/collapses
  - Step 3 and Step 4 remain visible and unaffected
  - Accordions show content when expanded

### Step 3: Add Your Bill
- Choose **Upload file**
- Upload a small image or PDF
- Expected (PASS):
  - Upload completes OR a friendly OCR message appears
  - No layout break or console errors

### Step 4: Usage & Health
- Confirm Step 4 stays visible regardless of Step 2 toggle
- Use the quick log controls to save a note
- Expected (PASS):
  - Context line shows product label and warranty id
  - No UI freeze or JS errors

## 2) Notifications (Customer)

- Click the bell icon
- Expected (PASS):
  - Drawer opens
  - Messages show product label + ID (not just raw warranty id)
  - Mark read removes items and badge updates

## 3) Warranty Details + Modal

In Step 2:
- Check **Coverage / Terms**, **Exclusions**, **Claim steps**
- Click **Open full-screen** (only when long content)
- Expected (PASS):
  - Formatted text (not JSON)
  - Copy button works
  - Raw JSON hidden unless `?debug=1`

## 4) Backend Checks (curl)

Run from terminal (copy/paste):

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

curl -i -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" \
  -c cookies.txt

curl -i http://127.0.0.1:8000/health/full
curl -i http://127.0.0.1:8000/health/ocr
curl -i http://127.0.0.1:8000/health/llm
curl -i http://127.0.0.1:8000/health/predictive
curl -i http://127.0.0.1:8000/warranties/wty_55f018de -b cookies.txt
echo '{"warranty_id":"wty_55f018de"}' > payload.json
curl -i -X POST http://127.0.0.1:8000/warranties/summary \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  --data-binary "@payload.json"
```

Note: `/auth/login` returns `303` and sets `access_token` in cookies; use `-b cookies.txt` for authenticated calls.

Artifact upload (replace PATH_TO_FILE):
```bash
curl -i -X POST http://127.0.0.1:8000/artifacts/upload \
  -b cookies.txt \
  -F "file=@PATH_TO_FILE" \
  -F "type=invoice"
```

Automated login + upload (PowerShell):
```powershell
powershell -ExecutionPolicy Bypass -File scripts/test_upload.ps1
```
Note: Server must be running on http://127.0.0.1:8000 and the file must exist at
`sample_invoice.pdf` in the repo root, or pass a full path.
To upload a different file:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/test_upload.ps1 -FilePath "C:\path\to\invoice.pdf"
```
If login needs credentials, set env vars before running:
```powershell
$env:SWH_USERNAME="admin"
$env:SWH_PASSWORD="admin123"
powershell -ExecutionPolicy Bypass -File scripts/test_upload.ps1
```

Job status + summary:
```bash
# Replace JOB_ID from the upload response
curl -i http://127.0.0.1:8000/jobs/JOB_ID -b cookies.txt

# Manually trigger processing for a warranty (optional)
curl -i -X POST http://127.0.0.1:8000/warranties/wty_55f018de/process \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"artifact_id":"art_example"}'

# Fetch best available summary
curl -i http://127.0.0.1:8000/warranties/wty_55f018de/summary -b cookies.txt
```

Expected (PASS):
- `/health/full` returns `status: ok` or `status: degraded` with structured checks
- `/health/ocr` returns `ok: true` if PaddleOCR installed
- Warranty endpoints return JSON and 200
 - `/jobs/{job_id}` shows status progression to `done`
 - `/warranties/{id}/summary` returns a summary (template if LLM disabled)

Optional (fresh DB only):
```bash
python scripts/sqlite_migrate.py
```

## 5) PASS / FAIL Criteria

PASS if:
- All UI steps work without console errors
- Step 2 toggles independently (Step 3/4 always visible)
- Notifications show product label + ID and mark-read works
- Warranty modal shows formatted text (no raw JSON unless debug)
- All curl checks return 200 and valid JSON

FAIL if:
- Any UI step freezes or throws JS errors
- Step 3/4 disappear when Step 2 toggles
- Notifications show only raw `wty_...` ids
- Warranty modal shows raw JSON by default
- Any critical endpoint returns 404/500

## 6) Degraded Mode (OCR unavailable)

If `/health/ocr` returns `ok: false`:
- Invoice upload should still work.
- UI must show: "OCR unavailable — using manual entry / limited extraction".
- Mark OCR checks as FAIL but non-blocking; rest of golden path must still PASS.

## 7) Logs to Check on Failure

Backend (uvicorn output):
- Any `ERROR` or stack traces during:
  - `/warranties/{id}`
  - `/health/ocr`
  - `/artifacts/upload`
  - `/behaviour/next-question`

Frontend:
- Browser DevTools Console: no red errors
- Network tab: no 404/500 for `/warranties/`, `/advisories/`, `/predictive/score`, `/notifications`

## 8) Run Log Template

```
Run #:
Date/Time:
Environment: local | railway
Step 1: PASS/FAIL
Step 2: PASS/FAIL
Step 3: PASS/FAIL
Step 4: PASS/FAIL
Notifications: PASS/FAIL
Warranty modal: PASS/FAIL
Health checks: PASS/FAIL
Notes:
```
