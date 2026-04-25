import { useEffect, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type { ActiveLearningSession } from "../../api/types";
import { redactPayload } from "../../lib/redact";
import { safeMessage } from "../../lib/safe-string";

const SCORERS = ["max_softmax", "entropy", "mc_dropout"];

export function AnnotateScreen() {
  const { client } = useAuth();
  const [sessions, setSessions] = useState<ActiveLearningSession[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latest, setLatest] = useState<ActiveLearningSession | null>(null);

  const [classes, setClasses] = useState("benign\nmalignant");
  const [poolSize, setPoolSize] = useState(64);
  const [seedSize, setSeedSize] = useState(8);
  const [holdoutSize, setHoldoutSize] = useState(16);
  const [iterations, setIterations] = useState(2);
  const [budget, setBudget] = useState(4);
  const [scorer, setScorer] = useState("max_softmax");

  useEffect(() => {
    let cancelled = false;
    client
      .listActiveLearningSessions()
      .then((response) => {
        if (cancelled) return;
        setSessions(redactPayload(response.items));
      })
      .catch((err) => {
        if (!cancelled) setError(safeMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  const start = async () => {
    const klasses = classes
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    if (klasses.length < 2) {
      setError("Provide at least two class names.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const session = await client.startActiveLearningSession({
        classes: klasses,
        pool_size: poolSize,
        seed_size: seedSize,
        holdout_size: holdoutSize,
        iterations,
        budget_per_iteration: budget,
        scorer,
      });
      setLatest(redactPayload(session));
      setSessions((prev) => [redactPayload(session), ...prev]);
    } catch (err) {
      setError(safeMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="task-content">
      <h2>Annotate</h2>
      <p className="lede">
        The active-learning loop (Bet 1). Phase 20.5 ships a synthetic demo
        session driven by the Phase-12 PrototypeTrainer + simulated oracle —
        you'll see the canonical loop shape (seed → score → acquire → label →
        retrain) and the iteration metrics. Real interactive labeling on tile
        images plugs in here in a later phase.
      </p>

      {error ? <div className="banner-err">{error}</div> : null}

      <div className="card">
        <h3>Start a demo session</h3>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="al_classes">Classes (one per line)</label>
            <textarea
              id="al_classes"
              rows={3}
              value={classes}
              onChange={(e) => setClasses(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="al_pool">Pool size</label>
            <input
              id="al_pool"
              type="number"
              min={8}
              max={2048}
              value={poolSize}
              onChange={(e) => setPoolSize(Number(e.target.value) || 64)}
            />
          </div>
          <div className="field">
            <label htmlFor="al_seed">Seed size</label>
            <input
              id="al_seed"
              type="number"
              min={2}
              max={64}
              value={seedSize}
              onChange={(e) => setSeedSize(Number(e.target.value) || 8)}
            />
          </div>
          <div className="field">
            <label htmlFor="al_holdout">Holdout size</label>
            <input
              id="al_holdout"
              type="number"
              min={4}
              max={256}
              value={holdoutSize}
              onChange={(e) => setHoldoutSize(Number(e.target.value) || 16)}
            />
          </div>
          <div className="field">
            <label htmlFor="al_iters">Iterations</label>
            <input
              id="al_iters"
              type="number"
              min={1}
              max={10}
              value={iterations}
              onChange={(e) => setIterations(Number(e.target.value) || 2)}
            />
          </div>
          <div className="field">
            <label htmlFor="al_budget">Budget per iteration</label>
            <input
              id="al_budget"
              type="number"
              min={1}
              max={64}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value) || 4)}
            />
          </div>
          <div className="field">
            <label htmlFor="al_scorer">Scorer</label>
            <select
              id="al_scorer"
              value={scorer}
              onChange={(e) => setScorer(e.target.value)}
            >
              {SCORERS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="toolbar" style={{ marginTop: 12 }}>
          <button onClick={start} disabled={busy}>
            {busy ? "Running…" : "Run demo loop"}
          </button>
        </div>
      </div>

      {latest ? <SessionCard session={latest} /> : null}

      <div className="card">
        <h3>Past sessions ({sessions.length})</h3>
        {sessions.length === 0 ? (
          <p className="lede">Run a demo loop above.</p>
        ) : (
          <table className="panel-table bordered">
            <thead>
              <tr>
                <th>Run id</th>
                <th>Initial ECE</th>
                <th>Final ECE</th>
                <th>Final accuracy</th>
                <th>Iterations</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td>
                    <code>{s.id.slice(0, 16)}</code>
                  </td>
                  <td>{(s.manifest.initial_ece ?? 0).toFixed(3)}</td>
                  <td>{(s.manifest.final_ece ?? 0).toFixed(3)}</td>
                  <td>{((s.manifest.final_accuracy ?? 0) * 100).toFixed(1)}%</td>
                  <td>{s.manifest.acquisitions?.length ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

function SessionCard({ session }: { session: ActiveLearningSession }) {
  return (
    <div className="card">
      <h3>Latest session — {session.id}</h3>
      <div className="kpi-row">
        <div className="kpi">
          <div className="label">Initial ECE</div>
          <div className="value">
            {(session.manifest.initial_ece ?? 0).toFixed(3)}
          </div>
        </div>
        <div
          className={
            session.manifest.final_ece <= session.manifest.initial_ece
              ? "kpi ok"
              : "kpi warn"
          }
        >
          <div className="label">Final ECE</div>
          <div className="value">
            {(session.manifest.final_ece ?? 0).toFixed(3)}
          </div>
        </div>
        <div className="kpi ok">
          <div className="label">Final accuracy</div>
          <div className="value">
            {((session.manifest.final_accuracy ?? 0) * 100).toFixed(1)}%
          </div>
        </div>
        <div className="kpi">
          <div className="label">Acquired</div>
          <div className="value">
            {session.manifest.acquired_tile_ids?.length ?? 0}
          </div>
        </div>
      </div>
      <table className="panel-table bordered">
        <thead>
          <tr>
            <th>Iter</th>
            <th>Selected</th>
            <th>ECE before → after</th>
            <th>Accuracy</th>
          </tr>
        </thead>
        <tbody>
          {(session.manifest.acquisitions ?? []).map((a) => (
            <tr key={a.iteration}>
              <td>{a.iteration}</td>
              <td>{a.selected_tile_ids.length}</td>
              <td>
                {a.ece_before.toFixed(3)} → {a.ece_after.toFixed(3)}
              </td>
              <td>{(a.accuracy_after * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
