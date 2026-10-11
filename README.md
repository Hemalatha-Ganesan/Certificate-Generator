# Bulk Certificate Generator API

A backend API that accepts a list of recipients, generates a PDF certificate for each one from a single predefined template, tracks the progress of the job, and lets the client download and verify the results.

**Stack:** Python 3.10+, FastAPI, SQLAlchemy, SQLite, ReportLab, pytest.

## Features

- Bulk generation: one request, up to 1000 recipients
- Input validation with clear `422` errors
- Background processing with live progress tracking
- Per-certificate failure isolation: one failure never stops the rest
- Download a single PDF or all PDFs as a zip
- Long names and course titles shrink automatically to fit the template
- Every certificate carries a unique ID and a QR code, and a public `/verify` endpoint confirms it is genuine

## Setup

```bash
git clone https://github.com/<your-username>/Certificate-Generator.git
cd Certificate-Generator

python -m venv venv
# Windows:   venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

pip install -r requirements.txt
```

## Run the application

```bash
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Interactive API docs (Swagger UI) are at `http://127.0.0.1:8000/docs`.
The SQLite database (`certs.db`) is created automatically on first start.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PUBLIC_BASE_URL` | `http://127.0.0.1:8000` | Address encoded in each certificate's QR code. Set it to your public address when deployed. |

Example (Windows PowerShell): `$env:PUBLIC_BASE_URL="https://certs.example.com"`

## Run the tests

```bash
pytest -v
```

Tests use an in-memory database and a temporary output folder, so they never touch real data.

## API usage

### 1. Submit a generation request

`POST /jobs` returns `202 Accepted` immediately with a job id; the certificates are generated in the background.

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d @sample_request.json
```

(On Windows PowerShell use `curl.exe` instead of `curl`.)

Response:

```json
{ "job_id": "a5068985-23b0-43e8-850e-b936a2b75d0b", "status": "pending", "total": 2 }
```

Validation rules: `course_title` and `date` are required; `recipients` must contain 1 to 1000 items; each recipient needs a non-blank `name` and a valid `email`. Invalid input returns `422` with details.

### 2. Check progress and results

`GET /jobs/{job_id}`

```bash
curl http://127.0.0.1:8000/jobs/<job_id>
```

Returns the job status, `total`, `success_count`, `failed_count`, and a per-recipient list with each certificate's `id`, `status` (`pending`, `success` or `failed`) and `error_message` for failures.

Job status values: `pending` -> `processing` -> `completed` (all succeeded) or `completed_with_errors` (at least one failed).

### 3. Retrieve generated certificates

- One certificate (PDF): `GET /jobs/{job_id}/certificates/{certificate_id}`
- All successful certificates as a zip: `GET /jobs/{job_id}/download`

```bash
curl -o certificates.zip http://127.0.0.1:8000/jobs/<job_id>/download
```

Errors: `404` if the job or certificate does not exist (or does not belong to that job); `409` if the certificate failed or nothing is ready yet.

### 4. Verify a certificate

`GET /verify/{certificate_id}` confirms that a certificate was really issued. The ID is printed at the bottom of every PDF, and the QR code in the corner links straight to this endpoint.

```bash
curl http://127.0.0.1:8000/verify/<certificate_id>
```

```json
{
  "valid": true,
  "certificate_id": "e163d3f1-552a-49a5-b4d7-2c887acc6db5",
  "name": "Hemalatha",
  "course_title": "Python Backend Development",
  "date": "11 October 2026"
}
```

Unknown or failed certificates return `404`. The recipient's email is never exposed.

## Project structure

```
app/
  main.py        API endpoints
  database.py    SQLAlchemy engine and session
  models.py      Job and Certificate tables
  schemas.py     Request/response models and validation
  generator.py   PDF certificate template (ReportLab)
  service.py     Bulk job processing and failure handling
tests/
  test_api.py    Test suite
sample_request.json   Example request body
```

## Design decisions

- **Background processing (FastAPI `BackgroundTasks`).** A request can contain up to 1000 recipients, so generating everything inside the request would be slow and could time out. The API stores the job, returns `202` right away, and the client polls `GET /jobs/{id}`. `BackgroundTasks` needs no extra infrastructure, which keeps the project simple to run and review.
  **Trade-off:** jobs run inside the web process, so a server restart during a job would leave it unfinished. In production I would move to a task queue such as Celery or RQ with Redis so jobs survive restarts and can scale across workers.
- **Per-certificate failure isolation.** Each recipient is processed in its own `try/except`. A failure is recorded on that certificate (`status=failed` plus the error message) and the loop continues, so one bad certificate never blocks the others. The final job status is `completed_with_errors` if any failed.
- **Two-level validation.** Bad input (empty list, invalid email, blank name) is rejected up front with `422` by Pydantic. Failures that happen later, during PDF generation, are handled per certificate as above.
- **Two tables.** `Job` (one per request, with counters for fast progress reads) and `Certificate` (one per recipient, with its own status and error). Counters are committed after every certificate, so progress is visible while the job runs.
- **Single fixed template.** All layout lives in one function, `generate_certificate`, which takes plain values rather than database objects. This keeps it easy to test and to swap.
- **Long names fit the template.** The name and course title shrink automatically (down to 8pt) so they never run past the certificate border.
- **Verifiable certificates.** Each PDF carries its unique ID and a QR code, and `/verify/{id}` confirms it. Only successful certificates verify, personal data such as email is never exposed, and IDs are random UUIDs, so they cannot be guessed. The QR code's base address comes from the `PUBLIC_BASE_URL` environment variable, so a deployed instance prints its real public URL.
- **Safe file handling.** Files are stored as `certificates/<job_id>/<certificate_id>.pdf` using UUIDs, not recipient names, which avoids duplicate-name collisions and unsafe characters. Zip entry names are sanitised, and a certificate can only be fetched through the job it belongs to.
- **Batch size cap of 1000** protects the server from oversized requests.
- **SQLite** is used for easy setup. Switching to PostgreSQL only requires changing `DATABASE_URL` in `app/database.py`.

## Known limitations

- Background jobs are not persisted across server restarts (see trade-off above).
- No authentication or rate limiting. The verify endpoint is public by design.
