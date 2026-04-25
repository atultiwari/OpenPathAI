import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type { NodeSummary, PipelineValidation } from "../../api/types";
import { Canvas } from "../../canvas/canvas";
import type { CanvasState } from "../../canvas/types";
import { newCanvas, toPipeline } from "../../canvas/types";
import {
  STARTER_PIPELINES,
  starterOps,
  type StarterPipeline,
} from "../../canvas/starters";
import { Inspector } from "../../inspector/inspector";
import { Palette } from "../../palette/palette";
import { safeMessage } from "../../lib/safe-string";
import { TabGuide } from "../../components/tab-guide";
import "./pipelines-screen.css";

type StatusBar = {
  kind: "info" | "ok" | "error";
  message: string;
};

export function PipelinesScreen() {
  const { client } = useAuth();
  const [canvas, setCanvas] = useState<CanvasState>(() => newCanvas());
  const [selection, setSelection] = useState<string | null>(null);
  const [paletteFilter, setPaletteFilter] = useState("");
  const [catalog, setCatalog] = useState<NodeSummary[]>([]);
  const [paletteLoading, setPaletteLoading] = useState(false);
  const [paletteError, setPaletteError] = useState<string | null>(null);
  const [validation, setValidation] = useState<PipelineValidation | null>(null);
  const [statusBar, setStatusBar] = useState<StatusBar | null>(null);
  const [busy, setBusy] = useState(false);
  const [starterMenuOpen, setStarterMenuOpen] = useState(false);
  const starterMenuRef = useRef<HTMLDivElement | null>(null);

  const catalogMap = useMemo(
    () => new Map(catalog.map((n) => [n.id, n])),
    [catalog]
  );
  const catalogIds = useMemo(
    () => new Set(catalog.map((n) => n.id)),
    [catalog]
  );

  useEffect(() => {
    let cancelled = false;
    setPaletteLoading(true);
    setPaletteError(null);
    client
      .listNodes()
      .then((response) => {
        if (!cancelled) setCatalog(response.items);
      })
      .catch((err) => {
        if (!cancelled) setPaletteError(safeMessage(err));
      })
      .finally(() => {
        if (!cancelled) setPaletteLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  // Close the starter popover on outside click.
  useEffect(() => {
    if (!starterMenuOpen) return;
    function onDocClick(event: MouseEvent) {
      if (
        starterMenuRef.current &&
        !starterMenuRef.current.contains(event.target as Node)
      ) {
        setStarterMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [starterMenuOpen]);

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
      setStatusBar({
        kind: report.valid ? "ok" : "error",
        message: report.valid
          ? "Pipeline is valid."
          : `Invalid: ${report.errors.length} error(s).`,
      });
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
        message: `Saved ${envelope.id} (graph ${envelope.graph_hash.slice(
          0,
          10
        )}).`,
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
    } catch (err) {
      setStatusBar({ kind: "error", message: safeMessage(err) });
    } finally {
      setBusy(false);
    }
  }, [canvas, client]);

  const loadStarter = useCallback(
    (starter: StarterPipeline) => {
      const next = starter.build();
      setCanvas(next);
      setSelection(null);
      setValidation(null);
      setStarterMenuOpen(false);
      setStatusBar({
        kind: "info",
        message: `Loaded starter "${starter.label}" — ${next.nodes.length} node(s).`,
      });
    },
    []
  );

  const isCanvasEmpty = canvas.nodes.length === 0;

  return (
    <div className="pipelines-screen">
      <header className="pipelines-header">
        <h2>Pipelines</h2>
        <span className="pill">{canvas.pipelineId}</span>
        <span className="pill">{canvas.mode}</span>
        {statusBar ? (
          <span
            className={
              statusBar.kind === "error"
                ? "pipelines-status-pill error"
                : statusBar.kind === "ok"
                ? "pipelines-status-pill ok"
                : "pipelines-status-pill"
            }
            title={statusBar.message}
          >
            {statusBar.message}
          </span>
        ) : null}
        <span className="grow" />
        <div className="toolbar-actions">
          <div className="starter-menu" ref={starterMenuRef}>
            <button
              type="button"
              className="starter-trigger"
              onClick={() => setStarterMenuOpen((open) => !open)}
              aria-haspopup="true"
              aria-expanded={starterMenuOpen}
              disabled={busy}
            >
              Load starter ▾
            </button>
            {starterMenuOpen ? (
              <div className="starter-popover" role="menu">
                {STARTER_PIPELINES.map((starter) => {
                  const ops = starterOps(starter);
                  const missing = catalog.length
                    ? ops.filter((op) => !catalogIds.has(op))
                    : [];
                  const disabled = missing.length > 0;
                  const title = disabled
                    ? `Disabled — missing op(s): ${missing.join(", ")}`
                    : starter.blurb;
                  return (
                    <button
                      key={starter.id}
                      type="button"
                      className="starter-row"
                      onClick={() => loadStarter(starter)}
                      disabled={disabled}
                      title={title}
                      role="menuitem"
                    >
                      <span className="starter-title">
                        {starter.label}
                        <span
                          className={`starter-tier-tag tier-${starter.tier}`}
                        >
                          {starter.tier}
                        </span>
                      </span>
                      <span className="starter-blurb">
                        {disabled
                          ? `Missing: ${missing.join(", ")}`
                          : starter.blurb}
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>
          <button onClick={handleValidate} disabled={busy}>
            Validate
          </button>
          <button onClick={handleSave} disabled={busy}>
            Save
          </button>
          <button onClick={handleRun} disabled={busy || isCanvasEmpty}>
            Run
          </button>
        </div>
      </header>

      <Palette
        nodes={catalog}
        loading={paletteLoading}
        error={paletteError}
        filter={paletteFilter}
        onFilterChange={setPaletteFilter}
      />

      <Canvas
        canvas={canvas}
        onChange={setCanvas}
        selection={selection}
        onSelect={setSelection}
        catalog={catalogMap}
      />

      {isCanvasEmpty ? (
        <div className="pipelines-empty" aria-live="polite">
          <h3>This canvas is empty</h3>
          <p>
            Drag a node from the palette on the left, or pick a starter
            pipeline from the toolbar to load a working example.
          </p>
          <div className="hint-row">
            <span className="hint-arrow">↙</span>
            <span>Palette</span>
            <span style={{ width: 24 }} />
            <span>Starter</span>
            <span className="hint-arrow">↗</span>
          </div>
          <div
            style={{
              marginTop: "var(--space-4)",
              pointerEvents: "auto",
              maxWidth: 640,
              textAlign: "left",
            }}
          >
            <TabGuide tab="pipelines" />
          </div>
        </div>
      ) : null}

      {validation && !validation.valid && validation.errors.length ? (
        <div className="pipelines-empty" style={{ pointerEvents: "auto" }}>
          <ul className="errors-list" style={{ maxWidth: 480 }}>
            {validation.errors.slice(0, 5).map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <Inspector
        canvas={canvas}
        selection={selection}
        catalog={catalogMap}
        onChange={setCanvas}
        onRename={onRename}
      />
    </div>
  );
}
