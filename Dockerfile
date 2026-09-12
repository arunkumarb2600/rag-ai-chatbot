# ============================================================
# Dockerfile for Hugging Face Spaces
#
# Stage 1 builds the React frontend (npm run build).
# Stage 2 installs the Python backend and serves the built
# frontend from FastAPI, so the whole app runs on ONE URL.
# ============================================================

# ---- Stage 1: build the React frontend ----
FROM node:20 AS frontend-build
WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend + frontend ----
FROM python:3.11-slim
WORKDIR /app

# Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend code (main.py, rag.py, database.py, ...)
COPY backend/ ./

# The built React app from stage 1 -> backend/static/index.html
COPY --from=frontend-build /frontend/dist ./static/

# Hugging Face Spaces keeps everything under /data between restarts.
# Our SQLite DB, ChromaDB and uploads all live there (DATA_DIR in code).
ENV DATA_DIR=/data

# Hugging Face Spaces expects the app on port 7860.
EXPOSE 7860

# Start the API (plus the frontend it serves).
# Render sets a PORT env var (Hugging Face uses 7860) - so read it,
# and fall back to 7860 when no PORT is provided.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]