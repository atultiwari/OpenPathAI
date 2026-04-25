import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type { DatasetCard } from "../../api/types";
import { redactPayload } from "../../lib/redact";
import { safeMessage } from "../../lib/safe-string";
import { TabGuide } from "../../components/tab-guide";

export function DatasetsScreen() {
  const { client } = useAuth();
  const [items, setItems] = useState<DatasetCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRegister, setShowRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [form, setForm] = useState({
    path: "",
    name: "",
    tissue: "colon",
    license: "user-supplied",
    stain: "H&E",
    overwrite: false,
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await client.listDatasets({ limit: 500 });
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

  const submitRegister = async () => {
    if (!form.path.trim() || !form.name.trim()) {
      setError("Provide both a folder path and a dataset name.");
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      const card = await client.registerDatasetFolder({
        path: form.path.trim(),
        name: form.name.trim(),
        tissue: form.tissue
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        license: form.license || undefined,
        stain: form.stain || undefined,
        overwrite: form.overwrite,
      });
      setFeedback(`Registered ${card.name} (${card.num_classes ?? "?"} classes).`);
      setShowRegister(false);
      void load();
    } catch (err) {
      setError(safeMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="task-content">
      <TabGuide tab="datasets" />
      <h2>Datasets</h2>
      <p className="lede">
        Browse the OpenPathAI dataset registry — and register a folder of
        class-named subdirectories as a custom tile dataset that the Train
        screen can use directly.
      </p>

      {error ? <div className="banner-err">{error}</div> : null}
      {feedback ? <div className="banner-ok">{feedback}</div> : null}

      <div className="toolbar">
        <button onClick={() => setShowRegister((v) => !v)}>
          {showRegister ? "Cancel registration" : "Register custom dataset"}
        </button>
        <span className="grow" />
        <button onClick={() => void load()} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {showRegister ? (
        <div className="card">
          <h3>Register a folder of class-named subfolders</h3>
          <p className="lede">
            Layout: <code>&lt;path&gt;/&lt;class_name&gt;/&lt;image&gt;.png</code>.
            Phase 7 walks the directory and writes a card under{" "}
            <code>$OPENPATHAI_HOME/datasets/&lt;name&gt;.yaml</code>.
          </p>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="ds_path">Folder path</label>
              <input
                id="ds_path"
                value={form.path}
                onChange={(e) => setForm({ ...form, path: e.target.value })}
                placeholder="/Users/dr/data/cohort_a"
              />
            </div>
            <div className="field">
              <label htmlFor="ds_name">Card name</label>
              <input
                id="ds_name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="cohort_a"
              />
            </div>
            <div className="field">
              <label htmlFor="ds_tissue">Tissue tags (comma-separated)</label>
              <input
                id="ds_tissue"
                value={form.tissue}
                onChange={(e) => setForm({ ...form, tissue: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="ds_license">License</label>
              <input
                id="ds_license"
                value={form.license}
                onChange={(e) => setForm({ ...form, license: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="ds_stain">Stain</label>
              <input
                id="ds_stain"
                value={form.stain}
                onChange={(e) => setForm({ ...form, stain: e.target.value })}
              />
            </div>
            <div className="field">
              <label
                htmlFor="ds_overwrite"
                style={{ display: "flex", gap: 8, alignItems: "center" }}
              >
                <input
                  id="ds_overwrite"
                  type="checkbox"
                  checked={form.overwrite}
                  style={{ width: "auto" }}
                  onChange={(e) =>
                    setForm({ ...form, overwrite: e.target.checked })
                  }
                />
                <span>Overwrite existing card with the same name</span>
              </label>
            </div>
          </div>
          <div className="toolbar" style={{ marginTop: 12 }}>
            <button onClick={submitRegister} disabled={busy}>
              {busy ? "Registering…" : "Register"}
            </button>
          </div>
        </div>
      ) : null}

      <div className="card">
        <h3>Registry ({items.length})</h3>
        {loading ? (
          <p>Loading…</p>
        ) : (
          <table className="panel-table bordered">
            <thead>
              <tr>
                <th>Name</th>
                <th>Display name</th>
                <th>Modality</th>
                <th>Classes</th>
                <th>License</th>
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
                    {d.num_classes ??
                      (Array.isArray(d.classes) ? d.classes.length : "")}
                  </td>
                  <td>{String(d.license ?? "")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
