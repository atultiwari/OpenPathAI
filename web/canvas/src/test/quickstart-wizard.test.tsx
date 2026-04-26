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

  it("YOLO strict-choice step exposes manualChoices so the user can advance", () => {
    const step = TEMPLATE_YOLO_CLASSIFIER.steps.find(
      (s) => s.id === "yolo_strict_choice"
    );
    expect(step).toBeDefined();
    expect(step?.kind).toBe("manual");
    expect(step?.manualChoices?.length).toBeGreaterThanOrEqual(2);
    const choiceIds = step!.manualChoices!.map((c) => c.id);
    expect(choiceIds).toContain("allow_fallback");
    expect(choiceIds).toContain("strict_v26");
  });

  it("download_dataset step ships override controls (url / hf repo / local)", () => {
    // Phase 21.9 — only the classification templates carry a
    // download_dataset step; embeddings / detection / segmentation /
    // zero-shot use a different on-ramp. Scope the contract check to
    // the templates that actually have the step.
    for (const t of WIZARD_TEMPLATES) {
      const step = t.steps.find((s) => s.id === "download_dataset");
      if (!step) continue;
      expect(step.controls?.length, t.id).toBeGreaterThanOrEqual(3);
      const controlIds = step.controls!.map((c) => c.id);
      expect(controlIds).toContain("override_url");
      expect(controlIds).toContain("override_huggingface_repo");
      expect(controlIds).toContain("local_source_path");
    }
  });

  it("train step ships duration_preset select + use_synthetic checkbox", () => {
    for (const t of WIZARD_TEMPLATES) {
      const step = t.steps.find((s) => s.id === "train");
      if (!step) continue;
      expect(step.controls?.length, t.id).toBeGreaterThanOrEqual(2);
      const dur = step.controls!.find((c) => c.id === "duration_preset");
      expect(dur?.kind).toBe("select");
      const synth = step.controls!.find((c) => c.id === "use_synthetic");
      expect(synth?.kind).toBe("checkbox");
    }
  });

  it("ships at least one template per task kind (classification + 4 more)", () => {
    const tasks = new Set(WIZARD_TEMPLATES.map((t) => t.task));
    for (const k of [
      "classification",
      "embeddings",
      "detection",
      "segmentation",
      "zero_shot",
    ]) {
      expect(tasks.has(k as never), `missing task: ${k}`).toBe(true);
    }
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

  it("download step posts the user's override fields when set", async () => {
    let downloadCalls = 0;
    let receivedBody: unknown = null;
    globalThis.fetch = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (
          url.endsWith("/v1/datasets/kather_crc_5k/download") &&
          init?.method === "POST"
        ) {
          downloadCalls += 1;
          receivedBody = JSON.parse(init.body as string);
          return mockJson({
            dataset: "kather_crc_5k",
            status: "downloaded",
            method: "local",
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
        // Pre-seed the override so the runStep call carries it.
        state: { local_source_path: "/Users/me/data/kather" },
      })
    );

    render(
      <AuthProvider>
        <QuickstartScreen />
      </AuthProvider>
    );

    // Phase 22.0 chunk E — the analyse step now precedes download; pick
    // the Run button inside the download step's row by walking from
    // the step title.
    const downloadTitle = await screen.findByText(
      /^Download dataset · kather_crc_5k$/i
    );
    const downloadStep = downloadTitle.closest("li");
    expect(downloadStep).not.toBeNull();
    const downloadRun = downloadStep!.querySelector(
      "button"
    ) as HTMLButtonElement;
    // The first button inside the step is the Run button.
    expect(downloadRun.textContent).toMatch(/^Run/i);
    fireEvent.click(downloadRun);

    await waitFor(() => {
      expect(downloadCalls).toBe(1);
      expect(receivedBody).toEqual({
        local_source_path: "/Users/me/data/kather",
      });
    });
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

    // Phase 22.0 chunk E — analyse step now precedes download. Click
    // the Run button inside the download step's row specifically.
    const downloadTitle = await screen.findByText(
      /^Download dataset · kather_crc_5k$/i
    );
    const downloadStep = downloadTitle.closest("li");
    expect(downloadStep).not.toBeNull();
    const downloadRun = downloadStep!.querySelector(
      "button"
    ) as HTMLButtonElement;
    expect(downloadRun.textContent).toMatch(/^Run/i);
    fireEvent.click(downloadRun);

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
