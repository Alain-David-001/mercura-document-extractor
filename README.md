# Mercura – Full-Stack Take-Home Challenge

Welcome! You've advanced to the stage where we want to understand how you approach a real-world full-stack engineering problem.

## Mission

Your task is to **design and build a simple web application** that allows users to upload PDF documents from construction specifications and extract project-related information using **Google Gemini**.

We want to see how you handle async workflows, manage scale, and think about maintainable architecture — all in the context of a realistic product feature.

---

## What to Build

Imagine you're part of a team that works on digitalizing construction specification documents.

Your goal is to:

- Let users upload one or more **PDFs** containing construction specs
- Extract structured information using Gemini, such as:
  - `Project ID`
  - `Project Name`
- Display the extracted information in a suitable user interface
- Let users **edit the extracted info** and **add comments**
- Ensure the UI remains **responsive and usable during the processing of specification files**
- Allow **multiple documents** to be uploaded and processed at the same time

You can think of this as a **mini production system**. What would you build if you were owning this feature?


- Process large documents (100s–1000s of pages) efficiently

---

## Tech Stack Provided

To help you get started, we provide:

- **Frontend**: React (Vite) + TypeScript  
- **Backend**: FastAPI + Python  
- **Gemini API Access**: API key and example PDF upload is provided in  `main.py`

You're free to use additional libraries or (AI) tools where you see fit. The goal is to showcase **how you tackle the problem**.

### Frontend

You can start the react frontend with:
````
cd app
npm ci
npm run dev
````

### Server

Use Python 3.12 and a project-local virtual environment. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.lock.txt
# On a fresh checkout, copy server/.env.example to server/.env and set GOOGLE_API_KEY.
.venv/bin/python -m uvicorn main:app --app-dir server --env-file server/.env --reload
```

The backend runs at http://127.0.0.1:8000, with API documentation at http://127.0.0.1:8000/docs.
The frontend requires Node.js 20.19+ or 22.12+ and normally runs at http://localhost:5173.

`server/requirements.txt` records direct dependencies; `server/requirements.lock.txt` pins the complete tested environment. The virtual environment, frontend dependencies, and local credentials are ignored by Git.

Frontend checks: run `npm run build` and `npm run lint` from `app/`.

The file `main.py` contains an example using a static PDF and a Gemini prompt. You can use this as a reference to build your own dynamic endpoint for PDF upload and AI extraction.

---

## How It Should Work

You decide the architecture and look of the app, but here are some key requirements:

- PDF uploads should **not block** the server or UI.
- The application needs to process large documents (100s–1000s of pages) efficiently. Large PDFs may take **minutes** — plan for that.

You can find example PDFs in the `specification_documents` dir.

Data should be persisted to local files or lightweight DB. That is up to you!


- Users should always have a clear view of:
  - What is processing
  - What is completed
  - If any errors occurred

Use Google Gemini to extract data from uploaded PDFs. You can prompt however you like.


## What We're Looking For

### Must-Haves

- Clean, maintainable code
- Clear, responsive, type-safe frontend UI
- Scalable and performant processing

### Nice-to-Haves

- Tests for key components
- Observability (e.g. logs, error handling)
- Data persistence (DB or file-based)
- Basic retry / error handling
- PDF preview or download options

## How We'll Evaluate

After your challenge, we’ll schedule a short session to discuss:

- Your approach and decisions
- What you’d do differently in production

We'll assess your submission based on:

- **Technical Execution**  
  Is the code functional and well-structured?

- **Architecture & Design**  
  Does the solution scale well? Can you explain tradeoffs.

- **Communication**  
  Can you clearly describe your design and decisions?

This challenge isn't about building *everything* — it's about how you **approach** real-world engineering problems.

---

We’re excited to see how you approach this — happy building!


