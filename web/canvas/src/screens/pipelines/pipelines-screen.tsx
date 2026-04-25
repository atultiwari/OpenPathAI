import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type { NodeSummary, PipelineValidation } from "../../api/types";
import { Canvas } from "../../canvas/canvas";
import type { CanvasState } from "../../canvas/types";
import { newCanvas, toPipeline } from "../../canvas/types";
import { Inspector } from "../../inspector/inspector";
import { Palette } from "../../palette/palette";
import { safeMessage } from "../../lib/safe-string";

export function PipelinesScreen() {
  const { client } = useAuth();
  const [canvas, setCanvas] = useState<CanvasState>(() => newCanvas());
  const [selection, setSelection] = useState<string | null>(null);
  const [paletteFilter, setPaletteFilter] = useState("");
  const [catalog, setCatalog] = useState<NodeSummary[]>([]);
  const [paletteLoading, setPaletteLoading] = useState(false);
  const [paletteError, setPaletteError] = useState<string | null>(null);
  const [validation, setValidation] = useState<PipelineValidation | null>(null);
  const [statusBar, setStatusBar] = useState<{
    kind: "info" | "ok" | "error";
    message: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);

  const catalogMap = useMemo(
    () => new Map(catalog.map((n) => [n.id, n])),
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

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "220px 1fr 320px",
        height: "calc(100vh - 48px)",
      }}
    >
      <Palette
        nodes={catalog}
        loading={paletteLoading}
        error={paletteError}
        filter={paletteFilter}
        onFilterChange={setPaletteFilter}
      />
      <main style={{ position: "relative" }}>
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
    </div>
  );
}
