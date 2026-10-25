# Test PDFs

| File | Pages | Purpose |
|---|---:|---|
| `specification_1.pdf` | 6 | Original scanned sample |
| `specification_2.pdf` | 5 | Original scanned sample |
| `specification_500_pages.pdf` | 500 | Repeated pages from specification_1; normally 13 chunks |
| `specification_700_pages.pdf` | 700 | Repeated pages from specification_2; normally 18 chunks |
| `specification_1000_pages.pdf` | 1,000 | Repeated pages from specification_1; normally 25 chunks |

The large PDFs are synthetic load-test fixtures. Reused images keep their file sizes small. Use them to test chunking, progress, queueing, and concurrent documents; they do not represent diverse thousand-page content or large-byte uploads. Uploads trigger real Gemini requests when the worker is running.
