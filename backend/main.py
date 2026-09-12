"""
main.py
=======

FastAPI web server for the RAG AI Chatbot.

Endpoints:
  GET  /            -> simple "alive" check
  POST /upload      -> receive a PDF, index it into ChromaDB
  GET  /documents   -> list uploaded documents
  POST /ask         -> ask a question about the uploaded documents
"""

import os
import shutil
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database
import rag

# ---- Where uploaded PDFs are saved ----
# In local dev: backend/uploads. In production (Docker): /data/uploads
# (Hugging Face Spaces keeps /data between restarts).
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---- Create the FastAPI app ----
app = FastAPI(title="RAG AI Chatbot API")

# Allow the React frontend (http://localhost:5173) to call this API.
# In real deployments you would restrict this list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Make sure the SQLite table exists when the server starts.
database.initialize_database()


# ---- Request/response models ----

class AskRequest(BaseModel):
    """JSON body expected by POST /ask."""
    question: str


# ---- Endpoints ----

@app.get("/")
def home():
    """Serve the React app in production, or a health message in dev."""
    # When a built frontend exists (deployment), "/" should show the app.
    if os.path.exists(FRONTEND_INDEX):
        return FileResponse(FRONTEND_INDEX)
    return {"message": "RAG AI Chatbot API is running"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Receive a PDF, save it to uploads/, extract text, chunk it,
    embed it and store it in ChromaDB. Also logs it in SQLite.
    """

    # Make sure a file was actually sent.
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded. Please choose a PDF file.")

    # Only allow PDFs.
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF files are allowed.",
        )

    # Create a unique filename so two files with the same name do not clash.
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)

    # Save the uploaded bytes to disk.
    with open(save_path, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    # Index the PDF (extract -> chunk -> embed -> store in ChromaDB).
    try:
        num_chunks = rag.store_document(filename=file.filename, pdf_path=save_path)
    except ValueError as error:
        # No text inside the PDF.
        os.remove(save_path)  # clean up the useless file
        raise HTTPException(status_code=422, detail=str(error))
    except Exception as error:
        # Gemini / ChromaDB errors - do not leak internals.
        os.remove(save_path)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to index the PDF: {type(error).__name__}. Please try again later.",
        )

    # Log the document in SQLite.
    row_id, row = database.add_document(filename=file.filename)

    return {
        "message": "PDF uploaded and indexed successfully",
        "filename": file.filename,
        "chunks": num_chunks,
        "document_id": row_id,
    }


@app.get("/documents")
def list_documents():
    """Return every PDF that has been indexed."""
    return {"documents": database.get_documents()}


@app.post("/ask")
def ask_question(request: AskRequest):
    """
    RAG question answering:
      question -> embedding -> Chroma similarity search -> context -> Gemini -> answer
    """
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Retrieve the most relevant chunks from ChromaDB.
    try:
        contexts = rag.search_documents(question)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not search the documents: {type(error).__name__}. Please try again.",
        )

    # Nothing relevant found - be honest about it instead of letting
    # the model guess (this is the core "no hallucination" rule).
    if not contexts:
        return {
            "answer": "I couldn't find that information in the uploaded document.",
            "sources": [],
        }

    # Ask Gemini to answer using only the retrieved context.
    try:
        answer, sources = rag.generate_answer(question, contexts)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"The AI model could not answer right now: {type(error).__name__}. Please try again.",
        )

    return {"answer": answer, "sources": sources}


# ---- Serve the built React frontend (production only) ----
# In development the React app runs on Vite (port 5173) and talks to this
# API on port 8000. When deployed, Vite is NOT running: we serve the
# pre-built React files directly from FastAPI, so the whole application
# lives on a single URL. This block is skipped when no build exists yet.
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
FRONTEND_INDEX = os.path.join(STATIC_DIR, "index.html")

if os.path.exists(FRONTEND_INDEX):
    # CSS / JS bundles created by "npm run build".
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(STATIC_DIR, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        # Return a real file if asked (e.g. /favicon.svg), otherwise
        # always send index.html so React handles the navigation.
        requested = os.path.join(STATIC_DIR, full_path)
        if full_path and os.path.isfile(requested):
            return FileResponse(requested)
        return FileResponse(FRONTEND_INDEX)