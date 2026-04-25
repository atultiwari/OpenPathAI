// Phase 21.6 chunk A — Quickstart wizard render / template pick / persistence.

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QuickstartScreen } from "../screens/quickstart/quickstart-screen";
import { AuthProvider } from "../api/auth-context";
import {
  WIZARD_TEMPLATES,
  TEMPLATE_TILE_CLASSIFIER,
  TEMPLATE_YOLO_CLASSIFIER,
} from "../screens/quickstart/templates";

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

function mockEverythingNotConfigured() {
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/v1/credentials/huggingface")) {
      return mockJson({ present: false, source: "none", token_preview: null });
    }
    if (url.includes("/v1/datasets/") && url.endsWith("/status")) {
      return mockJson({
        dataset: "kather_crc_5k",
        present: false,
        target_dir: "/tmp/.openpathai/datasets/kather_crc_5k",
        files: 0,
        bytes: 0,
      });
    }
    return mockJson({});
  }) as unknown as typeof fetch;
}

describe("WIZARD_TEMPLATES", () => {
  it("ships at least the two documented templates with stable shape", () => {
    expect(WIZARD_TEMPLATES.length).toBeGreaterThanOrEqual(2);
    const ids = WIZARD_TEMPLATES.map((t) => t.id);
    expect(ids).toContain(TEMPLATE_TILE_CLASSIFIER.id);
    expect(ids).toContain(TEMPLATE_YOLO_CLASSIFIER.id);
    for (const t of WIZARD_TEMPLATES) {
      expect(t.steps.length).toBeGreaterThan(0);
      expect(t.datasetCard.length).toBeGreaterThan(0);
      expect(t.modelCard.length).toBeGreaterThan(0);
      // Every step that writes should call out a storage path so the
      // user always knows where artifacts land.
      for (const step of t.steps) {
        if (step.id === "download_dataset" || step.id === "train") {
          expect(step.storagePathHint, `${t.id}.${step.id}`).toBeTruthy();
        }
      }
    }
  });

  it("YOLO template includes the strict-vs-fallback choice step", () => {
    const stepIds = TEMPLATE_YOLO_CLASSIFIER.steps.map((s) => s.id);
    expect(stepIds).toContain("yolo_strict_choice");
  });
});

describe("<QuickstartScreen>", () => {
  it("renders the template picker when no session exists", async () => {
    mockEverythingNotConfigured();

    render(
      <AuthProvider>
        <QuickstartScreen />
      </AuthProvider>
    );

    expect(
      await screen.findByText(/Quickstart wizard/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Tile classifier — DINOv2 \+ Kather-CRC-5K/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/YOLO classifier — YOLOv26-cls \+ Kather-CRC-5K/i)
    ).toBeInTheDocument();
  });

  it("clicking a template card switches to wizard view + persists state", async () => {
    mockEverythingNotConfigured();

    render(
      <AuthProvider>
        <QuickstartScreen />
      </AuthProvider>
    );

    const card = await screen.findByText(
      /Tile classifier — DINOv2 \+ Kather-CRC-5K/i
    );
    fireEvent.click(card);

    // Wizard header appears, picker buttons are gone.
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /pick a different template/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Plumb your Hugging Face token/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Download dataset · kather_crc_5k/i)
    ).toBeInTheDocument();

    // Storage path callout actually surfaces a concrete path.
    expect(
      screen.getByText(/\$OPENPATHAI_HOME\/datasets\/kather_crc_5k\//i)
    ).toBeInTheDocument();

    // Session persisted to localStorage.
    const stored = localStorage.getItem("openpathai.quickstart.session");
    expect(stored).toBeTruthy();
    expect(JSON.parse(stored!).templateId).toBe(
      "tile-classifier-dinov2-kather"
    );
  });

  it("resumes a stored session on a fresh mount", async () => {
    localStorage.setItem(
      "openpathai.quickstart.session",
      JSON.stringify({
        templateId: TEMPLATE_YOLO_CLASSIFIER.id,
        stepResults: {},
        state: {},
      })
    );
    mockEverythingNotConfigured();

    render(
      <AuthProvider>
        <QuickstartScreen />
      </AuthProvider>
    );

    expect(
      await screen.findByRole("button", { name: /pick a different template/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/YOLO classifier — YOLOv26-cls \+ Kather-CRC-5K/i)
    ).toBeInTheDocument();
  });

  it("download step calls the API and surfaces target_dir", async () => {
    let downloadCalls = 0;
    globalThis.fetch = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (
          url.endsWith("/v1/datasets/kather_crc_5k/download") &&
          init?.method === "POST"
        ) {
          downloadCalls += 1;
          return mockJson({
            dataset: "kather_crc_5k",
            status: "downloaded",
            method: "huggingface",
            target_dir: "/tmp/.openpathai/datasets/kather_crc_5k",
            files_written: 5000,
            bytes_written: 52428800,
            message: "ok",
            extra_required: null,
          });
        }
        if (url.includes("/v1/datasets/") && url.endsWith("/status")) {
          return mockJson({
            dataset: "kather_crc_5k",
            present: false,
            target_dir: "/tmp/.openpathai/datasets/kather_crc_5k",
            files: 0,
            bytes: 0,
          });
        }
        if (url.endsWith("/v1/credentials/huggingface")) {
          return mockJson({
            present: false,
            source: "none",
            token_preview: null,
          });
        }
        return mockJson({});
      }
    ) as unknown as typeof fetch;

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

    // Find the Download step's Run button (first "Run" in document).
    const runBtn = await screen.findAllByRole("button", { name: /^run$/i });
    expect(runBtn.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(runBtn[0]);

    await waitFor(() => {
      expect(downloadCalls).toBe(1);
      expect(
        screen.getByText(
          /Downloaded 5000 file\(s\) to \/tmp\/\.openpathai\/datasets\/kather_crc_5k/i
        )
      ).toBeInTheDocument();
    });
  });
});
