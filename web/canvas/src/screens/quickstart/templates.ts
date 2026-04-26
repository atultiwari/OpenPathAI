// Phase 21.6 chunk A — Quickstart wizard templates.
// Phase 21.6.1 — added per-step controls (download overrides, train
// duration + synthetic toggle, manual confirm choices) so every step
// is actionable without diving into other tabs.

import type { ApiClient } from "../../api/client";

export type StepKind = "manual" | "automatic";

export type StepStatus = "pending" | "running" | "done" | "error" | "skipped";

export type StepResult = {
  status: StepStatus;
  message?: string;
  artifacts?: Record<string, string>;
};

/** Free-form per-step inputs editable by the user before clicking Run. */
export type StepControl =
  | { id: string; kind: "text"; label: string; placeholder?: string; help?: string }
  | { id: string; kind: "select"; label: string; options: readonly string[]; help?: string }
  | { id: string; kind: "checkbox"; label: string; help?: string }
  // Phase 21.8 chunk D — model_select pulls options from /v1/models
  // (filtered to a kind list when present) at render time. The screen
  // shows id + license + size hint; selecting writes to ctx.state.<id>.
  | {
      id: string;
      kind: "model_select";
      label: string;
      kindFilter?: readonly string[];
      defaultValue?: string;
      help?: string;
    };

