// Phase 21.6 chunk A — Quickstart wizard templates.
//
// Each template is a typed multi-step recipe. The wizard renders one
// at a time and runs each step's `action` against the live API.
// Steps may be `manual` (user does it; wizard checks state) or
// `automatic` (wizard runs and reports back).
//
// Storage paths surface in every step that writes to disk so the
// user always knows where artifacts land — closes the "where do
// downloads go?" gap the screenshots flagged.

import type { ApiClient } from "../../api/client";

export type StepKind = "manual" | "automatic";

export type StepStatus = "pending" | "running" | "done" | "error" | "skipped";

export type StepResult = {
  status: StepStatus;
  message?: string;
  artifacts?: Record<string, string>;
};

export type WizardStep = {
  id: string;
  title: string;
  blurb: string;
  kind: StepKind;
  /** What the user has to do, written so a first-time user gets it. */
  userActions?: readonly string[];
  /** What the wizard does on the user's behalf. */
  wizardActions?: readonly string[];
  /** Where this step writes (or reads from) on disk. */
  storagePathHint?: string;
  /** When defined, the "Run" button calls this. */
  run?: (ctx: WizardContext) => Promise<StepResult>;
  /** Optional probe — used to mark a step done on tab open. */
  probe?: (ctx: WizardContext) => Promise<StepResult | null>;
  /** When true, surfaces a "Skip" button alongside Run. */
  skippable?: boolean;
};

export type WizardContext = {
  client: ApiClient;
  template: WizardTemplate;
  /** Mutable per-template state — survives across steps inside a session. */
  state: Record<string, unknown>;
};

export type WizardTemplate = {
  id: string;
  label: string;
  tier: "open" | "synthetic" | "gated";
  blurb: string;
  estimatedMinutes: number;
  // Per-template canonical artifacts the wizard will create.
  datasetCard: string;
  modelCard: string;
  steps: readonly WizardStep[];
};

// ─── Shared step builders ───────────────────────────────────────

function hfTokenStep(): WizardStep {
  return {
    id: "hf_token",
    title: "Plumb your Hugging Face token (optional for this template)",
    blurb:
      "Required only for gated foundation models. Skip if your template uses open weights.",
    kind: "manual",
    skippable: true,
    userActions: [
      "Open Settings → Hugging Face.",
      "Get a read token at https://huggingface.co/settings/tokens, paste it, hit Save then Test.",
    ],
    wizardActions: ["Reads the resolved status from /v1/credentials/huggingface."],
    storagePathHint: "$OPENPATHAI_HOME/secrets.json (mode 0600)",
    probe: async (ctx) => {
      const status = await ctx.client.getHfTokenStatus();
      if (status.present) {
        return {
          status: "done",
          message: `Active source: ${status.source} (${status.token_preview ?? "—"}).`,
        };
      }
      return {
        status: "pending",
        message: "Not configured — fine for open templates, required for gated ones.",
      };
    },
  };
}

function downloadDatasetStep(card: string, sizeHint: string): WizardStep {
  return {
    id: "download_dataset",
    title: `Download dataset · ${card}`,
    blurb: `Pulls the dataset onto disk. ${sizeHint}`,
    kind: "automatic",
    userActions: [
      "If the card is a Kaggle dataset, accept the competition rules in the Kaggle UI first (the wizard shows the URL).",
    ],
    wizardActions: [
      `POST /v1/datasets/${card}/download — runs the dispatcher matching the card's download.method.`,
      "Caches the result under the OpenPathAI datasets root and content-hashes the directory tree.",
    ],
    storagePathHint: `$OPENPATHAI_HOME/datasets/${card}/`,
    run: async (ctx) => {
      try {
        const result = await ctx.client.downloadDataset(card, {});
        ctx.state.datasetPath = result.target_dir;
        if (result.status === "manual") {
          return {
            status: "skipped",
            message: result.message ?? "Manual download required — see card instructions.",
            artifacts: { target_dir: result.target_dir },
          };
        }
        if (result.status === "missing_backend") {
          return {
            status: "error",
            message:
              result.message ??
              "Server is missing the required extra (e.g. install with [train]).",
          };
        }
        return {
          status: "done",
          message: `Downloaded ${result.files_written} file(s) to ${result.target_dir}.`,
          artifacts: { target_dir: result.target_dir },
        };
      } catch (err: unknown) {
        return {
          status: "error",
          message: err instanceof Error ? err.message : "Download failed.",
        };
      }
    },
    probe: async (ctx) => {
      try {
        const status = await ctx.client.getDatasetStatus(card);
        if (status.present) {
          ctx.state.datasetPath = status.target_dir;
          return {
            status: "done",
            message: `${status.files} file(s) at ${status.target_dir}.`,
            artifacts: { target_dir: status.target_dir },
          };
        }
        return null;
      } catch {
        return null;
      }
    },
  };
}

