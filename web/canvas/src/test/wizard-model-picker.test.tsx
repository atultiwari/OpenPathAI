// Phase 21.8 chunk D — wizard model_select control populates from
// /v1/models and per-row /status; selecting writes to ctx.state.

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QuickstartScreen } from "../screens/quickstart/quickstart-screen";
import { AuthProvider } from "../api/auth-context";
import { TEMPLATE_TILE_CLASSIFIER } from "../screens/quickstart/templates";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.localStorage?.clear();
  globalThis.sessionStorage?.clear();
  globalThis.sessionStorage.setItem("__openpathai_canvas_token__", "tok");
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function mockJson(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
  });
}

it("trainStep ships a model_select control with foundation+classifier filter", () => {
  const train = TEMPLATE_TILE_CLASSIFIER.steps.find((s) => s.id === "train");
  expect(train?.controls).toBeDefined();
  const picker = train!.controls!.find((c) => c.id === "model_id");
  expect(picker?.kind).toBe("model_select");
  expect((picker as { kindFilter?: string[] }).kindFilter).toEqual([
    "foundation",
    "classifier",
  ]);
});

describe("<ModelSelectControl> via QuickstartScreen", () => {
  it("lists foundation + classifier models in the dropdown", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/v1/models?") && url.includes("kind=foundation")) {
        return mockJson({
          items: [
            {
              id: "dinov2_vits14",
              kind: "foundation",
              display_name: "DINOv2 ViT-S/14",
              license: "Apache-2.0",
              gated: false,
              tier_compatibility: ["T1"],
              hf_repo: "timm/x",
              embedding_dim: 384,
              input_size: [224, 224],
              citation: null,
            },
            {
              id: "uni",
              kind: "foundation",
              display_name: "UNI",
              license: "CC-BY-NC-4.0",
              gated: true,
              tier_compatibility: ["T2"],
              hf_repo: "MahmoodLab/UNI",
              embedding_dim: 1024,
              input_size: [224, 224],
              citation: null,
            },
          ],
          total: 2,
        });
      }
      if (url.includes("/v1/models?") && url.includes("kind=classifier")) {
        return mockJson({
          items: [
            {
              id: "resnet18",
              kind: "classifier",
              display_name: "ResNet-18",
              license: "Apache-2.0",
              gated: false,
              tier_compatibility: ["T1"],
              hf_repo: null,
              embedding_dim: null,
              input_size: [224, 224],
              citation: null,
            },
          ],
          total: 1,
        });
      }
      if (url.includes("/v1/models/") && url.endsWith("/status")) {
        const id = url.match(/models\/([^/]+)\/status/)?.[1];
        return mockJson({
          model_id: id,
          present: id === "dinov2_vits14",
          target_dir: "/tmp/x",
          size_bytes: id === "dinov2_vits14" ? 4242 : 0,
          file_count: id === "dinov2_vits14" ? 1 : 0,
          source: "huggingface",
        });
      }
      if (url.endsWith("/v1/credentials/huggingface")) {
        return mockJson({
          present: true,
          source: "settings",
          token_preview: "…abcd",
        });
      }
      if (url.includes("/v1/datasets/") && url.endsWith("/status")) {
        return mockJson({
          dataset: "kather_crc_5k",
          present: false,
          target_dir: "/tmp/datasets/kather_crc_5k",
          files: 0,
          bytes: 0,
        });
      }
      return mockJson({});
    }) as unknown as typeof fetch;

    localStorage.setItem(
      "openpathai.quickstart.session",
      JSON.stringify({
        templateId: TEMPLATE_TILE_CLASSIFIER.id,
        stepResults: {},
        state: {},
      })
    );

    render(
      <AuthProvider>
        <QuickstartScreen />
      </AuthProvider>
    );

    // Backbone label appears in the train step.
    const label = await screen.findByText(/^Backbone$/i);
    const select = label.parentElement?.querySelector("select");
    expect(select).not.toBeNull();

    await waitFor(() => {
      const opts = Array.from(select!.querySelectorAll("option")).map(
        (o) => o.textContent ?? ""
      );
      expect(opts.some((o) => /dinov2_vits14/.test(o))).toBe(true);
      expect(opts.some((o) => /resnet18/.test(o))).toBe(true);
      expect(opts.some((o) => /uni/.test(o))).toBe(true);
    });

    // The downloaded one shows "✓ on disk".
    await waitFor(() => {
      const text = select!.textContent ?? "";
      expect(text).toMatch(/✓ on disk/);
    });

    // Switching the dropdown writes ctx.state.model_id (via session).
    fireEvent.change(select!, { target: { value: "resnet18" } });
    await waitFor(() => {
      const stored = JSON.parse(
        localStorage.getItem("openpathai.quickstart.session") || "{}"
      );
      expect(stored.state.model_id).toBe("resnet18");
    });
  });
});
