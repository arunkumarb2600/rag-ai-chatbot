import { useState } from "react";

// The FastAPI backend address.
// - In development: Vite runs on :5173 and the backend on :8000.
// - In production: the built app is served BY the backend itself, so we
//   call the same address (relative URLs -> fetch("/upload")).
const API_URL = import.meta.env.PROD ? "" : "http://localhost:8000";

function App() {
  // PDF upload state
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);

  // Chat state
  const [messages, setMessages] = useState([]); // [{role: 'user'|'ai', text, sources}]
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);

  // Pick a PDF file
  function handleFileChange(event) {
    setSelectedFile(event.target.files[0]);
    setUploadError("");
  }

  // Upload + index the PDF on the backend
  async function handleUpload() {
    if (!selectedFile) {
      setUploadError("Please choose a PDF file first.");
      return;
    }

    setUploading(true);
    setUploadStatus("");
    setUploadError("");

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed.");
      }

      setUploadStatus(
        `Uploaded and indexed "${data.filename}" (${data.chunks} chunks).`
      );
      setSelectedFile(null);
      // Reset the file input so the same file can be chosen again.
      document.getElementById("file-input").value = "";
    } catch (error) {
      setUploadError(error.message);
    } finally {
      setUploading(false);
    }
  }

  // Send a question to the backend, which runs the full RAG pipeline.
  async function handleAsk() {
    const question = input.trim();
    if (!question || thinking) return;

    // Add the user message to the chat list.
    const userMessage = { role: "user", text: question };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setThinking(true);

    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Something went wrong.");
      }

      const aiMessage = { role: "ai", text: data.answer, sources: data.sources || [] };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: `Error: ${error.message}`, sources: [] },
      ]);
    } finally {
      setThinking(false);
    }
  }

  return (
    <div className="container">
      <h1 className="title">RAG AI Chatbot</h1>

      {/* ---------- Upload section ---------- */}
      <section className="card upload-card">
        <h2>Upload your PDF</h2>
        <div className="upload-row">
          <input
            id="file-input"
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
          />
          <button onClick={handleUpload} disabled={uploading}>
            {uploading ? "Uploading..." : "Upload"}
          </button>
        </div>

        {uploadStatus && <p className="status success">✓ {uploadStatus}</p>}
        {uploadError && <p className="status error">{uploadError}</p>}
      </section>

      {/* ---------- Chat section ---------- */}
      <section className="card chat-card">
        <div className="chat-window">
          {messages.length === 0 && !thinking && (
            <p className="hint">
              Upload a PDF above, then ask me anything about it.
            </p>
          )}

          {messages.map((message, index) => (
            <div key={index} className={`message ${message.role}`}>
              <p className="message-label">
                {message.role === "user" ? "You" : "AI"}
              </p>
              <p className="message-text">{message.text}</p>

              {/* Sources shown under every AI answer */}
              {message.sources && message.sources.length > 0 && (
                <div className="sources">
                  <p>Sources:</p>
                  <ul>
                    {message.sources.map((source, i) => (
                      <li key={i}>
                        {source.filename} — chunk {source.chunk_number}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}

          {thinking && (
            <div className="message ai">
              <p className="message-label">AI</p>
              <p className="message-text thinking-text">Thinking...</p>
            </div>
          )}
        </div>

        {/* ---------- Input row ---------- */}
        <div className="input-row">
          <input
            type="text"
            placeholder="Ask a question..."
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") handleAsk();
            }}
          />
          <button onClick={handleAsk} disabled={thinking}>
            Send
          </button>
        </div>
      </section>
    </div>
  );
}

export default App;