/** A button that marks a manual step done with a fixed state delta. */
export type ManualChoice = {
  id: string;
  label: string;
  /** Patches to merge into ctx.state when this choice is picked. */
  state?: Record<string, unknown>;
  /** Banner shown after the choice lands. */
  message?: string;
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
  /** Inputs the user can edit before pressing Run. Defaults seeded
   *  from ctx.state[control.id]; updated values write back. */
  controls?: readonly StepControl[];
  /** When defined, the "Run" button calls this. */
  run?: (ctx: WizardContext) => Promise<StepResult>;
  /** Optional probe — used to mark a step done on tab open. */
  probe?: (ctx: WizardContext) => Promise<StepResult | null>;
  /** When true, surfaces a "Skip" button alongside Run. */
  skippable?: boolean;
  /** Manual steps with no `run`: surface one button per choice that
   *  marks the step done and merges `choice.state` into ctx.state. */
  manualChoices?: readonly ManualChoice[];
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
    manualChoices: [
      {
        id: "skip_hf",
        label: "Skip (open template)",
        message: "Skipped — fine for templates that use open weights.",
      },
    ],
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

function downloadDatasetStep(
  card: string,
  sizeHint: string,
  hfMirror?: string
): WizardStep {
  return {
    id: "download_dataset",
    title: `Download dataset · ${card}`,
    blurb: `Pulls the dataset onto disk. ${sizeHint}`,
    kind: "automatic",
    userActions: [
      "Click Run to use the card's declared source (Zenodo / Kaggle / HuggingFace / HTTP).",
      "If that source is down or unsupported, expand Advanced and provide an override URL, a Hugging Face mirror, or a local folder you've already populated.",
    ],
    wizardActions: [
      `POST /v1/datasets/${card}/download — runs the dispatcher matching the card's download.method (or your override).`,
      "Caches the result under the OpenPathAI datasets root and content-hashes the directory tree.",
    ],
    storagePathHint: `$OPENPATHAI_HOME/datasets/${card}/`,
    controls: [
      {
        id: "override_url",
        kind: "text",
        label: "Override URL (HTTP/HTTPS)",
        placeholder: "https://… (leave blank to use the card's source)",
        help: "Single-file HTTP download. Useful when the canonical Zenodo / Kaggle source is unreachable.",
      },
      {
        id: "override_huggingface_repo",
        kind: "text",
        label: "Hugging Face mirror repo",
        placeholder: hfMirror ?? "owner/repo (e.g. 1aurent/PatchCamelyon)",
        help: hfMirror
          ? `Suggested mirror: ${hfMirror}`
          : "Set when the original card uses Kaggle / Zenodo and you have an HF mirror.",
      },
      {
        id: "local_source_path",
        kind: "text",
        label: "Local source folder (already on disk)",
        placeholder: "/abs/path/to/dataset",
        help: "Symlinks an existing folder into the datasets root — no network fetch.",
      },
    ],
    run: async (ctx) => {
      const overrideUrl = (ctx.state.override_url as string | undefined)?.trim();
      const overrideRepo = (ctx.state.override_huggingface_repo as string | undefined)?.trim();
      const localPath = (ctx.state.local_source_path as string | undefined)?.trim();
      try {
        const result = await ctx.client.downloadDataset(card, {
          ...(overrideUrl ? { override_url: overrideUrl } : {}),
          ...(overrideRepo ? { override_huggingface_repo: overrideRepo } : {}),
          ...(localPath ? { local_source_path: localPath } : {}),
        });
        ctx.state.datasetPath = result.target_dir;
        if (result.status === "manual") {
          return {
            status: "skipped",
            message: result.message ?? "Manual download required — see card instructions.",
            artifacts: { target_dir: result.target_dir },
          };
        }
        if (result.status === "missing_backend") {
          const out: StepResult = {
            status: "error",
            message:
              result.message ??
              "Server is missing the required extra (e.g. install with [train]).",
          };
          if (result.extra_required) {
            out.artifacts = { install_extra: result.extra_required };
          }
          return out;
        }
        // Phase 21.7 chunk C — when the route auto-registered a
        // local-method card, store the new id so the train step
        // submits against the user's bytes instead of the original
        // (Zenodo / Kaggle / HF) card.
        if (result.registered_card) {
          ctx.state.datasetCard = result.registered_card;
        }
        const cardLabel = result.registered_card
          ? ` Auto-registered as card '${result.registered_card}'.`
          : "";
        return {
          status: "done",
          message: `Downloaded ${result.files_written} file(s) to ${result.target_dir}.${cardLabel}`,
          artifacts: {
            target_dir: result.target_dir,
            ...(result.registered_card
              ? { registered_card: result.registered_card }
              : {}),
          },
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
      "Pick a duration preset.",
      "Toggle Synthetic off to actually fit on the downloaded dataset.",
    ],
    wizardActions: [
      "POST /v1/train — submits a training run with the chosen dataset + model + duration + synthetic flag.",
      "Streams epoch metrics; best checkpoint is kept under the path below.",
    ],
    storagePathHint: "$OPENPATHAI_HOME/checkpoints/<run_id>/",
    controls: [
      // Phase 21.8 chunk D — model picker. Default reflects the
      // template's recommended backbone; the user can swap to any
      // registered model. Foundation backbones run via the new
      // linear-probe path, classifier zoo cards via Lightning.
      {
        id: "model_id",
        kind: "model_select",
        label: "Backbone",
        kindFilter: ["foundation", "classifier"],
        defaultValue: model,
        help: "Pick a downloaded backbone (✓) for fastest start. Use the Models tab to download more.",
      },
      {
        id: "duration_preset",
        kind: "select",
        label: "Duration preset",
        options: ["Quick", "Standard", "Thorough"],
        help: "Quick = ~5 min on M1; Standard = ~20 min; Thorough = ~1 h.",
      },
      {
        id: "use_synthetic",
        kind: "checkbox",
        label: "Synthetic mode (no dataset bytes required)",
        help: "Default ON. Flip OFF after the download step is green.",
      },
    ],
    run: async (ctx) => {
      const duration =
        (ctx.state.duration_preset as "Quick" | "Standard" | "Thorough" | undefined) ??
        "Quick";
      const synthetic = ctx.state.use_synthetic !== false;
      const strict = ctx.state.strict_model === true;
      // Phase 21.7 chunk C — when the download step auto-registered a
      // local-source card, prefer that id over the template default
      // so real training reads from the user's bytes.
      const datasetId =
        (ctx.state.datasetCard as string | undefined)?.trim() || card;
      // Phase 21.8 chunk D — pick the user-selected backbone if any.
      const modelId =
        (ctx.state.model_id as string | undefined)?.trim() || model;

      let submitted;
      try {
        submitted = await ctx.client.submitTrain({
          dataset: datasetId,
          model: modelId,
          synthetic,
          duration_preset: duration,
        });
      } catch (err: unknown) {
        return {
          status: "error",
          message: err instanceof Error ? err.message : "Train submit failed.",
        };
      }

      ctx.state.runId = submitted.run_id;
      const tag = `${duration}${synthetic ? " · synthetic" : ""}${
        strict ? " · strict" : ""
      }`;

      // Phase 21.7 chunk A — poll until the run actually finishes, so
      // the wizard never reports DONE on a queued / errored run again.
      const POLL_MS = 1500;
      const MAX_WAIT_MS = 10 * 60 * 1000;
      const started = Date.now();
      while (Date.now() - started < MAX_WAIT_MS) {
        let metrics;
        try {
          metrics = await ctx.client.getTrainMetrics(submitted.run_id);
        } catch (err: unknown) {
          return {
            status: "error",
            message:
              err instanceof Error ? err.message : "Failed to poll run metrics.",
          };
        }
        if (metrics.status === "success") {
          const result = (metrics.result ?? {}) as Record<string, unknown>;
          const tilesUsed = result.tiles_used as number | undefined;
          const datasetPath = result.dataset_path as string | undefined;
          const mode = metrics.mode ?? "synthetic";
          const checkpointPath = result.checkpoint_path as string | undefined;
          const bestAcc =
            metrics.best?.val_accuracy != null
              ? ` · val_acc=${(metrics.best.val_accuracy * 100).toFixed(1)}%`
              : "";
          return {
            status: "done",
            message: `Run ${submitted.run_id.slice(0, 12)} ✅ ${mode} (${tag})${bestAcc}.`,
            artifacts: {
              run_id: submitted.run_id,
              ...(datasetPath ? { dataset: datasetPath } : {}),
              ...(tilesUsed != null ? { tiles_used: String(tilesUsed) } : {}),
              ...(checkpointPath ? { checkpoint: checkpointPath } : {}),
              ...(metrics.epochs && metrics.epochs.length
                ? { epochs: String(metrics.epochs.length) }
                : {}),
            },
          };
        }
        if (metrics.status === "error" || metrics.status === "cancelled") {
          const installHint = metrics.install_cmd
            ? `  Install: ${metrics.install_cmd}`
            : "";
          return {
            status: "error",
            message: `Run ${submitted.run_id.slice(0, 12)} failed: ${
              metrics.error ?? "unknown error"
            }${installHint}`,
            artifacts: {
              run_id: submitted.run_id,
              ...(metrics.install_cmd
                ? { install_cmd: metrics.install_cmd }
                : {}),
            },
          };
        }
        await new Promise((r) => setTimeout(r, POLL_MS));
      }
      return {
        status: "error",
        message: `Run ${submitted.run_id.slice(0, 12)} did not finish in 10 min — check the Runs tab.`,
        artifacts: { run_id: submitted.run_id },
      };
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
    manualChoices: [
      {
        id: "explain_done",
        label: "I've done this",
        message: "Marked done — your prediction lives in the audit DB.",
      },
    ],
  };
}

function yoloStrictChoiceStep(): WizardStep {
  return {
    id: "yolo_strict_choice",
    title: "Strict YOLOv26 or fall-back to YOLOv8?",
    blurb:
      "Iron Rule #11: never silently swap models. The wizard records both requested + resolved ids on every run.",
    kind: "manual",
    userActions: [
      "Default: allow fallback (recommended on a fresh laptop).",
      "Strict mode: hard-fails if YOLOv26 weights aren't installable.",
    ],
    wizardActions: [
      "Marks ctx.state.strict_model for the Train step's submitTrain call.",
    ],
    storagePathHint: "$OPENPATHAI_HOME/models/ (downloaded weights cache)",
    manualChoices: [
      {
        id: "allow_fallback",
        label: "Allow fallback (default)",
        state: { strict_model: false },
        message:
          "Allowed fallback — Train will accept YOLOv8 if v26 weights aren't installable.",
      },
      {
        id: "strict_v26",
        label: "Strict mode — YOLOv26 only",
        state: { strict_model: true },
        message:
          "Strict mode — Train will hard-fail if YOLOv26 weights can't be loaded.",
      },
    ],
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
    downloadDatasetStep(
      "kather_crc_5k",
      "~50 MB, CC-BY-4.0.",
      "1aurent/Colorectal-Histology-MNIST"
    ),
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
    downloadDatasetStep(
      "kather_crc_5k",
      "~50 MB, CC-BY-4.0.",
      "1aurent/Colorectal-Histology-MNIST"
    ),
    yoloStrictChoiceStep(),
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
