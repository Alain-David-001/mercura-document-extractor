# Mercura Document Extractor

A full-stack take-home project for extracting project IDs and names from construction specification PDFs using Google Gemini. The target workflow includes multiple uploads, background processing, editable results, and comments.

Built with React, TypeScript, and Vite on the frontend, and Python/FastAPI on the backend. Currently, the health-check UI and static Gemini extraction example work; the full workflow is still to be built.

See [the original assignment](ASSIGNMENT.md) for requirements, [the architecture](docs/ARCHITECTURE.md) for the design and diagrams, and [the agent guide](AGENTS.md) for project goals.

## Run locally

Requires Python 3.12 and Node.js 20.19+ or 22.12+.

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.lock.txt
cp server/.env.example server/.env  # First setup only; set GOOGLE_API_KEY inside.
.venv/bin/python -m uvicorn main:app --app-dir server --env-file server/.env --reload
```

In another terminal:

```bash
cd app
npm ci
npm run dev
```

Open [the frontend](http://localhost:5173) or [the API docs](http://127.0.0.1:8000/docs). Keep credentials in the ignored `server/.env` file. The Gemini model can be configured with `GEMINI_MODEL`.

## Checks

Run `npm run build` and `npm run lint` from `app/`. Backend dependencies are pinned in `server/requirements.lock.txt`; direct dependencies are listed in `server/requirements.txt`.
