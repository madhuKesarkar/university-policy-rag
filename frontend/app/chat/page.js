"use client";
import { useState } from "react";
import NavBar from "../../components/NavBar";
import RequireAuth from "../../components/RequireAuth";
import { useAuth } from "../../lib/auth";
import { ask } from "../../lib/api";

function Citation({ citation }) {
  return (
    <div className="citation">
      <div className="citation-title">
        {citation.document_title}
        {citation.is_stale && <span className="stale-badge">May be outdated</span>}
      </div>
      <div className="citation-meta">
        {[citation.course_code || citation.department, citation.section_heading]
          .filter(Boolean)
          .join(" · ")}
        {citation.page_number ? ` · p. ${citation.page_number}` : ""}
      </div>
    </div>
  );
}

function AnswerCard({ response }) {
  return (
    <div className={`answer-card ${response.answered ? "" : "unanswered"}`}>
      <p className="answer-text">{response.answered ? response.answer : response.message}</p>

      {response.answered && response.citations?.length > 0 && (
        <>
          <div className="citations-label">Sources</div>
          {response.citations.map((c, i) => (
            <Citation key={i} citation={c} />
          ))}
        </>
      )}

      {response.retrieved_passages?.length > 0 && (
        <details>
          <summary style={{ cursor: "pointer", fontSize: "0.82rem", color: "var(--text-muted)", marginTop: "0.6rem" }}>
            Show all {response.retrieved_passages.length} retrieved passages considered
          </summary>
          {response.retrieved_passages.map((p, i) => (
            <div key={i} className="citation" style={{ marginTop: "0.5rem" }}>
              <div className="citation-meta">
                rerank score {p.rerank_score.toFixed(3)} · sources: {p.retrieval_sources.join(", ")}
              </div>
              <Citation citation={p.citation} />
              <div style={{ fontSize: "0.83rem", marginTop: "0.3rem" }}>{p.content}</div>
            </div>
          ))}
        </details>
      )}

      <div className="latency-note">{response.latency_ms}ms</div>
    </div>
  );
}

function ChatContent() {
  const { token } = useAuth();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || pending) return;
    setQuestion("");
    setError(null);
    setPending(true);
    try {
      const response = await ask(token, q);
      setMessages((prev) => [...prev, { question: q, response }]);
    } catch (err) {
      setError(err.message || "Something went wrong asking that question.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="page-container">
      <p className="chat-intro">
        Ask about course prerequisites, syllabi, or academic policies. Every answer is grounded
        in the indexed documents and cited — if nothing confidently answers your question,
        you&apos;ll be told directly rather than given a guess.
      </p>

      <form className="chat-form" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="e.g. Can I take the Machine Learning course before taking Statistics?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={pending}
        />
        <button type="submit" disabled={pending || !question.trim()}>
          {pending ? "Asking…" : "Ask"}
        </button>
      </form>

      {error && <div className="form-error" style={{ marginBottom: "1.5rem" }}>{error}</div>}

      {messages.length === 0 && !pending && (
        <div className="empty-state">Ask your first question above.</div>
      )}

      {messages.map((m, i) => (
        <div className="message-block" key={i}>
          <div className="question-row">
            <div className="question-bubble">{m.question}</div>
          </div>
          <AnswerCard response={m.response} />
        </div>
      ))}

      {pending && <div className="loading-dots">Searching documents and generating an answer…</div>}
    </div>
  );
}

export default function ChatPage() {
  return (
    <RequireAuth>
      <NavBar />
      <ChatContent />
    </RequireAuth>
  );
}
