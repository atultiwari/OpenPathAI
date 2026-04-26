// Phase 22.1 chunk C — wizard surfaces a model-aware plan inline.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QuickstartScreen } from "../screens/quickstart/quickstart-screen";
import { AuthProvider } from "../api/auth-context";
import { TEMPLATE_YOLO_CLASSIFIER } from "../screens/quickstart/templates";

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

describe("Phase 22.1 — model-aware plan in the analyse step preflight", () => {
  it("Inspect on the analyse step renders the bash, supports Copy, and lets Apply via library (commit) hit /v1/datasets/restructure", async () => {
    let planCalls = 0;
    let restructureCalls = 0;
    let lastRestructureBody: { path: string; model_id: string; dry_run: boolean } | null =
      null;

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/v1/datasets/analyse") && init?.method === "POST") {
        const body = JSON.parse(init.body as string) as { path: string };
        return mockJson({
          path: body.path,
          exists: true,
          is_directory: true,
          layout: "image_folder",
          image_count: 6,
          class_count: 2,
          classes: [
            { name: "a", count: 3 },
            { name: "b", count: 3 },
          ],
          extensions: [".png"],
          hidden_entries: [],
          non_image_files: [],
          suggested_root: null,
          warnings: [],
          truncated: false,
          bytes_total: 0,
        });
      }
      if (url.endsWith("/v1/datasets/plan") && init?.method === "POST") {
        planCalls += 1;
        return mockJson({
          model_id: "yolo-classifier-yolov26",
          requirement: "yolo_cls_split",
          source_path: "/data/Kather",
          target_path: "/data/Kather__yolo_cls_split",
          ok: true,
          actions: [
            { kind: "make_dir", path: "/data/Kather__yolo_cls_split" },
            {
              kind: "make_split",
              dest_root: "/data/Kather__yolo_cls_split",
              class_dirs: ["/data/Kather/a", "/data/Kather/b"],
              train_ratio: 0.8,
              val_ratio: 0.1,
              test_ratio: 0.1,
              seed: 0,
            },
          ],
          bash:
            "#!/usr/bin/env bash\nset -euo pipefail\nmkdir -p /data/Kather__yolo_cls_split\npython -m openpathai.cli.dataset split --classes a b --dest /data/Kather__yolo_cls_split\n",
          python_invocation: "",
          notes: ["Splits are deterministic at seed=0."],
          provenance: "rule_based",
        });
      }
      if (url.endsWith("/v1/datasets/restructure") && init?.method === "POST") {
        restructureCalls += 1;
        lastRestructureBody = JSON.parse(init.body as string);
        return mockJson({
          target_path: "/data/Kather__yolo_cls_split",
          dry_run: lastRestructureBody!.dry_run,
          executed_actions: ["make_dir /data/Kather__yolo_cls_split", "make_split into /data/Kather__yolo_cls_split"],
          errors: [],
          new_root: "/data/Kather__yolo_cls_split",
        });
      }
      if (url.endsWith("/v1/credentials/huggingface")) {
        return mockJson({ present: false, source: "none", token_preview: null });
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
        templateId: TEMPLATE_YOLO_CLASSIFIER.id,
        stepResults: {},
        state: { local_source_path: "/data/Kather" },
      })
    );

    render(
      <AuthProvider>
        <QuickstartScreen />
      </AuthProvider>
    );

    // Find the analyse step heading and walk to its Run button.
    const analyseTitle = await screen.findByText(/Analyse your dataset folder/i);
    const stepLi = analyseTitle.closest("li");
    expect(stepLi).not.toBeNull();
    const runBtn = Array.from(stepLi!.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Run"
    );
    expect(runBtn).toBeDefined();
    fireEvent.click(runBtn!);

    // Wait for the analyse to complete + plan call to land.
    await waitFor(() => expect(planCalls).toBeGreaterThan(0));

    // Open Inspect.
    const inspectBtn = Array.from(stepLi!.querySelectorAll("button")).find((b) =>
      b.textContent?.toLowerCase().includes("inspect")
    );
    expect(inspectBtn).toBeDefined();
    fireEvent.click(inspectBtn!);

    // Plan section renders with the bash details.
    await screen.findByText(/Proposed restructure/i);
    expect(screen.getByText(/requires: yolo_cls_split/)).toBeInTheDocument();
    // The plan badge code element shows the model id.
    expect(
      screen.getAllByText((_text, node) => node?.textContent === "yolo-classifier-yolov26").length
    ).toBeGreaterThan(0);

    // Apply via library (commit) hits /restructure with dry_run=false.
    const commitBtn = screen.getByRole("button", {
      name: /Apply via library \(commit\)/,
    });
    fireEvent.click(commitBtn);

    await waitFor(() => expect(restructureCalls).toBeGreaterThan(0));
    expect(lastRestructureBody).toEqual({
      path: "/data/Kather",
      model_id: "yolo-classifier-yolov26",
      dry_run: false,
    });
    await screen.findByText(/Applied →/);
  });

  it("Plan section renders the Incompatible reason when the planner returns ok=false", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/v1/datasets/analyse") && init?.method === "POST") {
        return mockJson({
          path: "/data/Kather",
          exists: true,
          is_directory: true,
          layout: "image_folder",
          image_count: 6,
          class_count: 2,
          classes: [
            { name: "a", count: 3 },
            { name: "b", count: 3 },
          ],
          extensions: [".png"],
          hidden_entries: [],
          non_image_files: [],
          suggested_root: null,
          warnings: [],
          truncated: false,
          bytes_total: 0,
        });
      }
      if (url.endsWith("/v1/datasets/plan") && init?.method === "POST") {
        return mockJson({
          model_id: "yolo-detector-yolov26",
          requirement: "yolo_det",
          source_path: "/data/Kather",
          target_path: "/data/Kather",
          ok: false,
          actions: [
            {
              kind: "incompatible",
              reason: "No bbox labels detected.",
              hint: "Bootstrap labels via MedSAM2 zero-shot.",
            },
          ],
          bash: "# Incompatible: No bbox labels detected.\n",
          python_invocation: "",
          notes: [],
          provenance: "rule_based",
        });
      }
      if (url.endsWith("/v1/credentials/huggingface")) {
        return mockJson({ present: false, source: "none", token_preview: null });
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
        templateId: TEMPLATE_YOLO_CLASSIFIER.id,
        stepResults: {},
        state: { local_source_path: "/data/Kather", model_id: "yolo-detector-yolov26" },
      })
    );

    render(
      <AuthProvider>
        <QuickstartScreen />
      </AuthProvider>
    );

    const analyseTitle = await screen.findByText(/Analyse your dataset folder/i);
    const stepLi = analyseTitle.closest("li")!;
    const runBtn = Array.from(stepLi.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Run"
    )!;
    fireEvent.click(runBtn);

    // Blocked preflight auto-opens the inspect panel — wait for the
    // plan section to render directly.
    await screen.findByText(
      (text) => text.includes("Cannot satisfy this model")
    );
    expect(screen.getAllByText(/No bbox labels detected/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/MedSAM2/).length).toBeGreaterThan(0);
    // Apply buttons should be hidden when the plan is not ok.
    expect(screen.queryByRole("button", { name: /Apply via library/ })).toBeNull();
    // Ask MedGemma button should be visible (rule-based + incompatible).
    expect(screen.getByRole("button", { name: /Ask MedGemma/ })).toBeInTheDocument();
  });

  it("Ask MedGemma posts to /v1/datasets/plan-llm and gates Apply on review", async () => {
    let llmCalls = 0;
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/v1/datasets/analyse") && init?.method === "POST") {
        return mockJson({
          path: "/data/Kather",
          exists: true,
          is_directory: true,
          layout: "image_folder",
          image_count: 6,
          class_count: 2,
          classes: [
            { name: "a", count: 3 },
            { name: "b", count: 3 },
          ],
          extensions: [".png"],
          hidden_entries: [],
          non_image_files: [],
          suggested_root: null,
          warnings: [],
          truncated: false,
          bytes_total: 0,
        });
      }
      if (url.endsWith("/v1/datasets/plan") && init?.method === "POST") {
        return mockJson({
          model_id: "yolo-detector-yolov26",
          requirement: "yolo_det",
          source_path: "/data/Kather",
          target_path: "/data/Kather",
          ok: false,
          actions: [
            {
              kind: "incompatible",
              reason: "No bbox labels detected.",
              hint: "Bootstrap labels via MedSAM2 zero-shot.",
            },
          ],
          bash: "# Incompatible.\n",
          python_invocation: "",
          notes: [],
          provenance: "rule_based",
        });
      }
      if (url.endsWith("/v1/datasets/plan-llm") && init?.method === "POST") {
        llmCalls += 1;
        return mockJson({
          model_id: "yolo-detector-yolov26",
          requirement: "yolo_det",
          source_path: "/data/Kather",
          target_path: "/data/Kather/auto_bootstrap_labels",
          ok: true,
          actions: [
            { kind: "make_dir", path: "/data/Kather/auto_bootstrap_labels" },
          ],
          bash: "#!/usr/bin/env bash\nmkdir -p /data/Kather/auto_bootstrap_labels\n",
          python_invocation: "",
          notes: ["Bootstrap labels with MedSAM2 prior to detector training."],
          provenance: "medgemma",
        });
      }
      if (url.endsWith("/v1/credentials/huggingface")) {
        return mockJson({ present: false, source: "none", token_preview: null });
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
        templateId: TEMPLATE_YOLO_CLASSIFIER.id,
        stepResults: {},
        state: { local_source_path: "/data/Kather", model_id: "yolo-detector-yolov26" },
      })
    );

    render(
      <AuthProvider>
        <QuickstartScreen />
      </AuthProvider>
    );

    const analyseTitle = await screen.findByText(/Analyse your dataset folder/i);
    const stepLi = analyseTitle.closest("li")!;
    const runBtn = Array.from(stepLi.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "Run"
    )!;
    fireEvent.click(runBtn);

    await screen.findByRole("button", { name: /Ask MedGemma/ });
    fireEvent.click(screen.getByRole("button", { name: /Ask MedGemma/ }));
    await waitFor(() => expect(llmCalls).toBeGreaterThan(0));

    // After MedGemma returns ok=true, Apply buttons appear but are
    // disabled until the user ticks the review checkbox.
    const applyBtn = await screen.findByRole("button", {
      name: /Apply via library \(commit\)/,
    });
    expect(applyBtn).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/I have reviewed this MedGemma-proposed plan/));
    expect(applyBtn).not.toBeDisabled();
  });
});
