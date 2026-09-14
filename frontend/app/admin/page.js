"use client";
import { useEffect, useState } from "react";
import NavBar from "../../components/NavBar";
import RequireAuth from "../../components/RequireAuth";
import { useAuth } from "../../lib/auth";
import { analytics } from "../../lib/api";

function AdminContent() {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    let cancelled = false;
    analytics(token, days)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [token, days]);

  if (error) return <div className="page-container form-error">{error}</div>;
  if (!data) return <div className="page-loading">Loading analytics…</div>;

  const unansweredPct = (data.unanswered_rate * 100).toFixed(1);

  function handleDaysChange(e) {
    setData(null);
    setDays(Number(e.target.value));
  }

  return (
    <div className="page-container">
      <div className="dashboard-controls">
        <p className="chat-intro" style={{ margin: 0 }}>
          System usage
        </p>
        <select className="window-select" value={days} onChange={handleDaysChange}>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">Total queries</div>
          <div className="kpi-value">{data.total_queries}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Failed searches / &quot;I don&apos;t know&quot;</div>
          <div className={`kpi-value ${data.unanswered_rate > 0.3 ? "warn" : ""}`}>
            {data.unanswered_count}
          </div>
          <div className="kpi-sub">{unansweredPct}% of all queries</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Answered</div>
          <div className="kpi-value">{data.answered_count}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Latency (p50 / p95)</div>
          <div className="kpi-value">{Math.round(data.latency_p50_ms)}ms</div>
          <div className="kpi-sub">p95: {Math.round(data.latency_p95_ms)}ms · mean: {Math.round(data.latency_mean_ms)}ms</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Estimated cost</div>
          <div className="kpi-value">${data.estimated_cost_usd.toFixed(4)}</div>
          <div className="kpi-sub">
            {data.total_prompt_tokens + data.total_completion_tokens} tokens
            {data.priced_models.length > 0 ? ` · ${data.priced_models.join(", ")}` : ""}
          </div>
        </div>
      </div>

      {data.unpriced_models.length > 0 && (
        <div className="form-hint" style={{ marginBottom: "1.5rem" }}>
          Note: {data.unpriced_models.join(", ")} usage isn&apos;t in the pricing table, so its
          cost isn&apos;t counted above.
        </div>
      )}

      <div className="section-title">Daily volume</div>
      {data.daily.length === 0 ? (
        <div className="empty-state">No queries in this window.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Total</th>
              <th>Answered</th>
              <th>Unanswered</th>
              <th>Avg latency</th>
            </tr>
          </thead>
          <tbody>
            {data.daily.map((d) => (
              <tr key={d.date}>
                <td>{d.date}</td>
                <td>{d.total}</td>
                <td>{d.answered}</td>
                <td>{d.unanswered}</td>
                <td>{Math.round(d.avg_latency_ms)}ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="section-title">Recent unsupported / unanswered questions</div>
      {data.recent_unanswered_questions.length === 0 ? (
        <div className="empty-state">None in this window — every question was answered.</div>
      ) : (
        <ul className="unanswered-list">
          {data.recent_unanswered_questions.map((q, i) => (
            <li key={i}>{q}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function AdminPage() {
  return (
    <RequireAuth role="admin">
      <NavBar />
      <AdminContent />
    </RequireAuth>
  );
}
