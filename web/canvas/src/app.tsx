import { useCallback, useEffect, useMemo, useState } from "react";
import { AuthProvider, useAuth } from "./api/auth-context";
import type { NodeSummary, PipelineValidation } from "./api/types";
import { ApiError } from "./api/client";
import { Canvas } from "./canvas/canvas";
import { newCanvas, toPipeline } from "./canvas/types";
import type { CanvasState } from "./canvas/types";
import { Palette } from "./palette/palette";
import { Inspector } from "./inspector/inspector";
import { RunsPanel } from "./runs/runs-panel";
import { AuditPanel } from "./audit/audit-panel";
import { ModelsPanel } from "./models/models-panel";
import { DatasetsPanel } from "./datasets/datasets-panel";
import { safeMessage } from "./lib/safe-string";

type Tab = "canvas" | "runs" | "audit" | "models" | "datasets";

const TABS: { id: Tab; label: string }[] = [
  { id: "canvas", label: "Canvas" },
  { id: "runs", label: "Runs" },
  { id: "audit", label: "Audit" },
  { id: "models", label: "Models" },
  { id: "datasets", label: "Datasets" },
];

function TokenPrompt({
  onSubmit,
  baseUrl,
  setBaseUrl,
}: {
  onSubmit: (token: string) => void;
  baseUrl: string;
  setBaseUrl: (url: string) => void;
}) {
  const [draft, setDraft] = useState("");
  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h2>Connect to OpenPathAI API</h2>
        <p className="inspector-empty">
          Paste the bearer token printed by <code>openpathai serve</code>.
          The token is held in this tab's session memory only — closing the
          tab clears it.
        </p>
        <form
          className="token-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim()) onSubmit(draft.trim());
          }}
        >
          <div className="inspector-row">
            <label htmlFor="t_baseurl">Base URL</label>
            <input
              id="t_baseurl"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://127.0.0.1:7870"
            />
          </div>
          <div className="inspector-row">
            <label htmlFor="t_token">Bearer token</label>
            <input
              id="t_token"
              type="password"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
            />
          </div>
          <div className="actions">
            <button type="submit" disabled={!draft.trim()}>
              Connect
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function CanvasShell() {
  const { client, token, setToken, baseUrl, setBaseUrl } = useAuth();
  const [tab, setTab] = useState<Tab>("canvas");
  const [canvas, setCanvas] = useState<CanvasState>(() => newCanvas());
  const [selection, setSelection] = useState<string | null>(null);
  const [paletteFilter, setPaletteFilter] = useState("");
  const [catalog, setCatalog] = useState<NodeSummary[]>([]);
  const [paletteLoading, setPaletteLoading] = useState(false);
  const [paletteError, setPaletteError] = useState<string | null>(null);
  const [validation, setValidation] = useState<PipelineValidation | null>(
    null
  );
  const [statusBar, setStatusBar] = useState<{
    kind: "info" | "ok" | "error";
    message: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);

  const catalogMap = useMemo(
    () => new Map(catalog.map((n) => [n.id, n])),
    [catalog]
  );

  // Load /v1/nodes when the token + base url change.
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setPaletteLoading(true);
    setPaletteError(null);
    client
      .listNodes()
      .then((response) => {
        if (!cancelled) setCatalog(response.items);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          setToken(null);
        }
        setPaletteError(safeMessage(err));
      })
      .finally(() => {
        if (!cancelled) setPaletteLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client, token, setToken]);

  const onRename = useCallback(
    (oldId: string, newId: string) => {
      const trimmed = newId.trim();
      if (!trimmed || trimmed === oldId) return;
      if (canvas.nodes.some((n) => n.id === trimmed)) return;
      const nextNodes = canvas.nodes.map((n) =>
        n.id === oldId ? { ...n, id: trimmed } : n
      );
      const nextEdges = canvas.edges.map((e) => ({
        ...e,
        source: e.source === oldId ? trimmed : e.source,
        target: e.target === oldId ? trimmed : e.target,
      }));
      setCanvas({ ...canvas, nodes: nextNodes, edges: nextEdges });
      if (selection === oldId) setSelection(trimmed);
    },
    [canvas, selection]
  );

  const handleValidate = useCallback(async () => {
    setBusy(true);
    setStatusBar({ kind: "info", message: "Validating…" });
    try {
      const report = await client.validatePipeline(toPipeline(canvas));
      setValidation(report);
      if (report.valid) {
        setStatusBar({ kind: "ok", message: "Pipeline is valid." });
      } else {
        setStatusBar({
          kind: "error",
          message: `Invalid: ${report.errors.length} error(s).`,
        });
      }
    } catch (err) {
      setStatusBar({ kind: "error", message: safeMessage(err) });
    } finally {
      setBusy(false);
    }
  }, [canvas, client]);

  const handleSave = useCallback(async () => {
    setBusy(true);
    setStatusBar({ kind: "info", message: "Saving…" });
    try {
      const envelope = await client.putPipeline(
        canvas.pipelineId,
        toPipeline(canvas)
      );
      setStatusBar({
        kind: "ok",
        message: `Saved ${envelope.id} (graph ${envelope.graph_hash.slice(0, 10)}).`,
      });
    } catch (err) {
      setStatusBar({ kind: "error", message: safeMessage(err) });
    } finally {
      setBusy(false);
    }
  }, [canvas, client]);

  const handleRun = useCallback(async () => {
    setBusy(true);
    setStatusBar({ kind: "info", message: "Submitting run…" });
    try {
      const record = await client.createRun({ pipeline: toPipeline(canvas) });
      setStatusBar({
        kind: "ok",
        message: `Run ${record.run_id.slice(0, 12)} ${record.status}.`,
      });
      setTab("runs");
    } catch (err) {
      setStatusBar({ kind: "error", message: safeMessage(err) });
    } finally {
      setBusy(false);
    }
  }, [canvas, client]);

  const tabContent = useMemo(() => {
    switch (tab) {
      case "runs":
        return <RunsPanel />;
      case "audit":
        return <AuditPanel />;
      case "models":
        return <ModelsPanel />;
      case "datasets":
        return <DatasetsPanel />;
      case "canvas":
      default:
        return null;
    }
  }, [tab]);

  if (!token) {
    return (
      <TokenPrompt
        baseUrl={baseUrl}
        setBaseUrl={setBaseUrl}
        onSubmit={setToken}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <h1>OpenPathAI Canvas</h1>
        <span className="pill">{baseUrl}</span>
        <nav>
          {TABS.map((t) => (
            <button
              key={t.id}
              className={t.id === tab ? "active" : undefined}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
          <button onClick={() => setToken(null)} title="Forget token">
            Sign out
          </button>
        </nav>
      </header>

      {tab === "canvas" ? (
        <>
          <Palette
            nodes={catalog}
            loading={paletteLoading}
            error={paletteError}
            filter={paletteFilter}
            onFilterChange={setPaletteFilter}
          />
          <main style={{ position: "relative", gridArea: "canvas" }}>
            <div className="canvas-toolbar">
              <button onClick={handleValidate} disabled={busy}>
                Validate
              </button>
              <button onClick={handleSave} disabled={busy}>
                Save
              </button>
              <button
                onClick={handleRun}
                disabled={busy || canvas.nodes.length === 0}
              >
                Run
              </button>
            </div>
            <Canvas
              canvas={canvas}
              onChange={setCanvas}
              selection={selection}
              onSelect={setSelection}
              catalog={catalogMap}
            />
            {statusBar ? (
              <div
                className={
                  statusBar.kind === "error"
                    ? "canvas-status error"
                    : statusBar.kind === "ok"
                    ? "canvas-status ok"
                    : "canvas-status"
                }
              >
                {statusBar.message}
                {validation && !validation.valid && validation.errors.length ? (
                  <ul className="errors-list">
                    {validation.errors.slice(0, 5).map((e) => (
                      <li key={e}>{e}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </main>
          <Inspector
            canvas={canvas}
            selection={selection}
            catalog={catalogMap}
            onChange={setCanvas}
            onRename={onRename}
          />
        </>
      ) : (
        <main
          style={{ gridArea: "palette / palette / inspector / inspector" }}
        >
          {tabContent}
        </main>
      )}
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <CanvasShell />
    </AuthProvider>
  );
}
