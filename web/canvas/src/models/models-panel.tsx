import { useEffect, useState } from "react";
import { useAuth } from "../api/auth-context";
import type { ModelSummary } from "../api/types";
import { safeMessage } from "../lib/safe-string";

export function ModelsPanel() {
  const { client } = useAuth();
  const [items, setItems] = useState<ModelSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    client
      .listModels({ kind: kind || undefined, limit: 500 })
      .then((response) => {
        if (cancelled) return;
        setItems(response.items);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(safeMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client, kind]);

  return (
    <div style={{ padding: 16 }}>
      <h2 style={{ marginTop: 0 }}>Models</h2>
      <div style={{ marginBottom: 12 }}>
        <label htmlFor="kind-filter" style={{ marginRight: 8 }}>
          Kind
        </label>
        <select
          id="kind-filter"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          style={{ width: 200, display: "inline-block" }}
        >
          <option value="">all</option>
          <option value="classifier">classifier</option>
          <option value="foundation">foundation</option>
          <option value="detection">detection</option>
          <option value="segmentation">segmentation</option>
        </select>
      </div>
      {loading ? <p>Loading…</p> : null}
      {error ? <p style={{ color: "var(--color-error)" }}>{error}</p> : null}
      {!loading && !error && items.length > 0 ? (
        <table className="panel-table">
          <thead>
            <tr>
              <th>Id</th>
              <th>Kind</th>
              <th>Name</th>
              <th>License</th>
              <th>Gated</th>
              <th>Tiers</th>
            </tr>
          </thead>
          <tbody>
            {items.map((m) => (
              <tr key={`${m.kind}-${m.id}`}>
                <td>
                  <code>{m.id}</code>
                </td>
                <td>{m.kind}</td>
                <td>{m.display_name}</td>
                <td>{m.license ?? ""}</td>
                <td>{m.gated ? "yes" : ""}</td>
                <td>{m.tier_compatibility.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
