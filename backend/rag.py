"""
rag.py
======

The heart of the RAG pipeline.

RAG = Retrieval-Augmented Generation.

Instead of asking the AI model blindly, we first SEARCH our own documents
and only then let the AI answer using the found text. This prevents the
model from making things up about your documents.

The full flow this file implements:

  PDF file
     |
     v
  1. extract_text_from_pdf()   -> raw text
     |
     v
  2. split_text()              -> small chunks (1000 chars, 200 overlap)
     |
     v
  3. create_embeddings()       -> Google Gemini turns each chunk into numbers
     |
     v
  4. store_document()          -> chunks + embeddings saved in ChromaDB
                                 (chunks stored together with metadata:
                                  filename, page_number, chunk_number)
     |
     |   ... later, when the user asks a question ...
     |
     v
  5. search_documents()        -> question becomes an embedding, ChromaDB
                                 finds the most similar chunks (top 4)
     |
     v
  6. generate_answer()         -> Gemini gets (retrieved context + question)
                                 and answers ONLY from that context
"""

import os

from dotenv import load_dotenv

# ---- Load the API key from the .env file in the project root ----
load_dotenv()

# ---- Easy-to-change settings ----

# How big each text chunk is (in characters).
CHUNK_SIZE = 1000
# How much overlap between chunks (keeps context when we split).
CHUNK_OVERLAP = 200
# How many chunks ChromaDB returns for each question.
TOP_K = 4

# Gemini model names (current recommended models, change freely).
# NOTE: the correct model name differs per API project -
# if embeddings fail with NOT_FOUND, check your available models:
#   https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY
EMBEDDING_MODEL = "gemini-embedding-2"
CHAT_MODEL = "gemini-3.5-flash"

# Where ChromaDB stores its persistent vector database.
# In local dev this is the backend folder. When deployed (Docker/Hugging
# Face Spaces) DATA_DIR points to /data, a persistent disk, so the vectors
# survive restarts.
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")

# Name of the ChromaDB collection (a named folder of vectors).
COLLECTION_NAME = "rag_documents"

# ---- Set up reusable objects (done once, not on every request) ----

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

# 1. Embeddings: turns text into numbers so computers can compare meaning.
embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)

# 2. Chat model: the Gemini model that writes the final answer.
llm = ChatGoogleGenerativeAI(model=CHAT_MODEL, temperature=0.3)

# 3. The vector store. We import Chroma lazily below because creating it
#    touches the on-disk database.


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Read a PDF file and return all the text inside it as one big string.
    """
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    pages_text = []

    for page_number, page in enumerate(reader.pages, start=1):
        # page.extract_text() can return None for image-only pages.
        text = page.extract_text() or ""
        pages_text.append(text)

    full_text = "\n".join(pages_text).strip()

    if not full_text:
        raise ValueError(
            "No text could be extracted from this PDF. "
            "It may be a scanned/image-only document."
        )

    return full_text


def split_text(text: str):
    """
    Split one big block of text into smaller chunks so embeddings are
    more precise (a 1000-char chunk is easier to match than a 20-page PDF).
    Each chunk keeps metadata so we can cite the source later.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_text(text)


def get_vector_store():
    """
    Open (or create) the persistent ChromaDB store.
    This is safe to call on every request because the same collection is
    reused - documents survive backend restarts.
    """
    from langchain_chroma import Chroma

    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )


def store_document(filename: str, pdf_path: str):
    """
    Full indexing of one PDF:
      1. extract text
      2. split into chunks
      3. build LangChain Document objects carrying metadata
      4. save them into ChromaDB
    Returns the number of chunks stored.
    """
    text = extract_text_from_pdf(pdf_path)
    chunks = split_text(text)

    # LangChain wraps text + metadata in a "Document".
    # We can't know the real page of a chunk after joining all pages,
    # so we reference the whole file for now (page is best-effort).
    from langchain_core.documents import Document

    documents = [
        Document(
            page_content=chunk,
            metadata={
                "filename": filename,
                "chunk_number": i + 1,
            },
        )
        for i, chunk in enumerate(chunks)
    ]

    vector_store = get_vector_store()

    # This computes all embedding vectors and stores them on disk.
    vector_store.add_documents(documents)

    return len(chunks)


def search_documents(query: str, top_k: int = TOP_K):
    """
    RAG step 5: given a question, embed it and find the most similar chunks.
    Returns a list of dicts: {"content": ..., "filename": ..., "chunk_number": ...}
    """
    vector_store = get_vector_store()

    # ChromaDB converts the query into an embedding vector internally and
    # returns the chunks whose vectors are "closest" to the question.
    results = vector_store.similarity_search_with_relevance_scores(query, k=top_k)

    sources = []
    seen = set()
    for doc, _score in results:
        filename = doc.metadata.get("filename", "unknown")
        chunk_number = doc.metadata.get("chunk_number", 0)

        # Skip duplicate chunks (ChromaDB can return the same chunk twice
        # when there are fewer documents in the collection than top_k).
        key = (filename, chunk_number)
        if key in seen:
            continue
        seen.add(key)

        sources.append(
            {
                "content": doc.page_content,
                "filename": filename,
                "chunk_number": chunk_number,
            }
        )
    return sources


def generate_answer(question: str, contexts):
    """
    RAG step 6: give Gemini ONLY the retrieved context + the question.
    The instruction inside the prompt forces the model to answer strictly
    from the context, which stops hallucinations.
    Returns (answer, sources_list).
    """
    # Join all retrieved chunks into one "context block" for the prompt.
    context_text = "\n\n---\n\n".join(c["content"] for c in contexts)

    prompt = f"""You are a document question-answering assistant.

Answer the user's question using ONLY the context provided below.

If the answer cannot be found in the context, clearly say:
"I couldn't find that information in the uploaded document."

Do not invent information.

Context:
{context_text}

Question:
{question}"""

    # Ask Gemini and convert its response to a plain text string.
    # Newer Google SDKs return "content" as a list of text blocks, e.g.
    #   [{"type": "text", "text": "The answer..."}]
    # instead of a simple str - so we handle both cases.
    content = llm.invoke(prompt).content

    if isinstance(content, str):
        answer = content
    else:
        answer = "".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        ).strip()

    # Sources: filename + chunk number, without duplicates.
    # (ChromaDB can return the same chunk twice when the collection has
    # fewer documents than TOP_K.)
    sources = []
    seen = set()
    for c in contexts:
        source = (c["filename"], c["chunk_number"])
        if source not in seen:
            seen.add(source)
            sources.append(
                {
                    "filename": c["filename"],
                    "chunk_number": c["chunk_number"],
                }
            )

    return answer, sources