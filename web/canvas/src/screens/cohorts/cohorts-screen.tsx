import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type { CohortQCSummary, CohortSummary } from "../../api/types";
import { redactPayload } from "../../lib/redact";
import { safeMessage } from "../../lib/safe-string";

export function CohortsScreen() {
  const { client } = useAuth();
  const [items, setItems] = useState<CohortSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [qc, setQc] = useState<CohortQCSummary | null>(null);
  const [form, setForm] = useState({ id: "", directory: "", pattern: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await client.listCohorts();
      setItems(redactPayload(response.items));
      setError(null);
    } catch (err) {
      setError(safeMessage(err));
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  const submitBuild = async () => {
    if (!form.id.trim() || !form.directory.trim()) {
      setError("Provide a cohort id and a slide directory.");
      return;
    }
    setBusy(true);
    setError(null);
    setFeedback(null);
    try {
      const cohort = await client.createCohort({
        id: form.id.trim(),
        directory: form.directory.trim(),
        pattern: form.pattern.trim() || null,
      });
      setFeedback(`Built cohort ${cohort.id} with ${cohort.slide_count} slide(s).`);
      setForm({ id: "", directory: "", pattern: "" });
      void load();
    } catch (err) {
      setError(safeMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const runQc = async (cohortId: string) => {
    setBusy(true);
    setQc(null);
    setError(null);
    try {
      const summary = await client.cohortQc(cohortId);
      setQc(redactPayload(summary));
    } catch (err) {
      setError(safeMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (cohortId: string) => {
    if (!window.confirm(`Delete cohort "${cohortId}"?`)) return;
    setBusy(true);
    try {
      await client.deleteCohort(cohortId);
      void load();
    } catch (err) {
      setError(safeMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="task-content">
      <h2>Cohorts</h2>
      <p className="lede">
        Group slides into named cohorts the pipeline executor can fan out
        over. Build a cohort YAML from a directory, view its slides, and run
        the Phase-9 QC summary.
      </p>

      {error ? <div className="banner-err">{error}</div> : null}
      {feedback ? <div className="banner-ok">{feedback}</div> : null}

      <div className="card">
        <h3>Build cohort from directory</h3>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="c_id">Cohort id</label>
            <input
              id="c_id"
              value={form.id}
              onChange={(e) => setForm({ ...form, id: e.target.value })}
              placeholder="cohort_a"
            />
          </div>
          <div className="field">
            <label htmlFor="c_dir">Slide directory</label>
            <input
              id="c_dir"
              value={form.directory}
              onChange={(e) => setForm({ ...form, directory: e.target.value })}
              placeholder="/Users/dr/data/cohort-a/slides"
            />
          </div>
          <div className="field">
            <label htmlFor="c_pattern">Glob pattern (optional)</label>
            <input
              id="c_pattern"
              value={form.pattern}
              onChange={(e) => setForm({ ...form, pattern: e.target.value })}
              placeholder="*.svs"
            />
          </div>
        </div>
        <div className="toolbar" style={{ marginTop: 12 }}>
          <button onClick={submitBuild} disabled={busy}>
            {busy ? "Working…" : "Build + save"}
          </button>
        </div>
      </div>

      <div className="card">
        <h3>Saved cohorts ({items.length})</h3>
        {loading ? <p>Loading…</p> : null}
        {!loading && items.length === 0 ? (
          <p className="lede">No cohorts yet. Build one above.</p>
        ) : null}
        <table className="panel-table bordered">
          <thead>
            <tr>
              <th>Id</th>
              <th>Slides</th>
              <th>Slide ids</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id}>
                <td>
                  <code>{c.id}</code>
                </td>
                <td>{c.slide_count ?? ""}</td>
                <td>
                  <code style={{ fontSize: 11 }}>
                    {(c.slide_ids ?? []).slice(0, 5).join(", ")}
                    {c.slide_ids && c.slide_ids.length > 5 ? "…" : ""}
                  </code>
                </td>
                <td>
                  <button onClick={() => void runQc(c.id)} disabled={busy}>
                    QC
                  </button>{" "}
                  <button onClick={() => void remove(c.id)} disabled={busy}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {qc ? (
        <div className="card">
          <h3>QC summary — {qc.id}</h3>
          <div className="kpi-row">
            <div className="kpi ok">
              <div className="label">Pass</div>
              <div className="value">{qc.summary.pass}</div>
            </div>
            <div className="kpi warn">
              <div className="label">Warn</div>
              <div className="value">{qc.summary.warn}</div>
            </div>
            <div className="kpi err">
              <div className="label">Fail</div>
              <div className="value">{qc.summary.fail}</div>
            </div>
            <div className="kpi">
              <div className="label">Slides</div>
              <div className="value">{qc.slide_count}</div>
            </div>
          </div>
          <div className="toolbar" style={{ marginTop: 12, gap: 8 }}>
            <a
              className="nav-item"
              href={client.cohortQcHtmlUrl(qc.id)}
              target="_blank"
              rel="noopener noreferrer"
            >
              Download HTML report
            </a>
            <a
              className="nav-item"
              href={client.cohortQcPdfUrl(qc.id)}
              target="_blank"
              rel="noopener noreferrer"
            >
              Download PDF report
            </a>
          </div>
          <p className="lede" style={{ marginTop: 8, fontSize: ".7rem" }}>
            HTML works without extras; the PDF requires the
            <code> [safety]</code> server extra (ReportLab).
          </p>
        </div>
      ) : null}
    </section>
  );
}
