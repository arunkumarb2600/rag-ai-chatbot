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
├── Dockerfile             # Builds frontend + backend for deployment
├── .dockerignore
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

## 13. Deploy to Render (free)

Deployed live at: **https://rag-ai-chatbot-bknm.onrender.com**

Everything is deployment-ready:
- A `Dockerfile` builds the React frontend, then runs FastAPI which serves **both** the API and the frontend — one single URL, nothing else to host.
- `DATA_DIR` (set to `/data` in the Dockerfile) controls where SQLite + ChromaDB + uploads are stored, so the paths work on any host.

**Steps (about 15 minutes):**

1. Create the GitHub repo:
   - Go to **https://github.com/new** → name it `rag-ai-chatbot` → **do not** add a README → Create.
   - Create a GitHub token once: avatar → **Settings → Developer settings → Personal access tokens → Tokens (classic)** → tick **`repo`** → Generate → copy it.
2. Push the code (from the project folder):
   ```bash
   git init -b main
   git add -A
   git commit -m "RAG AI chatbot: FastAPI + React + Gemini + ChromaDB"
   git remote add origin https://github.com/YOUR_USERNAME/rag-ai-chatbot.git
   git push -u origin main
   # username = YOUR_USERNAME, password = your GitHub token
   ```
   > After pushing, **delete the token** (Settings → Developer settings → Personal access tokens). Render connects via GitHub OAuth, not the token.
3. Create the Render app:
   - Go to **https://render.com** → **Sign up** → **Continue with GitHub**.
   - Dashboard → **New +** → **Web Service** → connect the `rag-ai-chatbot` repo.
   - Render auto-detects the `Dockerfile`. Choose name `rag-ai-chatbot`, a region near you, and instance type **Free** → **Create Web Service**.
4. Add your API key (backend reads it from the environment):
   - Service page → **Environment** → **Add Environment Variable**:
   - Key: `GOOGLE_API_KEY` → Value: your real Gemini key → **Save Changes** (it redeploys automatically).
5. Wait 5–10 minutes for the Docker build. When it says **Live**, open your app.

Your app is live at: **https://rag-ai-chatbot-bknm.onrender.com** — the base name `rag-ai-chatbot.onrender.com` was already taken, so Render appended a random suffix (`-bknm`).

**Updating the app later:** any `git push` to the repository makes Render rebuild automatically.

**Want a cleaner URL (e.g. `rag-ai-chatbot.onrender.com`)?**
After creation the onrender.com subdomain is locked to your service name. To change it:
1. In Render, click **New + → Web Service** again, pick the same repo, and name it **exactly** `rag-ai-chatbot` (the suffix only appears when that name is taken).
2. Re-add the environment variable `GOOGLE_API_KEY`.
3. Wait for **Live**, open the new URL, then **delete** the old `-bknm` service in the dashboard.

**Free-tier limits (normal behavior):**
- The app **sleeps after ~15 min of no traffic** — the first visit after that takes about a minute to wake up.
- Render free has an **ephemeral filesystem** — uploaded PDFs, SQLite and ChromaDB are lost when Render restarts the service. Just re-upload your PDFs.
- Free Elastic/Key Value instances and disk require a paid plan if you need permanent storage.

**Why not Hugging Face?** HF moved Docker Spaces behind a paid PRO plan in mid-2026 — Render's free tier still runs FastAPI web services.

---

## Notes

- Everything is stored locally: PDFs in `backend/uploads/`, vectors in `backend/chroma_db/`, metadata in SQLite. Restart the backend any time — your data survives (locally). On Render's free tier it is ephemeral.
- This is a **learning project** by design: no auth, no Redis, no cloud vector database, no microservices. Read every file — it is intentionally simple.