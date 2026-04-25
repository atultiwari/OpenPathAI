// Phase 21 — thin React shell around OpenSeadragon.
//
// The component takes a slide DZI url + an optional heatmap DZI url +
// an alpha (0..1). All OpenSeadragon calls live behind a single dynamic
// import so unit tests can mock the module wholesale and the bundle
// stays in its own chunk (refinement #3).

import { useEffect, useMemo, useRef } from "react";
import { useAuth } from "../../api/auth-context";

interface SlideViewerProps {
  slideDziUrl: string;
  heatmapDziUrl?: string | null;
  heatmapOpacity?: number;
  className?: string;
  onTileClick?: (point: { x: number; y: number }) => void;
}

interface ViewerInstance {
  open: (sources: string | string[]) => void;
  destroy: () => void;
  addHandler: (event: string, handler: (...args: unknown[]) => void) => void;
  world: { getItemCount: () => number; getItemAt: (i: number) => Overlay };
  addTiledImage: (config: AddTiledImageOptions) => void;
}

interface Overlay {
  setOpacity: (alpha: number) => void;
}

interface AddTiledImageOptions {
  tileSource: string;
  opacity: number;
  loadTilesWithAjax?: boolean;
  ajaxHeaders?: Record<string, string>;
  success?: () => void;
}

export function SlideViewer({
  slideDziUrl,
  heatmapDziUrl,
  heatmapOpacity = 0.6,
  className,
  onTileClick,
}: SlideViewerProps) {
  const { token } = useAuth();
  const hostRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<ViewerInstance | null>(null);

  // The id is stable per-mount; OpenSeadragon needs a real DOM node.
  const id = useMemo(
    () => `osd-${Math.random().toString(36).slice(2, 10)}`,
    []
  );

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      const mod = await import("openseadragon");
      const OpenSeadragon = mod.default ?? (mod as unknown as typeof mod.default);
      if (cancelled || !hostRef.current) return;
      // Bearer token must travel with every DZI XML descriptor + tile
      // PNG request — both are auth-gated. OpenSeadragon's
      // `loadTilesWithAjax + ajaxHeaders` injects the header on every
      // fetch so a bare <img>-style tile pull doesn't 401.
      const ajaxHeaders: Record<string, string> = token
        ? { Authorization: `Bearer ${token}` }
        : {};
      const viewer = OpenSeadragon({
        id,
        prefixUrl:
          "https://cdn.jsdelivr.net/npm/openseadragon@4/build/openseadragon/images/",
        showNavigationControl: true,
        gestureSettingsMouse: { clickToZoom: false },
        crossOriginPolicy: "Anonymous",
        loadTilesWithAjax: true,
        ajaxHeaders,
        ajaxWithCredentials: false,
        tileSources: slideDziUrl,
      }) as unknown as ViewerInstance;
      viewerRef.current = viewer;
      if (heatmapDziUrl) {
        viewer.addTiledImage({
          tileSource: heatmapDziUrl,
          opacity: heatmapOpacity,
          loadTilesWithAjax: true,
          ajaxHeaders,
        });
      }
      if (onTileClick) {
        viewer.addHandler("canvas-click", (...args: unknown[]) => {
          const event = args[0] as
            | { position?: { x?: number; y?: number } }
            | undefined;
          const x = event?.position?.x ?? 0;
          const y = event?.position?.y ?? 0;
          onTileClick({ x, y });
        });
      }
    }

    void boot();
    return () => {
      cancelled = true;
      const viewer = viewerRef.current;
      if (viewer) {
        viewer.destroy();
        viewerRef.current = null;
      }
    };
    // re-create the viewer when the slide source changes; opacity / heatmap
    // updates use the effect below to avoid teardown cost on every change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slideDziUrl, id]);

  // Live-update heatmap opacity / source without rebuilding the viewer.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const count = viewer.world.getItemCount();
    if (count > 1) {
      const overlay = viewer.world.getItemAt(1);
      overlay.setOpacity(heatmapOpacity);
    }
  }, [heatmapOpacity, heatmapDziUrl]);

  return (
    <div
      ref={hostRef}
      id={id}
      className={className ?? "slide-viewer"}
      style={{ width: "100%", height: "560px", background: "#0b0d10" }}
    />
  );
}
