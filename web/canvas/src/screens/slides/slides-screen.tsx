// Phase 21 — Slides screen: upload, list, viewer + heatmap overlay.

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../api/auth-context";
import { BadgeStrip } from "../../components/tier-badges";
import { redactString } from "../../lib/redact";
import type { HeatmapSummary, RunMode, SlideSummary, TierLevel } from "../../api/types";
import { HeatmapControls } from "./heatmap-controls";
import { SlideViewer } from "./slide-viewer";

export function SlidesScreen() {
  const { client: api } = useAuth();

  const [slides, setSlides] = useState<SlideSummary[]>([]);
  const [selected, setSelected] = useState<SlideSummary | null>(null);
  const [heatmaps, setHeatmaps] = useState<HeatmapSummary[]>([]);
  const [activeHeatmap, setActiveHeatmap] = useState<HeatmapSummary | null>(null);
  const [opacity, setOpacity] = useState(0.6);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tier] = useState<TierLevel>("Standard");
  const [mode] = useState<RunMode>("exploratory");

  const refreshSlides = useCallback(async () => {
    try {
      const list = await api.listSlides();
      setSlides(list.items);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "list failed";
      setError(redactString(message));
    }
  }, [api]);

  const refreshHeatmaps = useCallback(
    async (slideId: string) => {
      try {
        const list = await api.listHeatmaps({ slide_id: slideId });
        setHeatmaps(list.items);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "heatmap list failed";
        setError(redactString(message));
      }
    },
    [api]
  );

  useEffect(() => {
    void refreshSlides();
  }, [refreshSlides]);

  useEffect(() => {
    if (selected) {
      void refreshHeatmaps(selected.slide_id);
    } else {
      setHeatmaps([]);
      setActiveHeatmap(null);
    }
  }, [selected, refreshHeatmaps]);

  async function onUpload(file: File) {
    setBusy(true);
    setError(null);
    try {
      const created = await api.uploadSlide(file);
      await refreshSlides();
      setSelected(created);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "upload failed";
      setError(redactString(message));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(slide: SlideSummary) {
    if (!confirm(`Delete slide ${slide.filename}?`)) return;
    try {
      await api.deleteSlide(slide.slide_id);
      if (selected?.slide_id === slide.slide_id) {
        setSelected(null);
      }
      await refreshSlides();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "delete failed";
      setError(redactString(message));
    }
  }

  return (
    <section className="task-panel" aria-labelledby="slides-heading">
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "1rem 1.5rem",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <div>
          <h2 id="slides-heading" style={{ margin: 0 }}>
            Slides
          </h2>
          <p
            className="inspector-empty"
            style={{ margin: ".25rem 0 0 0", fontSize: ".75rem" }}
          >
            Upload a slide → pan / zoom in OpenSeadragon → optionally
            overlay a heatmap.
          </p>
        </div>
        <BadgeStrip tier={tier} mode={mode} />
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "320px 1fr",
          gap: "1.5rem",
          padding: "1.5rem",
          height: "calc(100vh - 48px - 64px)",
          overflow: "hidden",
        }}
      >
        <aside
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "1rem",
            overflow: "auto",
          }}
        >
          <div className="card dropzone">
            <h3 style={{ margin: 0 }}>Upload slide</h3>
            <input
              type="file"
              accept="image/png,image/jpeg,image/tiff,image/x-tiff,.svs,.ndpi,.mrxs,.tiff,.tif"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  void onUpload(file);
                  e.target.value = "";
                }
              }}
            />
            <p className="inspector-empty" style={{ fontSize: ".7rem" }}>
              Single-plane TIFFs work without openslide. Real WSI
              (.svs / .ndpi / .mrxs) needs the [wsi] extra on the
              server.
            </p>
            {error ? <p className="banner-err">{error}</p> : null}
            {busy ? (
              <p className="inspector-empty">Uploading…</p>
            ) : null}
          </div>

          <div className="card" style={{ display: "grid", gap: ".5rem" }}>
            <h3 style={{ margin: 0 }}>Library ({slides.length})</h3>
            {slides.length === 0 ? (
              <p className="inspector-empty">No slides yet.</p>
            ) : (
              slides.map((slide) => (
                <button
                  key={slide.slide_id}
                  type="button"
                  className={
                    selected?.slide_id === slide.slide_id
                      ? "nav-item active"
                      : "nav-item"
                  }
                  onClick={() => setSelected(slide)}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-start",
                    gap: ".25rem",
                  }}
                >
                  <strong>{slide.filename}</strong>
                  <small className="inspector-empty">
                    {slide.width} × {slide.height} · {slide.backend}
                  </small>
                </button>
              ))
            )}
          </div>

          {selected ? (
            <HeatmapControls
              api={api}
              slideId={selected.slide_id}
              heatmaps={heatmaps}
              selected={activeHeatmap}
              onSelect={setActiveHeatmap}
              onCreated={(h) =>
                setHeatmaps((prev) => [...prev.filter((x) => x.heatmap_id !== h.heatmap_id), h])
              }
              opacity={opacity}
              setOpacity={setOpacity}
              onError={(m) => setError(redactString(m))}
            />
          ) : null}

          {selected ? (
            <button
              type="button"
              className="nav-item"
              onClick={() => onDelete(selected)}
              style={{ color: "var(--color-text-dim)" }}
            >
              Delete slide
            </button>
          ) : null}
        </aside>

        <main style={{ overflow: "auto" }}>
          {selected ? (
            <SlideViewer
              key={selected.slide_id + (activeHeatmap?.heatmap_id ?? "")}
              slideDziUrl={api.slideDziUrl(selected.slide_id)}
              heatmapDziUrl={
                activeHeatmap
                  ? api.heatmapDziUrl(activeHeatmap.heatmap_id)
                  : null
              }
              heatmapOpacity={opacity}
            />
          ) : (
            <div className="card" style={{ padding: "2rem", textAlign: "center" }}>
              <p>Select a slide on the left to view it.</p>
            </div>
          )}
        </main>
      </div>
    </section>
  );
}
