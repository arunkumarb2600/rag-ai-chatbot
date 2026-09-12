# RAG AI Chatbot

A beginner-friendly **RAG (Retrieval-Augmented Generation)** chatbot. Upload a PDF, ask questions in natural language, and Gemini answers using **only** the content of your document — no hallucinations, no unrelated facts.

---

## 1. What this project does

1. You upload a PDF.
2. The backend extracts the text, splits it into small chunks, and turns each chunk into an **embedding** (a list of numbers that captures meaning).
3. The chunks + embeddings are stored in **ChromaDB** (a local vector database on disk).
4. You ask a question.
5. The question is turned into an embedding too, and ChromaDB finds the 4 most similar chunks (semantic search).
6. Those chunks are inserted into a prompt, and **Gemini** answers using them.
7. The answer (with sources) is displayed in a React chat UI.

---

## 2. RAG architecture

```
PDF
 ↓
Text Extraction (pypdf)
 ↓
Text Chunking (LangChain, 1000 chars / 200 overlap)
 ↓
Embeddings (Google Gemini embeddings)
 ↓
ChromaDB (local vector store, persisted on disk)
 ↓
Similarity Search (question embedding → closest chunks)
 ↓
Retrieved Context + Question
 ↓
Gemini LLM
 ↓
Answer + Sources
 ↓
React Chat UI
```

The key idea of RAG: **the AI never answers from memory alone.** It first *retrieves* the relevant parts of your document, and the prompt tells it to answer only from that context.

---

## 3. Technologies

| Layer     | Technology                                        |
| --------- | ------------------------------------------------- |
| Backend   | Python, FastAPI, Uvicorn                          |
| RAG       | LangChain, Google Gemini, Gemini Embeddings       |
| Vectors   | ChromaDB (local, persistent)                      |
| PDF       | PyPDF                                             |
| Metadata  | SQLite (`backend/documents.db`)                   |
| Frontend  | React + Vite (JavaScript), plain CSS, fetch()     |

---

## 4. Folder structure

```
rag-ai-chatbot/
├── backend/
│   ├── main.py           # FastAPI app + endpoints
│   ├── rag.py            # The RAG pipeline (heart of the project)
│   ├── database.py       # SQLite helpers for document metadata
│   ├── requirements.txt  # Python packages
│   ├── venv/             # Python virtual environment (do not commit)
│   ├── uploads/          # Saved PDFs (do not commit)
│   ├── chroma_db/        # ChromaDB vector database (do not commit)
│   └── documents.db      # Created automatically
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Chat + upload UI
│   │   ├── main.jsx       # React entry point
│   │   └── style.css      # All styling
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .env                   # Your GOOGLE_API_KEY (do not commit)
├── .gitignore
└── README.md
```

---

## 5. Install Python dependencies

```bash
cd backend
python -m venv venv

:: Windows
venv\Scripts\activate

# macOS / Linux
# source venv/bin/activate

pip install -r requirements.txt
```

---

## 6. Create `.env` and add your API key

1. Get a **free** Gemini API key: **https://aistudio.google.com/apikey**
2. Open the `.env` file (already created in the project root).
3. Replace the placeholder with your key:

```env
GOOGLE_API_KEY=AIzaSyYourRealKeyHere
```

> Never put `.env` in Git — it is already in `.gitignore`.

---

## 7. Start the backend

```bash
cd backend
venv\Scripts\activate      # Windows
# source venv/bin/activate # macOS / Linux

uvicorn main:app --reload
```

Backend runs at: **http://localhost:8000**

FastAPI auto-docs (test endpoints in the browser): **http://localhost:8000/docs**

---

## 8. Start the frontend

Open a **second** terminal:

```bash
cd frontend
npm install      # only the first time
npm run dev
```

Frontend runs at: **http://localhost:5173**

---

## 9. How to use the application

1. Open http://localhost:5173 in your browser.
2. Choose a PDF, click **Upload**.
3. Wait for the green status message (uploading → chunking → embedding).
4. Type a question in the chat box, then press **Send** (or Enter).
5. Read the answer and check the **Sources** listed below it.
6. Both terminals must be running at the same time.

Try asking things **not** in the document too — the bot must say it could not find the answer (no hallucination).

---

## 10. How RAG works internally (`backend/rag.py`)

Read the comments in `rag.py` — the whole pipeline lives there as simple functions:

1. `extract_text_from_pdf()` — pypdf reads every page.
2. `split_text()` — `RecursiveCharacterTextSplitter` cuts text into chunks of 1000 chars with 200 overlap. **Easily change `CHUNK_SIZE` / `CHUNK_OVERLAP` at the top of `rag.py`.**
3. `store_document()` — builds LangChain `Document` objects with metadata (`filename`, `chunk_number`) and saves them to ChromaDB.
4. `search_documents()` — embeds your question and returns the `top_k = 4` closest chunks.
5. `generate_answer()` — builds the prompt below (nothing else goes in):

