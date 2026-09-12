"""
database.py
===========

A tiny SQLite helper that keeps track of the PDFs the user has uploaded.

We use Python's built-in sqlite3 instead of a heavy ORM so it is easy to
understand. The database file (documents.db) is created in the backend folder.

Table: documents
  - id           : unique number for each row
  - filename     : name of the uploaded PDF
  - upload_date  : when it was uploaded (YYYY-MM-DD)
  - status       : "indexed" after the PDF text was stored in ChromaDB
"""

import os
import sqlite3
from datetime import date

# Where the database file lives.
# In local dev this is the backend folder. When deployed (Docker/Hugging
# Face Spaces) the DATA_DIR env var points to /data, which is a persistent
# disk that survives server restarts - so uploads and vectors are kept.
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
DB_PATH = os.path.join(DATA_DIR, "documents.db")


def _connect():
    """Open a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    # Keep the columns we write in the correct order when inserting.
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    """
    Create the documents table if it does not exist yet.
    Called once when the backend starts.
    """
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            upload_date TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def add_document(filename: str, status: str = "indexed"):
    """
    Insert a new document row and return its id.
    Returns (id, row) so the caller can confirm it was stored.
    """
    conn = _connect()
    cursor = conn.execute(
        "INSERT INTO documents (filename, upload_date, status) VALUES (?, ?, ?)",
        (filename, date.today().isoformat(), status),
    )
    conn.commit()

    row_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (row_id,)).fetchone()
    conn.close()
    return row_id, dict(row)


def get_documents():
    """Return all stored documents, newest first."""
    conn = _connect()
    rows = conn.execute("SELECT * FROM documents ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]