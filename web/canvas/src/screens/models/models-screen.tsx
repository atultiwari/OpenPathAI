import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type { ModelSummary } from "../../api/types";
import { safeMessage } from "../../lib/safe-string";

const KIND_LABEL: Record<string, string> = {
  classifier: "Tier A — Classifier zoo",
  foundation: "Tier C — Foundation models",
  detection: "Tier D — Detection",
  segmentation: "Tier D — Segmentation",
};

export function ModelsScreen() {
  const { client } = useAuth();
  const [items, setItems] = useState<ModelSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<string>("");
  const [selected, setSelected] = useState<ModelSummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    client
      .listModels({ kind: kind || undefined, limit: 500 })
      .then((response) => {
        if (cancelled) return;
        setItems(response.items);
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

  const grouped = useMemo(() => {
    const groups = new Map<string, ModelSummary[]>();
    for (const m of items) {
      const arr = groups.get(m.kind) ?? [];
      arr.push(m);
      groups.set(m.kind, arr);
    }
    return Array.from(groups.entries());
  }, [items]);

  return (
    <section className="task-content">
      <h2>Models</h2>
      <p className="lede">
        The OpenPathAI model zoo. Gated foundation models (UNI, Virchow2,
        CONCH, …) display a request-access banner that links to the upstream
        Hugging Face form.
      </p>

      {error ? <div className="banner-err">{error}</div> : null}

      <div className="toolbar">
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          style={{ width: 240 }}
        >
          <option value="">All kinds</option>
          <option value="classifier">classifier</option>
          <option value="foundation">foundation</option>
          <option value="detection">detection</option>
          <option value="segmentation">segmentation</option>
        </select>
      </div>

      {loading ? <p>Loading…</p> : null}
      {grouped.map(([k, rows]) => (
        <div className="card" key={k}>
          <h3>{KIND_LABEL[k] ?? k}</h3>
          <table className="panel-table bordered">
            <thead>
              <tr>
                <th>Id</th>
                <th>Display name</th>
                <th>License</th>
                <th>Tier</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => (
                <tr key={`${m.kind}-${m.id}`}>
                  <td>
                    <code>{m.id}</code>{" "}
                    {m.gated ? (
                      <span className="tag gated">gated</span>
                    ) : null}
                  </td>
                  <td>{m.display_name}</td>
                  <td>{m.license ?? ""}</td>
                  <td>{m.tier_compatibility.join(", ")}</td>
                  <td>
                    <button onClick={() => setSelected(m)}>Details</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {selected ? (
        <ModelDetailModal model={selected} onClose={() => setSelected(null)} />
      ) : null}
    </section>
  );
}

function ModelDetailModal({
  model,
  onClose,
}: {
  model: ModelSummary;
  onClose: () => void;
}) {
  const hfUrl = model.hf_repo
    ? `https://huggingface.co/${model.hf_repo}`
    : null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h2>{model.id}</h2>
        <p className="lede">{model.display_name}</p>
        {model.gated ? (
          <div className="banner-warn">
            This model is gated on Hugging Face. Request access on the upstream
            page using a matching institutional email; once approved, set{" "}
            <code>HF_TOKEN</code> on the API host and the model will appear in
            the Analyse / Train pickers.
          </div>
        ) : null}
        <table className="panel-table">
          <tbody>
            <tr>
              <th>Kind</th>
              <td>{model.kind}</td>
            </tr>
            <tr>
              <th>License</th>
              <td>{model.license ?? "—"}</td>
            </tr>
            <tr>
              <th>Citation</th>
              <td>{model.citation ?? "—"}</td>
            </tr>
            <tr>
              <th>HF repo</th>
              <td>
                {hfUrl ? (
                  <a href={hfUrl} target="_blank" rel="noreferrer">
                    {model.hf_repo}
                  </a>
                ) : (
                  "—"
                )}
              </td>
            </tr>
            <tr>
              <th>Embedding dim</th>
              <td>{model.embedding_dim ?? "—"}</td>
            </tr>
            <tr>
              <th>Input size</th>
              <td>
                {model.input_size
                  ? `${model.input_size[0]} × ${model.input_size[1]}`
                  : "—"}
              </td>
            </tr>
            <tr>
              <th>Tier compatibility</th>
              <td>{model.tier_compatibility.join(", ") || "—"}</td>
            </tr>
          </tbody>
        </table>
        <div className="token-form actions" style={{ marginTop: 16 }}>
          {model.gated && hfUrl ? (
            <a
              href={hfUrl}
              target="_blank"
              rel="noreferrer"
              className="nav-item"
              style={{
                background: "var(--color-panel-2)",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                padding: "8px 12px",
                color: "var(--color-accent)",
              }}
            >
              Request access on Hugging Face →
            </a>
          ) : null}
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
