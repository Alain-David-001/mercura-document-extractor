# Project guide for agents

## Goal

Help Alain deliver Mercura's full-stack take-home assignment: a usable application that extracts project metadata from construction specification PDFs with Gemini, then lets users review, edit, and comment on the results.

The deliverable should demonstrate full-stack understanding, maintainable code, asynchronous workflows, scalability awareness, and clear architectural tradeoffs. The original timebox is 2.5 hours; favor a complete, defensible solution and verify the remaining time with Alain when relevant.

## Working context

- Read `ASSIGNMENT.md` for the original requirements and `README.md` for setup. Inspect the code and Git history for current implementation state.
- The supplied stack is React/Vite/TypeScript and FastAPI/Python. Example PDFs are scanned documents; do not rely on embedded text being available.
- Read `docs/ARCHITECTURE.md` for the agreed MVP direction, both diagrams, and implementation boundaries. The MVP is implemented; discuss significant departures and keep that document current as details are decided.
- Read `docs/MVP_PLAN.md` for the implemented UI, API, database, file storage, worker, and verification scope discussed with Alain.
- Keep dependencies local to `.venv` and `app/node_modules`. Keep API keys in ignored environment files and out of source, logs, and commits.
- Make small, coherent progress commits. Verify relevant behavior and clearly distinguish implemented functionality from planned work.
- Keep this guide focused on durable goals and conventions; put detailed architecture and progress notes in separate documents when needed.

## Current working agreement

Keep changes committed locally and defer pushing until the project is ready. The worker defaults to one active document; concurrency is configurable. Use the README for startup and tests, and the architecture document for tradeoffs and verification limits.