```
You are a document question-answering assistant.
Answer the user's question using ONLY the context provided below.
If the answer cannot be found ... say "I couldn't find that information ..."
Context: <retrieved chunks>
Question: <your question>
```

Model names are variables at the top of `rag.py`: `EMBEDDING_MODEL` (default `gemini-embedding-2`) and `CHAT_MODEL` (default `gemini-3.5-flash`). If a model is not found, use the link in Section 12 to list the models your API key can actually use.

---

## 11. API endpoints

| Method | Endpoint      | Purpose                               |
| ------ | ------------- | ------------------------------------- |
| GET    | `/`           | Health check                          |
| POST   | `/upload`     | `multipart/form-data` PDF upload      |
| GET    | `/documents`  | List indexed documents (from SQLite)  |
| POST   | `/ask`        | `{"question": "..."}` → answer+ sources |

---

## 12. Common errors and fixes

| Problem                                                          | Fix                                                                   |
| ---------------------------------------------------------------- | --------------------------------------------------------------------- |
| `GoogleGenerativeAIError ... NOT_FOUND` | The model name is outdated **for your key**. Model availability differs per project. Check your models at https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY and update `EMBEDDING_MODEL` / `CHAT_MODEL` in `rag.py`. |
| `GoogleGenerativeAIError ... 403/404`                            | Your API key is wrong (check `.env`), or a model name is outdated.    |
| `401 Invalid API key`                                            | API key not loaded — make sure `.env` is at the project **root**.     |
| `No text could be extracted from this PDF`                       | The PDF is scanned/image-only. Convert it to text first (OCR).        |
| `ModuleNotFoundError`                                            | `pip install -r requirements.txt` inside the activated venv.          |
| CORS error in the browser console                                 | Both servers must run, and the backend must be on port **8000**.      |
| Embeddings are slow on free tier                                  | Normal — free Gemini keys are rate-limited. Wait a few seconds.       |
| Port already in use                                               | Stop old servers, or run `uvicorn main:app --port 8001`.              |
| Model name not found                                              | Update `CHAT_MODEL` / `EMBEDDING_MODEL` in `rag.py` to a current one. |

---

## 13. Deploy to Hugging Face Spaces (free)

Everything is deployed-ready: a `Dockerfile` builds the React frontend, then runs
FastAPI which serves **both** the API and the frontend — one single URL, nothing
else to host. Your SQLite + ChromaDB + uploads live in `/data`, which Hugging Face
keeps between restarts.

**Steps (about 10 minutes):**

1. Create a free account at https://huggingface.co and get a token
   (Settings → Access Tokens → New token → write).
2. Go to **https://huggingface.co/new** → name it `rag-ai-chatbot` → **SDK: Docker** → Create.
3. Clone your empty Space (replace `YOUR_USERNAME`):
   ```bash
   git clone https://huggingface.co/YOUR_USERNAME/rag-ai-chatbot
   ```
4. Copy the deploy files into the cloned folder:
   ```bash
   # from inside the cloned rag-ai-chatbot folder
   cp -r /path/to/your/local/rag-ai-chatbot/Dockerfile .
   cp -r /path/to/your/local/rag-ai-chatbot/.dockerignore .
   cp -r /path/to/your/local/rag-ai-chatbot/backend .
   cp -r /path/to/your/local/rag-ai-chatbot/frontend .
   ```
   (skip `venv/`, `node_modules/`, `uploads/`, `chroma_db/`, `.env`, `documents.db`, `dist/`, `static/`)
5. Commit and push (enter your username + the token as the password):
   ```bash
   git add . && git commit -m "deploy rag chatbot" && git push
   ```
6. On the Space page: **Settings → Variables and secrets → New secret**:
   - Name: `GOOGLE_API_KEY`   Value: your real Gemini key
7. Wait 3–5 minutes for the Docker build. Done!

Your app is live at:

**https://huggingface.co/spaces/YOUR_USERNAME/rag-ai-chatbot**

> Note: no `.env` is needed on Hugging Face — the secret replaces it.
> First upload may take ~10s (free-tier rate limits on Gemini embeddings).

---

## Notes

- Everything is stored locally: PDFs in `backend/uploads/`, vectors in `backend/chroma_db/`, metadata in SQLite. Restart the backend any time — your data survives.
- This is a **learning project** by design: no auth, no Docker, no Redis, no cloud. Read every file — it is intentionally simple.