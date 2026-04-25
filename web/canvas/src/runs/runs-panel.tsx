import { useEffect, useState } from "react";
import { useAuth } from "../api/auth-context";
import type { RunRecord } from "../api/types";
import { safeMessage, shortHash } from "../lib/safe-string";
import { ManifestView } from "./manifest-view";

const POLL_MS = 2000;

export function RunsPanel() {
  const { client } = useAuth();
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openRunId, setOpenRunId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    async function tick() {
      try {
        const response = await client.listRuns({ limit: 50 });
        if (cancelled) return;
        setRuns(response.items);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(safeMessage(err));
      } finally {
        if (!cancelled) {
          setLoading(false);
          timer = setTimeout(tick, POLL_MS);
        }
      }
    }
    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [client]);

  return (
    <div style={{ padding: 16 }}>
      <h2 style={{ marginTop: 0 }}>Recent runs</h2>
      {loading ? <p>Loading…</p> : null}
      {error ? <p style={{ color: "var(--color-error)" }}>{error}</p> : null}
      {!loading && runs.length === 0 ? (
        <p>No runs yet. Click <strong>Run</strong> on the canvas to start one.</p>
      ) : null}
      {runs.length > 0 ? (
        <table className="panel-table">
          <thead>
            <tr>
              <th>Run id</th>
              <th>Status</th>
              <th>Pipeline</th>
              <th>Mode</th>
              <th>Submitted</th>
              <th>Duration</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.run_id}>
                <td>
                  <code>{shortHash(run.run_id, 12)}</code>
                </td>
                <td>
                  <StatusPill status={run.status} />
                </td>
                <td>{String(run.metadata.pipeline_id ?? "")}</td>
                <td>{String(run.metadata.mode ?? "")}</td>
                <td>{run.submitted_at}</td>
                <td>{duration(run.started_at, run.ended_at)}</td>
                <td>
                  {run.status === "success" ? (
                    <button onClick={() => setOpenRunId(run.run_id)}>
                      Manifest
                    </button>
                  ) : run.status === "queued" || run.status === "running" ? (
                    <button
                      onClick={async () => {
                        try {
                          await client.cancelRun(run.run_id);
                        } catch {
                          /* polling will refresh */
                        }
                      }}
                    >
                      Cancel
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {openRunId ? (
        <ManifestView
          runId={openRunId}
          onClose={() => setOpenRunId(null)}
        />
      ) : null}
    </div>
  );
}

function StatusPill({ status }: { status: RunRecord["status"] }) {
  const colour: Record<RunRecord["status"], string> = {
    queued: "var(--color-text-dim)",
    running: "var(--color-accent)",
    success: "var(--color-accent-2)",
    error: "var(--color-error)",
    cancelled: "var(--color-warn)",
  };
  return (
    <span
      style={{
        color: colour[status],
        fontWeight: 600,
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: 0.04,
      }}
    >
      {status}
    </span>
  );
}

function duration(start: string | null, end: string | null): string {
  if (!start) return "";
  const s = Date.parse(start);
  const e = end ? Date.parse(end) : Date.now();
  if (Number.isNaN(s) || Number.isNaN(e)) return "";
  const seconds = Math.max(0, Math.round((e - s) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  return `${mins}m ${seconds - mins * 60}s`;
}