function trainStep(card: string, model: string): WizardStep {
  return {
    id: "train",
    title: `Train ${model} on ${card}`,
    blurb:
      "Synthetic mode runs end-to-end without dataset bytes. Toggle it off once the download step is green.",
    kind: "automatic",
    userActions: [
      "Pick Quick / Standard / Thorough duration if you want longer training.",
    ],
    wizardActions: [
      "POST /v1/train — submits a training run with the chosen dataset + model.",
      "Streams epoch metrics; best checkpoint is kept.",
    ],
    storagePathHint: "$OPENPATHAI_HOME/checkpoints/<run_id>/",
    run: async (ctx) => {
      const synthetic = ctx.state.useSynthetic !== false;
      try {
        const submitted = await ctx.client.submitTrain({
          dataset: card,
          model,
          synthetic,
          duration_preset: "Quick",
        });
        ctx.state.runId = submitted.run_id;
        return {
          status: submitted.status === "error" ? "error" : "done",
          message: `Run ${submitted.run_id.slice(0, 12)} ${submitted.status}${
            synthetic ? " (synthetic)" : ""
          }.`,
          artifacts: { run_id: submitted.run_id },
        };
      } catch (err: unknown) {
        return {
          status: "error",
          message: err instanceof Error ? err.message : "Train submit failed.",
        };
      }
    },
  };
}

function explainStep(): WizardStep {
  return {
    id: "explain",
    title: "Drop a tile and read the explanation",
    blurb: "Top-k prediction + Grad-CAM overlay on a single tile.",
    kind: "manual",
    userActions: [
      "Open the Analyse tab.",
      "Drag-drop a tile (any 96–224 px PNG).",
      "Pick gradcam as the explainer (safe default).",
      "Read the predicted class, confidence, and overlay.",
    ],
    wizardActions: [
      "Result lands in the audit DB automatically — flip to Audit to confirm.",
    ],
    storagePathHint: "$OPENPATHAI_HOME/audit.sqlite",
  };
}

// ─── Templates ──────────────────────────────────────────────────

export const TEMPLATE_TILE_CLASSIFIER: WizardTemplate = {
  id: "tile-classifier-dinov2-kather",
  label: "Tile classifier — DINOv2 + Kather-CRC-5K",
  tier: "open",
  blurb:
    "Open-access end-to-end recipe. Kather-CRC-5K is the smallest CC-BY card; DINOv2-small is open and downloads without a Hugging Face token.",
  estimatedMinutes: 15,
  datasetCard: "kather_crc_5k",
  modelCard: "dinov2-small",
  steps: [
    hfTokenStep(),
    downloadDatasetStep("kather_crc_5k", "~50 MB, CC-BY-4.0."),
    trainStep("kather_crc_5k", "dinov2-small"),
    explainStep(),
  ],
};

export const TEMPLATE_YOLO_CLASSIFIER: WizardTemplate = {
  id: "yolo-classifier-yolov26-kather",
  label: "YOLO classifier — YOLOv26-cls + Kather-CRC-5K",
  tier: "open",
  blurb:
    "Same dataset as the DINOv2 template, but uses the YOLOv26 backbone (Ultralytics, AGPL-3.0). If YOLOv26 weights aren't installable, the resolver gracefully falls back to YOLOv8 and records both ids in the audit manifest (Iron Rule #11). The model card lives at models/zoo/yolov26_cls.yaml.",
  estimatedMinutes: 15,
  datasetCard: "kather_crc_5k",
  modelCard: "yolov26_cls",
  steps: [
    hfTokenStep(),
    downloadDatasetStep("kather_crc_5k", "~50 MB, CC-BY-4.0."),
    {
      id: "yolo_strict_choice",
      title: "Strict YOLOv26 or fall-back to YOLOv8?",
      blurb:
        "Iron Rule #11: never silently swap models. The wizard records both requested + resolved ids on every run.",
      kind: "manual",
      userActions: [
        "Default: allow fallback (recommended on a fresh laptop).",
        "Strict mode: hard-fails if YOLOv26 weights aren't installable. Toggle in Train.",
      ],
      wizardActions: ["Marks ctx.state.strictModel for the train step."],
      storagePathHint: "$OPENPATHAI_HOME/models/ (downloaded weights cache)",
    },
    trainStep("kather_crc_5k", "yolov26_cls"),
    explainStep(),
  ],
};

export const WIZARD_TEMPLATES: readonly WizardTemplate[] = [
  TEMPLATE_TILE_CLASSIFIER,
  TEMPLATE_YOLO_CLASSIFIER,
];

export function findTemplate(id: string): WizardTemplate | undefined {
  return WIZARD_TEMPLATES.find((t) => t.id === id);
}
