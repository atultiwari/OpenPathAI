import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type {
  DatasetCard,
  DatasetDownloadResult,
  DatasetStatus,
} from "../../api/types";
import { redactPayload } from "../../lib/redact";
import { safeMessage } from "../../lib/safe-string";
import { TabGuide } from "../../components/tab-guide";

type RowStatus =
  | { kind: "unknown" }
  | { kind: "checking" }
  | { kind: "absent"; target: string }
  | { kind: "present"; target: string; files: number; bytes: number }
  | { kind: "downloading" }
  | { kind: "manual"; message: string }
  | { kind: "missing_backend"; message: string; extra: string | null }
  | { kind: "error"; message: string };

function formatBytes(n: number): string {
  if (n === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = n;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[i]}`;
}

export function DatasetsScreen() {
  const { client } = useAuth();
  const [items, setItems] = useState<DatasetCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRegister, setShowRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [rowStatus, setRowStatus] = useState<Record<string, RowStatus>>({});
  const [expanded, setExpanded] = useState<string | null>(null);
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

  // Probe download status for every card on first load + on refresh.
  useEffect(() => {
    if (!items.length) return;
    let cancelled = false;
    (async () => {
      for (const card of items) {
        if (cancelled) return;
        const name = String(card.name ?? "");
        if (!name) continue;
        try {
          const status: DatasetStatus = await client.getDatasetStatus(name);
          if (cancelled) return;
          setRowStatus((prev) => ({
            ...prev,
            [name]: status.present
              ? {
                  kind: "present",
                  target: status.target_dir,
                  files: status.files,
                  bytes: status.bytes,
                }
              : { kind: "absent", target: status.target_dir },
          }));
        } catch {
          // best-effort
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [items, client]);

  const downloadOne = useCallback(
    async (card: DatasetCard) => {
      const name = String(card.name ?? "");
      if (!name) return;
      const method = (card.download as Record<string, unknown> | undefined)?.method;
      setRowStatus((prev) => ({ ...prev, [name]: { kind: "downloading" } }));
      try {
        const result: DatasetDownloadResult = await client.downloadDataset(
          name,
          {}
        );
        if (result.status === "downloaded") {
          setRowStatus((prev) => ({
            ...prev,
            [name]: {
              kind: "present",
              target: result.target_dir,
              files: result.files_written,
              bytes: result.bytes_written ?? 0,
            },
          }));
          setFeedback(
            `Downloaded ${result.files_written} file(s) for ${name} → ${result.target_dir}`
          );
        } else if (result.status === "manual") {
          setRowStatus((prev) => ({
            ...prev,
            [name]: {
              kind: "manual",
              message: result.message ?? "See card instructions.",
            },
          }));
        } else if (result.status === "missing_backend") {
          setRowStatus((prev) => ({
            ...prev,
            [name]: {
              kind: "missing_backend",
              message: result.message ?? "Required extra is not installed.",
              extra: result.extra_required,
            },
          }));
        } else {
          setRowStatus((prev) => ({
            ...prev,
            [name]: {
              kind: "error",
              message: result.message ?? `Download ${result.status}`,
            },
          }));
        }
      } catch (err) {
        setRowStatus((prev) => ({
          ...prev,
          [name]: { kind: "error", message: safeMessage(err) },
        }));
      }
      void method; // method captured for future per-method UI tweaks
    },
    [client]
  );

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
                <th>Cls</th>
                <th>License</th>
                <th>Status</th>
                <th>On disk</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {items.flatMap((d, idx) => {
                const name = String(d.name ?? `dataset-${idx}`);
                const status = rowStatus[name] ?? { kind: "unknown" };
                const method = (
                  d.download as Record<string, unknown> | undefined
                )?.method as string | undefined;
                const isManual = method === "manual";
                const detailOpen = expanded === name;
                const rows = [
                  <tr
                    key={name}
                    onClick={() =>
                      setExpanded((curr) => (curr === name ? null : name))
                    }
                    style={{ cursor: "pointer" }}
                  >
                    <td>
                      <code>{name}</code>
                    </td>
                    <td>{d.display_name ?? ""}</td>
                    <td>{d.modality ?? ""}</td>
                    <td>
                      {d.num_classes ??
                        (Array.isArray(d.classes) ? d.classes.length : "")}
                    </td>
                    <td>{String(d.license ?? "")}</td>
                    <td>
                      {status.kind === "present" ? (
                        <span className="tag" style={{ borderColor: "var(--color-accent-2)", color: "var(--color-accent-2)" }}>
                          ✓ {status.files} file(s) · {formatBytes(status.bytes)}
                        </span>
                      ) : status.kind === "downloading" ? (
                        <span className="tag" style={{ color: "var(--color-accent)" }}>
                          downloading…
                        </span>
                      ) : status.kind === "manual" ? (
                        <span className="tag gated">manual ↗</span>
                      ) : status.kind === "missing_backend" ? (
                        <span className="tag gated">install extra</span>
                      ) : status.kind === "error" ? (
                        <span className="tag" style={{ borderColor: "var(--color-error)", color: "var(--color-error)" }}>
                          error
                        </span>
                      ) : status.kind === "absent" ? (
                        <span className="tag">not downloaded</span>
                      ) : (
                        <span className="tag">checking…</span>
                      )}
                    </td>
                    <td>
                      <code style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                        {"target" in status ? status.target : "—"}
                      </code>
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        onClick={() => void downloadOne(d)}
                        disabled={status.kind === "downloading"}
                      >
                        {isManual
                          ? "Show instructions"
                          : status.kind === "present"
                          ? "Re-download"
                          : "Download"}
                      </button>
                    </td>
                  </tr>,
                ];
                if (detailOpen) {
                  rows.push(
                    <tr key={`${name}-detail`} style={{ background: "var(--color-bg)" }}>
                      <td colSpan={8}>
                        <div style={{ padding: "10px 4px", display: "grid", gap: 8 }}>
                          <div>
                            <strong style={{ fontSize: 12 }}>Card download metadata</strong>
                          </div>
                          <dl
                            style={{
                              display: "grid",
                              gridTemplateColumns: "max-content 1fr",
                              columnGap: 16,
                              rowGap: 4,
                              margin: 0,
                              fontSize: 12,
                            }}
                          >
                            <dt>Method</dt>
                            <dd>{String(method ?? "—")}</dd>
                            <dt>Stain</dt>
                            <dd>{String((d as Record<string, unknown>).stain ?? "—")}</dd>
                            <dt>Tissue</dt>
                            <dd>
                              {Array.isArray((d as Record<string, unknown>).tissue)
                                ? ((d as Record<string, unknown>).tissue as unknown[]).join(", ")
                                : "—"}
                            </dd>
                            {status.kind === "manual" || status.kind === "missing_backend" || status.kind === "error" ? (
                              <>
                                <dt>Detail</dt>
                                <dd style={{ whiteSpace: "pre-wrap" }}>
                                  {(status as { message?: string }).message ?? ""}
                                  {status.kind === "missing_backend" && status.extra ? (
                                    <>
                                      {"\n\n"}
                                      Install with: <code>uv pip install -e ".{status.extra.split(" ")[0]}"</code>
                                    </>
                                  ) : null}
                                </dd>
                              </>
                            ) : null}
                          </dl>
                        </div>
                      </td>
                    </tr>
                  );
                }
                return rows;
              })}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
