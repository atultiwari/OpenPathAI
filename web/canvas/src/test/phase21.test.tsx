// Phase 21 frontend smoke — slides client + tier badges + audit modal.

import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { ApiClient } from "../api/client";
import { TierBadge, ModeBadge, BadgeStrip } from "../components/tier-badges";
import { RunAuditModal } from "../components/run-audit-modal";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function mockJson(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
  });
}

describe("Phase 21 slides + heatmaps client", () => {
  it("uploadSlide posts multipart form data", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        expect(String(input)).toBe("http://api.test/v1/slides");
        expect(init?.method).toBe("POST");
        expect(init?.body).toBeInstanceOf(FormData);
        return mockJson({
          slide_id: "deadbeef" + "00".repeat(28),
          filename: "x.tif",
          size_bytes: 12,
          width: 1,
          height: 1,
          mpp: null,
          level_count: 1,
          backend: "pillow",
          dzi_url: "/v1/slides/deadbeef.dzi",
          tile_url_template: "/v1/slides/x_files/{level}/{col}_{row}.png",
        });
      }
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const client = new ApiClient("http://api.test", "tok");
    const slide = await client.uploadSlide(
      new Blob([new Uint8Array([1, 2, 3])], { type: "image/png" })
    );
    expect(slide.backend).toBe("pillow");
    expect(slide.filename).toBe("x.tif");
  });

  it("computeHeatmap returns the wire shape", async () => {
    globalThis.fetch = vi.fn(async () =>
      mockJson(
        {
          heatmap_id: "hm_abc",
          slide_id: "slide_xyz",
          model_name: "synth",
          resolved_model_name: "synth-synthetic",
          classes: ["a", "b"],
          fallback_reason: "demo",
          width: 8,
          height: 8,
          dzi_url: "/v1/heatmaps/hm_abc.dzi",
          tile_url_template: "/v1/heatmaps/hm_abc_files/{level}/{col}_{row}.png",
        },
        { status: 201 }
      )
    ) as unknown as typeof fetch;
    const client = new ApiClient("http://api.test", "tok");
    const hm = await client.computeHeatmap({
      slide_id: "slide_xyz",
      model_name: "synth",
      classes: ["a", "b"],
    });
    expect(hm.heatmap_id).toBe("hm_abc");
    expect(hm.fallback_reason).toBe("demo");
  });

  it("buildUrl helpers produce stable absolute URLs", () => {
    const client = new ApiClient("http://api.test/", "tok");
    expect(client.slideDziUrl("abc")).toBe("http://api.test/v1/slides/abc.dzi");
    expect(client.heatmapDziUrl("hm_x")).toBe(
      "http://api.test/v1/heatmaps/hm_x.dzi"
    );
    expect(client.cohortQcHtmlUrl("cohort/with bad")).toContain(
      "/v1/cohorts/cohort%2Fwith%20bad/qc.html"
    );
    expect(client.cohortQcPdfUrl("c1")).toBe(
      "http://api.test/v1/cohorts/c1/qc.pdf"
    );
  });

  it("submitBrowserCorrections posts the payload", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        expect(String(input)).toBe(
          "http://api.test/v1/active-learning/sessions/sess-1/corrections"
        );
        expect(init?.method).toBe("POST");
        const body = JSON.parse((init?.body as string) ?? "{}");
        expect(body.corrections.length).toBe(1);
        return mockJson({
          id: "sess-1",
          written: 1,
          annotator_id: "browser-test",
          timestamp: "2026-04-25T00:00:00+00:00",
        });
      }
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const client = new ApiClient("http://api.test", "tok");
    const res = await client.submitBrowserCorrections("sess-1", {
      annotator_id: "browser-test",
      corrections: [{ tile_id: "t1", corrected_label: "x" }],
    });
    expect(res.written).toBe(1);
  });
});

describe("Tier + Mode badges", () => {
  it("renders the tier label", () => {
    render(<TierBadge tier="Easy" />);
    expect(screen.getByText("Easy")).toBeInTheDocument();
  });

  it("renders the mode label", () => {
    render(<ModeBadge mode="diagnostic" />);
    expect(screen.getByText("Diagnostic")).toBeInTheDocument();
  });

  it("composes both badges in a strip", () => {
    render(<BadgeStrip tier="Standard" mode="exploratory" />);
    expect(screen.getByText("Standard")).toBeInTheDocument();
    expect(screen.getByText("Exploratory")).toBeInTheDocument();
  });
});

describe("RunAuditModal", () => {
  it("renders the modal shell with the run id", () => {
    globalThis.fetch = vi.fn(async () =>
      // Never resolves during the synchronous render — the shell text
      // is still expected (the loader paints first).
      mockJson({})
    ) as unknown as typeof fetch;
    const client = new ApiClient("http://api.test", "tok");
    render(
      <RunAuditModal api={client} runId="run-7" onClose={() => undefined} />
    );
    expect(screen.getByText(/Run audit/)).toBeInTheDocument();
    expect(screen.getByText(/run-7/)).toBeInTheDocument();
  });
});
