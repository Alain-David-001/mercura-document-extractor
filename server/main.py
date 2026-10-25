from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import pathlib
from google import genai
from google.genai import types

# Configure Gemini API
# Read GOOGLE_API_KEY from the environment; local value is in the ignored .env file.
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/example-static-pdf-upload")
def upload_to_gemini():
    pdf_path = os.path.join(os.path.dirname(__file__), "../specification_documents/specification_1.pdf")
    if not os.path.exists(pdf_path):
        return {"error": "PDF file not found"}

    try:
        filepath = pathlib.Path(pdf_path)
        prompt = (
            "Extract the project ID and project name from this construction specification. "
            "Return JSON with project_id and project_name. Use null for missing values. "
            "Do not confuse the project ID with a specification or LV number."
        )
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
            contents=[
                types.Part.from_bytes(
                    data=filepath.read_bytes(),
                    mime_type='application/pdf',
                ),
                prompt
            ]
        )
        return {"output": response.text}
    except Exception as e:
        return {"error": str(e)}
