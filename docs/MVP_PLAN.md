# MVP implementation plan

This records the implemented MVP scope. See [the architecture](ARCHITECTURE.md) for the design, implementation notes, and verified limits.

## UI

One document workspace:

- Upload area: select or drop multiple PDFs.
- Document list: filename, processing stage, and clear success/error states. Poll while work is pending.
- Selected document panel: editable Project ID and Project Name, an explicit Save changes button, and confirmation or error feedback.
- Comments: a persisted chronological list with a text box and Add comment button.
- Original PDF: an Open/download PDF link.
- Delete: remove the selected PDF, extracted data, edits, job, and comments after confirmation.
- Failed extraction: a readable error and Retry button.
- Worker availability: a warning when processing is unavailable; uploads and existing document review remain available.

Other documents remain usable while processing continues. Editing becomes available once extraction finishes. An explicit save avoids unnecessary autosave complexity.

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/documents` | Upload one PDF, persist it, queue extraction, return `202` with its document ID |
| `GET /api/worker-status` | Report whether a worker heartbeat is recent |
| `GET /api/documents` | List documents and processing summaries |
| `GET /api/documents/{id}` | Get results, original extracted values, status, and comments |
| `PATCH /api/documents/{id}` | Save reviewed project ID and project name |
| `POST /api/documents/{id}/comments` | Add a comment |
| `GET /api/documents/{id}/file` | Serve the original PDF |
| `DELETE /api/documents/{id}` | Delete one document and its associated data and stored PDF |
| `POST /api/documents/{id}/retry` | Queue another attempt for a failed extraction |

The browser sends one upload request per selected file, with bounded upload concurrency. A failed file does not undo successful uploads.

## SQLite: four tables

| Table | Stores |
|---|---|
| `documents` | Internal ID, original filename, storage key, size/page count, original AI values, current editable values, revision, and timestamps |
| `extraction_jobs` | Document reference, queued/processing/completed/failed state, processing phase, attempts, progress, error, claim/lease information, and timestamps |
| `comments` | Comment ID, document reference, text, and creation time |
| `worker_heartbeats` | Process registration and last heartbeat time, independent of job leases |

The internal document ID is separate from the Project ID extracted from the PDF.

AI values remain available after edits. Revision checks prevent stale saves from silently overwriting newer changes. No user/accounts table for this local MVP.

## PDF storage

- Keep PDFs under ignored `server/data/uploads/`.
- Use generated document IDs for stored filenames; retain the original filename in SQLite.
- Validate PDF content and size, write through a temporary file, then finalize it.
- Serve files through the API using the document record, rather than exposing arbitrary filesystem paths.
- Store the database under ignored `server/data/` as well.

## Worker

One separate worker process, configured for two active documents by default. The processing limit remains configurable from 1 to 8.

It atomically claims jobs, reads the stored PDF, requests schema-validated Gemini output, and persists results or failure. Expiring claims and heartbeats support recovery after interruption; stale attempts cannot overwrite newer results.

For large PDFs, split into chunks bounded by pages and bytes, process chunks sequentially per document, and report completed chunks. Conflicting project metadata should be flagged for review. A pending Gemini call shows its stage, without a fabricated percentage.

## Delivery checks

Verify upload → extraction → edit → comment → restart persistence, malformed PDFs, provider failures, retry, and interrupted-job recovery. Run frontend build/lint and check the complete flow in the browser.
