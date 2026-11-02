# LLM Document Extractor

Upload a PDF (an invoice or a product spec sheet) and get back validated, structured JSON. The service sends the PDF to Claude, constrains the answer to a Pydantic schema with structured outputs, and stores every result in a database.

**Stack:** Python, FastAPI, Claude API (`claude-opus-5-5`), SQLAlchemy (SQLite locally, PostgreSQL in production), S3, AWS Lambda (SAM), pytest, GitHub Actions.

## How it works

```
PDF upload ──> FastAPI ──> storage (local disk or S3)
                  │
                  └──> Claude: PDF as a document block + Pydantic schema (structured outputs)
                            │
                            └──> validated object ──> database row (status, JSON data, error)
```

- **Schemas:** `app/schemas.py` defines one Pydantic model per document type (`Invoice`, `SpecSheet`). Claude must answer in that shape, so the API never stores free-form text.
- **Failure handling:** refusals, truncated output, rate limits and API errors become a `failed` row with a readable error instead of a 500. A safety decline is retried on Anthropic's recommended fallback model server-side.
- **Storage:** `STORAGE_BACKEND=local` writes to `./uploads`; `STORAGE_BACKEND=s3` writes to `S3_BUCKET`.
- **Testable offline:** the extractor is a dependency, so tests swap in a stub and run without an API key.

## Run locally

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; use source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env            # then set ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs, or:

```bash
curl -F "file=@invoice.pdf" -F "document_type=invoice" http://localhost:8000/extractions
curl http://localhost:8000/extractions?document_type=invoice
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/extractions` | Upload a PDF (`file`) with `document_type` = `invoice` or `spec_sheet` |
| GET | `/extractions` | List results, newest first; filter with `document_type` |
| GET | `/extractions/{id}` | One result |
| GET | `/health` | Health check |

## Deploy to AWS Lambda

`template.yaml` creates an encrypted private S3 bucket and a Lambda function behind an HTTP API. The Anthropic key comes from Secrets Manager.

```bash
sam build
sam deploy --guided   # asks for AnthropicApiKeySecretArn and DatabaseUrl (e.g. an RDS PostgreSQL URL)
```

## Tests

```bash
pytest -q
```

Covers upload and storage, both schemas, failure recording, file validation, filtering, and the exact request sent to Claude (document block, schema, fallback).
