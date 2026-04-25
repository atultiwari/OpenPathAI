// Phase 21 — heatmap-controls panel for the Slides viewer.

import { useEffect, useState } from "react";
import type { ApiClient } from "../../api/client";
import type { HeatmapSummary, ModelSummary } from "../../api/types";

interface HeatmapControlsProps {
  api: ApiClient;
  slideId: string;
  heatmaps: HeatmapSummary[];
  selected: HeatmapSummary | null;
  onSelect: (h: HeatmapSummary | null) => void;
  onCreated: (h: HeatmapSummary) => void;
  opacity: number;
  setOpacity: (alpha: number) => void;
  onError: (message: string) => void;
}

export function HeatmapControls({
  api,
  slideId,
  heatmaps,
  selected,
  onSelect,
  onCreated,
  opacity,
  setOpacity,
  onError,
}: HeatmapControlsProps) {
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [modelName, setModelName] = useState<string>("heuristic-synthetic");
  const [classes, setClasses] = useState<string>("benign,malignant");
  const [grid, setGrid] = useState<number>(8);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .listModels({ kind: "classifier", limit: 50 })
      .then((res) => setModels(res.items))
      .catch((err: unknown) => {
        // Models are optional for heatmap compute (synthetic stays valid).
        const message = err instanceof Error ? err.message : "models unavailable";
        onError(message);
      });
  }, [api, onError]);

  async function compute() {
    setBusy(true);
    try {
      const created = await api.computeHeatmap({
        slide_id: slideId,
        model_name: modelName,
        classes: classes
          .split(",")
          .map((c) => c.trim())
          .filter(Boolean),
        tile_grid: grid,
      });
      onCreated(created);
      onSelect(created);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "heatmap failed";
      onError(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ display: "grid", gap: ".5rem" }}>
      <h3 style={{ margin: 0 }}>Heatmap overlay</h3>
      <div className="inspector-row">
        <label htmlFor="hm_model">Model</label>
        <select
          id="hm_model"
          value={modelName}
          onChange={(e) => setModelName(e.target.value)}
        >
          <option value="heuristic-synthetic">heuristic-synthetic</option>
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.display_name}
            </option>
          ))}
        </select>
      </div>
      <div className="inspector-row">
        <label htmlFor="hm_classes">Classes</label>
        <input
          id="hm_classes"
          value={classes}
          onChange={(e) => setClasses(e.target.value)}
          placeholder="benign,malignant"
        />
      </div>
      <div className="inspector-row">
        <label htmlFor="hm_grid">Tile grid</label>
        <input
          id="hm_grid"
          type="number"
          min={2}
          max={64}
          value={grid}
          onChange={(e) => setGrid(Number.parseInt(e.target.value, 10) || 8)}
        />
      </div>
      <button type="button" onClick={compute} disabled={busy}>
        {busy ? "Computing…" : "Compute heatmap"}
      </button>
      {heatmaps.length > 0 ? (
        <>
          <div className="inspector-row">
            <label htmlFor="hm_existing">Layer</label>
            <select
              id="hm_existing"
              value={selected?.heatmap_id ?? ""}
              onChange={(e) => {
                const next =
                  heatmaps.find((h) => h.heatmap_id === e.target.value) ?? null;
                onSelect(next);
              }}
            >
              <option value="">— none —</option>
              {heatmaps.map((h) => (
                <option key={h.heatmap_id} value={h.heatmap_id}>
                  {h.heatmap_id} · {h.resolved_model_name}
                </option>
              ))}
            </select>
          </div>
          <div className="inspector-row">
            <label htmlFor="hm_opacity">Opacity</label>
            <input
              id="hm_opacity"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={opacity}
              onChange={(e) => setOpacity(Number.parseFloat(e.target.value))}
            />
          </div>
          {selected?.fallback_reason ? (
            <p
              className="banner-warn"
              role="alert"
              style={{ fontSize: ".75rem" }}
            >
              fallback: {selected.fallback_reason}
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
