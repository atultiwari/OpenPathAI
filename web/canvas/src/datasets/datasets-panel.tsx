import { useEffect, useState } from "react";
import { useAuth } from "../api/auth-context";
import type { DatasetCard } from "../api/types";
import { redactPayload } from "../lib/redact";
import { safeMessage } from "../lib/safe-string";

export function DatasetsPanel() {
  const { client } = useAuth();
  const [items, setItems] = useState<DatasetCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    client
      .listDatasets({ limit: 500 })
      .then((response) => {
        if (cancelled) return;
        setItems(redactPayload(response.items));
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
      <h2 style={{ marginTop: 0 }}>Datasets</h2>
      {loading ? <p>Loading…</p> : null}
      {error ? <p style={{ color: "var(--color-error)" }}>{error}</p> : null}
      {!loading && !error && items.length > 0 ? (
        <table className="panel-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Display name</th>
              <th>Modality</th>
              <th>Classes</th>
            </tr>
          </thead>
          <tbody>
            {items.map((d, idx) => (
              <tr key={d.name ?? `dataset-${idx}`}>
                <td>
                  <code>{d.name}</code>
                </td>
                <td>{d.display_name ?? ""}</td>
                <td>{d.modality ?? ""}</td>
                <td>
                  {d.num_classes ?? (Array.isArray(d.classes) ? d.classes.length : "")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
