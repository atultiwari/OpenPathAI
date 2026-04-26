import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type {
  HFTokenStatus,
  ModelDownloadResult,
  ModelSizeEstimate,
  ModelStatus,
  ModelSummary,
} from "../../api/types";
import { safeMessage } from "../../lib/safe-string";
import { TabGuide } from "../../components/tab-guide";
import { StorageBanner } from "../../components/storage-banner";
import { navigateToTab } from "../../components/quick-start-card";

const KIND_LABEL: Record<string, string> = {
  classifier: "Tier A — Classifier zoo",
  foundation: "Tier C — Foundation models",
  detection: "Tier D — Detection",
  segmentation: "Tier D — Segmentation",
};

type RowState =
  | { kind: "unknown" }
  | { kind: "checking" }
  | { kind: "absent"; target: string | null }
  | { kind: "present"; target: string | null; sizeBytes: number; files: number }
  | { kind: "downloading" }
  | {
      kind: "gated";
      message: string;
    }
  | {
      kind: "missing_backend";
      message: string;
      installCmd: string | null;
    }
  | { kind: "error"; message: string };

function formatBytes(n: number | null | undefined): string {
  if (!n) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = n;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[i]}`;
}

export function ModelsScreen() {
  const { client } = useAuth();
  const [items, setItems] = useState<ModelSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<string>("");
  const [selected, setSelected] = useState<ModelSummary | null>(null);
  const [rowState, setRowState] = useState<Record<string, RowState>>({});
  const [sizeEstimates, setSizeEstimates] = useState<
    Record<string, ModelSizeEstimate>
  >({});
  const [hfStatus, setHfStatus] = useState<HFTokenStatus | null>(null);

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

  // Live HF token state — surfaced on the detail modal so the user
  // doesn't see a generic "set HF_TOKEN" message after they already
  // configured one in Settings.
  useEffect(() => {
    let cancelled = false;
    client
      .getHfTokenStatus()
      .then((s) => {
        if (!cancelled) setHfStatus(s);
      })
      .catch(() => {
        // best-effort
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  // Probe per-row status as the rows arrive.
  useEffect(() => {
    if (!items.length) return;
    let cancelled = false;
    (async () => {
      for (const m of items) {
        if (cancelled) return;
        try {
          const status: ModelStatus = await client.getModelStatus(m.id);
          if (cancelled) return;
          setRowState((prev) => ({
            ...prev,
            [m.id]: status.present
              ? {
                  kind: "present",
                  target: status.target_dir,
                  sizeBytes: status.size_bytes,
                  files: status.file_count,
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

  // Pull HF size estimates lazily for every row that has an hf_repo.
  useEffect(() => {
    if (!items.length) return;
    let cancelled = false;
    (async () => {
      for (const m of items) {
        if (cancelled) return;
        if (!m.hf_repo) continue;
        try {
          const est = await client.getModelSizeEstimate(m.id);
          if (cancelled) return;
          setSizeEstimates((prev) => ({ ...prev, [m.id]: est }));
        } catch {
          // network unreachable / API down — UI shows "—"
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [items, client]);

  const downloadOne = useCallback(
    async (model: ModelSummary) => {
      setRowState((prev) => ({ ...prev, [model.id]: { kind: "downloading" } }));
      try {
        const result: ModelDownloadResult = await client.downloadModel(model.id);
        if (result.status === "downloaded" || result.status === "already_present") {
          setRowState((prev) => ({
            ...prev,
            [model.id]: {
              kind: "present",
              target: result.target_dir,
              sizeBytes: result.size_bytes,
              files: result.file_count,
            },
          }));
        } else if (result.status === "gated") {
          setRowState((prev) => ({
            ...prev,
            [model.id]: {
              kind: "gated",
              message: result.message ?? "Gated — request access first.",
            },
          }));
        } else if (result.status === "missing_backend") {
          setRowState((prev) => ({
            ...prev,
            [model.id]: {
              kind: "missing_backend",
              message: result.message ?? "Required extra is not installed.",
              installCmd: result.install_cmd,
            },
          }));
        } else {
          setRowState((prev) => ({
            ...prev,
            [model.id]: {
              kind: "error",
              message: result.message ?? `Download ${result.status}`,
            },
          }));
        }
      } catch (err) {
        setRowState((prev) => ({
          ...prev,
          [model.id]: { kind: "error", message: safeMessage(err) },
        }));
      }
    },
    [client]
  );

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
      <TabGuide tab="models" />
      <StorageBanner paths={["models", "hf_hub_cache"]} />
      <h2>Models</h2>
      <p className="lede">
        The OpenPathAI model zoo. Status / Size / Action columns let you
        download backbones to disk before training. Gated foundation models
        require a Hugging Face token (configure under Settings → Hugging Face).
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
                <th>Status</th>
                <th>Size</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => {
                const state = rowState[m.id] ?? { kind: "unknown" };
                const est = sizeEstimates[m.id];
                const sizeText =
                  state.kind === "present"
                    ? formatBytes(state.sizeBytes)
                    : est?.size_bytes
                    ? `~${formatBytes(est.size_bytes)}`
                    : est?.reason
                    ? "—"
                    : "…";
                const canDownload =
                  m.hf_repo &&
                  (state.kind === "absent" ||
                    state.kind === "error" ||
                    state.kind === "missing_backend");
                const downloading = state.kind === "downloading";
                const isGated = m.gated && state.kind === "gated";
                return (
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
                      {state.kind === "present" ? (
                        <span
                          className="tag"
                          style={{
                            borderColor: "var(--color-accent-2)",
                            color: "var(--color-accent-2)",
                          }}
                        >
                          ✓ downloaded
                        </span>
                      ) : downloading ? (
                        <span
                          className="tag"
                          style={{ color: "var(--color-accent)" }}
                        >
                          downloading…
                        </span>
                      ) : state.kind === "gated" ? (
                        <span className="tag gated">request access</span>
                      ) : state.kind === "missing_backend" ? (
                        <span className="tag gated">install extra</span>
                      ) : state.kind === "error" ? (
                        <span
                          className="tag"
                          style={{
                            borderColor: "var(--color-error)",
                            color: "var(--color-error)",
                          }}
                        >
                          error
                        </span>
                      ) : state.kind === "absent" ? (
                        <span className="tag">not downloaded</span>
                      ) : (
                        <span className="tag">checking…</span>
                      )}
                    </td>
                    <td>
                      <code style={{ fontSize: 11 }}>{sizeText}</code>
                    </td>
                    <td style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {canDownload && !isGated ? (
                        <button
                          onClick={() => void downloadOne(m)}
                          disabled={downloading}
                        >
                          Download
                        </button>
                      ) : null}
                      {state.kind === "present" ? (
                        <button onClick={() => void downloadOne(m)}>
                          Re-download
                        </button>
                      ) : null}
                      {state.kind === "missing_backend" && state.installCmd ? (
                        <button onClick={() => navigateToTab("settings")}>
                          Settings
                        </button>
                      ) : null}
                      <button onClick={() => setSelected(m)}>Details</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}

      {selected ? (
        <ModelDetailModal
          model={selected}
          onClose={() => setSelected(null)}
          state={rowState[selected.id]}
          sizeEstimate={sizeEstimates[selected.id]}
          hfStatus={hfStatus}
          onDownload={() => void downloadOne(selected)}
        />
      ) : null}
    </section>
  );
}

function ModelDetailModal({
  model,
  onClose,
  state,
  sizeEstimate,
  hfStatus,
  onDownload,
}: {
  model: ModelSummary;
  onClose: () => void;
  state: RowState | undefined;
  sizeEstimate: ModelSizeEstimate | undefined;
  hfStatus: HFTokenStatus | null;
  onDownload: () => void;
}) {
  const hfUrl = model.hf_repo
    ? `https://huggingface.co/${model.hf_repo}`
    : null;
  const tokenPresent = hfStatus?.present === true;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h2>{model.id}</h2>
        <p className="lede">{model.display_name}</p>

        {model.gated ? (
          tokenPresent ? (
            <div className="banner-ok">
              ✅ Hugging Face token configured (source:{" "}
              <code>{hfStatus?.source}</code>). If you've been granted access on
              the upstream HF page, click <strong>Download</strong> to pull
              weights into the local cache.
            </div>
          ) : (
            <div className="banner-warn">
              This model is gated on Hugging Face. Configure a token under{" "}
              <button
                type="button"
                onClick={() => {
                  onClose();
                  navigateToTab("settings");
                }}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--color-accent)",
                  textDecoration: "underline",
                  cursor: "pointer",
                  padding: 0,
                  font: "inherit",
                }}
              >
                Settings → Hugging Face
              </button>{" "}
              after requesting access on the upstream page below.
            </div>
          )
        ) : null}

        {state?.kind === "present" ? (
          <div className="banner-ok" style={{ marginTop: 8 }}>
            ✅ Downloaded: {state.files} file(s),{" "}
            <code>{formatBytes(state.sizeBytes)}</code> at{" "}
            <code>{state.target ?? "—"}</code>
          </div>
        ) : null}
        {state?.kind === "missing_backend" && state.installCmd ? (
          <div className="banner-warn" style={{ marginTop: 8 }}>
            Missing extra. Run: <code>{state.installCmd}</code>
          </div>
        ) : null}
        {state?.kind === "error" ? (
          <div className="banner-err" style={{ marginTop: 8 }}>
            {state.message}
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
            <tr>
              <th>Estimated download size</th>
              <td>
                {sizeEstimate?.size_bytes
                  ? `~${formatBytes(sizeEstimate.size_bytes)} (${
                      sizeEstimate.file_count ?? "?"
                    } file(s))`
                  : sizeEstimate?.reason ?? "querying…"}
              </td>
            </tr>
          </tbody>
        </table>

        <div
          className="token-form actions"
          style={{ marginTop: 16, gap: 8, flexWrap: "wrap" }}
        >
          {model.hf_repo &&
          (state?.kind === "absent" || state?.kind === "error") ? (
            <button onClick={onDownload}>Download</button>
          ) : null}
          {model.gated && hfUrl ? (
            <a
              href={hfUrl}
              target="_blank"
              rel="noreferrer"
              style={{
                background: "var(--color-panel-2)",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                padding: "8px 12px",
                color: "var(--color-accent)",
                textDecoration: "none",
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
