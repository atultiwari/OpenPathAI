// Phase 21.5 — starter pipelines + Pipelines screen empty state.

import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { STARTER_PIPELINES, starterOps } from "../canvas/starters";
import { toPipeline } from "../canvas/types";
import { PipelinesScreen } from "../screens/pipelines/pipelines-screen";
import { AuthProvider } from "../api/auth-context";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.sessionStorage?.clear();
  globalThis.localStorage?.clear();
});

describe("STARTER_PIPELINES", () => {
  it("exposes at least one starter and gives every starter a stable shape", () => {
    expect(STARTER_PIPELINES.length).toBeGreaterThan(0);
    for (const starter of STARTER_PIPELINES) {
      expect(starter.id).toMatch(/^[a-z0-9_]+$/);
      expect(starter.label.length).toBeGreaterThan(0);
      expect(["open", "synthetic", "gated"]).toContain(starter.tier);
      expect(starter.blurb.length).toBeGreaterThan(0);
    }
  });

  it("every starter builds a CanvasState that toPipeline can serialise", () => {
    for (const starter of STARTER_PIPELINES) {
      const canvas = starter.build();
      expect(canvas.nodes.length).toBeGreaterThan(0);
      const pipeline = toPipeline(canvas);
      expect(pipeline.steps.length).toBe(canvas.nodes.length);
      // All step ids unique.
      const ids = pipeline.steps.map((s) => s.id);
      expect(new Set(ids).size).toBe(ids.length);
      // All edges reference real nodes.
      const idSet = new Set(canvas.nodes.map((n) => n.id));
      for (const edge of canvas.edges) {
        expect(idSet.has(edge.source)).toBe(true);
        expect(idSet.has(edge.target)).toBe(true);
      }
    }
  });

  it("starterOps deduplicates operator ids from a starter graph", () => {
    const helloCanvas = STARTER_PIPELINES.find((s) => s.id === "hello_canvas");
    expect(helloCanvas).toBeDefined();
    const ops = starterOps(helloCanvas!);
    // Hello canvas uses demo.constant twice + demo.double + demo.mean.
    expect(ops).toContain("demo.constant");
    expect(ops).toContain("demo.double");
    expect(ops).toContain("demo.mean");
    expect(new Set(ops).size).toBe(ops.length);
  });

  it("hello_canvas only references ops that ship in the live registry", () => {
    // The Phase-19 nodes catalog exposes demo.* + explain.* + training.train
    // (see src/openpathai/{demo,explain,training}/*.py). Hello canvas uses
    // only demo.* so it must run on every install.
    const liveOps = new Set([
      "demo.constant",
      "demo.double",
      "demo.mean",
      "explain.gradcam",
      "explain.attention_rollout",
      "explain.integrated_gradients",
      "training.train",
    ]);
    for (const starter of STARTER_PIPELINES) {
      for (const op of starterOps(starter)) {
        expect(liveOps.has(op)).toBe(true);
      }
    }
  });
});

function mockJson(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
  });
}

describe("PipelinesScreen empty state + header", () => {
  it("renders the empty-state hint when no nodes are placed", async () => {
    // Stub the catalog fetch so the palette settles, then assert empty state.
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/v1/nodes") || url.endsWith("/v1/nodes/")) {
        return mockJson({
          items: [
            {
              id: "demo.constant",
              description: "constant int",
              code_hash: "x",
              input_schema: { type: "object" },
              output_schema: { type: "object" },
            },
          ],
          total: 1,
        });
      }
      return mockJson({ status: "ok", api_version: "1" });
    }) as unknown as typeof fetch;

    // Seed the AuthProvider's session token (key per auth-context.tsx).
    globalThis.sessionStorage.setItem("__openpathai_canvas_token__", "tok");

    render(
      <AuthProvider>
        <PipelinesScreen />
      </AuthProvider>
    );

    expect(await screen.findByText(/this canvas is empty/i)).toBeInTheDocument();
    expect(
      screen.getByText(/pick a starter pipeline from the toolbar/i)
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /load starter/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /^run$/i })).toBeDisabled();

    await waitFor(() => {
      expect(screen.getByText(/constant int/i)).toBeInTheDocument();
    });
  });
});
