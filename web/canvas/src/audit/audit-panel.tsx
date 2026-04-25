import { useEffect, useState } from "react";
import { useAuth } from "../api/auth-context";
import type { AuditRunRow } from "../api/types";
import { redactPayload } from "../lib/redact";
import { safeMessage } from "../lib/safe-string";
import { TabGuide } from "../components/tab-guide";

export function AuditPanel() {
  const { client } = useAuth();
  const [rows, setRows] = useState<AuditRunRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    client
      .listAuditRuns({ limit: 100 })
      .then((response) => {
        if (cancelled) return;
        setRows(redactPayload(response.items));
      })
      .catch((err) => {
        if (cancelled) return;
        setError(safeMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  return (
    <div style={{ padding: 16 }}>
      <TabGuide tab="audit" />
      <h2 style={{ marginTop: 0 }}>Audit log</h2>
      {loading ? <p>Loading…</p> : null}
      {error ? <p style={{ color: "var(--color-error)" }}>{error}</p> : null}
      {!loading && !error && rows.length === 0 ? (
        <p>No audit rows yet.</p>
      ) : null}
      {rows.length > 0 ? (
        <table className="panel-table">
          <thead>
            <tr>
              <th>Run id</th>
              <th>Kind</th>
              <th>Status</th>
              <th>Started</th>
              <th>Manifest path</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={row.run_id ? String(row.run_id) : `audit-${idx}`}>
                <td>
                  <code>{String(row.run_id ?? "")}</code>
                </td>
                <td>{String(row.kind ?? "")}</td>
                <td>{String(row.status ?? "")}</td>
                <td>{String(row.timestamp_start ?? "")}</td>
                <td>
                  <code>{String(row.manifest_path ?? "")}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
