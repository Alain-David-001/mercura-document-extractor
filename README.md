# Mercura Document Extractor

Extract project IDs and names from construction specification PDFs with Google Gemini, then review the results, make corrections, and add comments.

React/TypeScript and FastAPI provide the workspace and API. A separate worker processes a durable SQLite queue; original PDFs and results stay on local disk. Multiple uploads, processing states, retries, large-document chunking, and PDF access are included.

[Assignment](ASSIGNMENT.md) · [Architecture](docs/ARCHITECTURE.md) · [Implemented features](docs/MVP_PLAN.md) · [Agent guide](AGENTS.md)

## Setup

Requires Python 3.12 and Node.js 20.19+ or 22.12+. Run from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.lock.txt
cp server/.env.example server/.env  # First setup only; preserve any existing .env.
# Set GOOGLE_API_KEY inside server/.env.
cd app
npm ci
```

## Run

Use three terminals, starting from the repository root:

```bash
# API
.venv/bin/python -m uvicorn main:app --app-dir server --env-file server/.env --reload
```

```bash
# Background worker (required for extraction)
.venv/bin/python server/worker.py
```

```bash
# Frontend
cd app
npm run dev
```

Open [the workspace](http://localhost:5173) or [API docs](http://127.0.0.1:8000/docs). Upload PDFs, wait for extraction, save reviewed project fields, and add comments. Use Delete beside Open PDF to remove a selected upload, its extracted data, edits, and comments after confirmation. Each file is queued independently. The UI refreshes status automatically. A worker heartbeat reports availability: if the worker stops, uploads stay saved and a warning appears. The worker reports every 5 seconds; missed heartbeats expire after 20 seconds, plus the UI polling delay. This detects outages; it does not automatically restart the worker.

## Test documents

The [specification_documents](specification_documents/README.md) folder contains the two original scanned samples and synthetic 500-, 700-, and 1,000-page PDFs for testing chunking and concurrent processing.

## Configuration and limits

Set these in ignored `server/.env`:

| Variable | Default |
|---|---|
| `GOOGLE_API_KEY` | Required for the worker |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` |
| `WORKER_CONCURRENCY` | `2`; configurable from `1` to `8` |
| `DATA_DIR` | `server/data/`, resolved from the backend code location |

PDF limits: 100 MiB and 5,000 pages per file; no password-protected PDFs. Chunks are at most 40 pages and 18 MiB. The queue accepts up to 200 pending/active uploads. A single page exceeding the chunk byte limit is rejected. Files, SQLite data, credentials, and temporary job files are local and excluded from Git.

The application has no authentication and stores data locally. See the architecture document for restart recovery, extraction behavior, and verification limits.

## Checks

```bash
.venv/bin/python -m pip install -r server/requirements-dev.txt
.venv/bin/python -m pytest server/tests -q
cd app
npm run build
npm run lint
```

Backend tests use temporary databases and fake provider responses, without Gemini calls or changes to your workspace. Direct dependencies are listed in `server/requirements.txt`; the runtime lock file pins the resolved environment.
