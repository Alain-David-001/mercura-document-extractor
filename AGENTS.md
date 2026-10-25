# Project guide for agents

## Goal

Help Alain deliver Mercura's full-stack take-home assignment: a usable application that extracts project metadata from construction specification PDFs with Gemini, then lets users review, edit, and comment on the results.

The deliverable should demonstrate full-stack understanding, maintainable code, asynchronous workflows, scalability awareness, and clear architectural tradeoffs. The original timebox is 2.5 hours; favor a complete, defensible solution and verify the remaining time with Alain when relevant.

## Working context

- Read `ASSIGNMENT.md` for the original requirements and `README.md` for setup. Inspect the code and Git history for current implementation state.
- The supplied stack is React/Vite/TypeScript and FastAPI/Python. Example PDFs are scanned documents; do not rely on embedded text being available.
- Architecture is still being discussed with Alain. Treat earlier proposals as proposals, and communicate significant tradeoffs before committing to a design.
- Keep dependencies local to `.venv` and `app/node_modules`. Keep API keys in ignored environment files and out of source, logs, and commits.
- Make small, coherent progress commits. Verify relevant behavior and clearly distinguish implemented functionality from planned work.
- Keep this guide focused on durable goals and conventions; put detailed architecture and progress notes in separate documents when needed.
