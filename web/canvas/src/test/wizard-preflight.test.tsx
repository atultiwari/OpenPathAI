// Phase 22.0 chunks B/D/E — preflight + fix-it + analyse step.

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

it("tile classifier template ships an analyse_folder step before download", () => {
  const stepIds = TEMPLATE_TILE_CLASSIFIER.steps.map((s) => s.id);
  const analyseIdx = stepIds.indexOf("analyse_folder");
  const downloadIdx = stepIds.indexOf("download_dataset");
  expect(analyseIdx).toBeGreaterThanOrEqual(0);
  expect(downloadIdx).toBeGreaterThan(analyseIdx);
});

it("train step has a preflight contract", () => {
  const train = TEMPLATE_TILE_CLASSIFIER.steps.find((s) => s.id === "train");
  expect(train?.preflight).toBeDefined();
  expect(typeof train?.preflight).toBe("function");
});

describe("analyse step + fix-it", () => {
  it("Run on the analyse step posts the user's path to /v1/datasets/inspect and surfaces the inner ImageFolder", async () => {
    let inspectCalls = 0;
    let receivedPath: string | null = null;
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/v1/datasets/inspect") && init?.method === "POST") {
        inspectCalls += 1;
        const body = JSON.parse(init.body as string) as { path: string };
        receivedPath = body.path;
        return mockJson({
          path: body.path,
          kind: "empty",
          image_count: 0,
          bytes_total: 0,
          extensions: [],
          classes: [],
          csvs: [],
          hidden_entries: [".DS_Store"],
          tile_sample: null,
          notes: [],
          children: [
            {
              path: "/Users/me/data/Kather/Kather_texture_2016_image_tiles_5000",
              kind: "class_bucket",
              image_count: 5000,
              bytes_total: 0,
              extensions: [".tif"],
              classes: [
                { name: "01_TUMOR", image_count: 625 },
                { name: "02_STROMA", image_count: 625 },
              ],
              csvs: [],
              hidden_entries: [],
              tile_sample: {
                median_width: 150,
                median_height: 150,
                mode: "RGB",
                format: "TIFF",
                sampled: 5,
              },
              children: [],
              notes: [],
            },
          ],
        });
      }
      if (url.endsWith("/v1/credentials/huggingface")) {
        return mockJson({
          present: false,
          source: "none",
          token_preview: null,
        });
      }
      if (url.includes("/v1/datasets/") && url.endsWith("/status")) {
        return mockJson({
          dataset: "kather_crc_5k",
          present: false,
          target_dir: "/tmp/x",
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
        state: { local_source_path: "/Users/me/data/Kather" },
      })
    );

    render(
      <AuthProvider>
        <QuickstartScreen />
      </AuthProvider>
    );

    const analyseTitle = await screen.findByText(/Analyse your dataset folder/i);
    const analyseStep = analyseTitle.closest("li");
    expect(analyseStep).not.toBeNull();
    const runBtn = analyseStep!.querySelector("button") as HTMLButtonElement;
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(inspectCalls).toBe(1);
      expect(receivedPath).toBe("/Users/me/data/Kather");
      // The Run output surfaces the inner ImageFolder somewhere on the
      // page (banner + step message both include the path).
      const matches = screen.getAllByText(/Kather_texture_2016_image_tiles_5000/i);
      expect(matches.length).toBeGreaterThan(0);
    });
  });

  it("preflight on train refuses when no analysis is present and synthetic mode is OFF", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith("http") && url.endsWith("/v1/credentials/huggingface")) {
        return mockJson({
          present: true,
          source: "settings",
          token_preview: "…abcd",
        });
      }
      if (url.includes("/v1/models")) {
        return mockJson({
          items: [
            {
              id: "dinov2_vits14",
              kind: "foundation",
              display_name: "DINOv2",
              license: "Apache-2.0",
              gated: false,
              tier_compatibility: ["T1"],
              hf_repo: "timm/dinov2",
              embedding_dim: 384,
              input_size: [224, 224],
              citation: null,
            },
          ],
          total: 1,
        });
      }
      if (url.includes("/v1/datasets/") && url.endsWith("/status")) {
        return mockJson({
          dataset: "kather_crc_5k",
          present: false,
          target_dir: "/tmp/x",
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
        state: { use_synthetic: false },
      })
    );

    render(
      <AuthProvider>
        <QuickstartScreen />
      </AuthProvider>
    );

    const trainTitle = await screen.findByText(/^Train dinov2_vits14 on kather_crc_5k$/i);
    const trainStep = trainTitle.closest("li");
    expect(trainStep).not.toBeNull();
    const inspectBtn = Array.from(
      trainStep!.querySelectorAll("button")
    ).find((b) => /Inspect/i.test(b.textContent ?? ""));
    expect(inspectBtn).toBeDefined();
    fireEvent.click(inspectBtn!);

    await waitFor(() => {
      // The preflight surfaces the "Dataset not inspected yet" warning.
      expect(
        screen.getByText(/Dataset not inspected yet/i)
      ).toBeInTheDocument();
    });
  });
});
