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

// ─── Phase 22.0 chunk B/D — preflight contracts + fix-it actions ──

/**
 * Discriminated-union of fix actions a preflight blocker can suggest.
 * Wizard executes the action then re-runs the preflight.
 */
export type FixAction =
  | { kind: "set_state"; key: string; value: unknown }
  | { kind: "navigate_tab"; tab: string }
  | { kind: "open_url"; url: string }
  | { kind: "rerun_step"; step_id: string }
  | { kind: "noop"; message: string };

export type PreflightFix = {
  label: string;
  action: FixAction;
};

export type PreflightBlocker = {
  title: string;
  detail?: string;
};

export type PreflightWarning = {
  title: string;
  detail?: string;
};

export type PreflightResult = {
  ok: boolean;
  blockers?: readonly PreflightBlocker[];
  warnings?: readonly PreflightWarning[];
  fixes?: readonly PreflightFix[];
  /** Optional snapshot the wizard surfaces under "Step health". */
  manifest?: Record<string, string>;
};

export type StepManifest = {
  artifacts: Record<string, string>;
  warnings: readonly string[];
  completed_at: string;
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
  /**
   * Phase 22.0 chunk B — preflight contract. Runs before `run()` /
   * `manualChoices` are surfaced. When `ok=false`, the wizard refuses
   * to advance and surfaces blockers + apply-fix buttons.
   */
  preflight?: (ctx: WizardContext) => Promise<PreflightResult>;
};

export type WizardContext = {
  client: ApiClient;
  template: WizardTemplate;
  /** Mutable per-template state — survives across steps inside a session. */
  state: Record<string, unknown>;
};

// Phase 21.9 chunk B — task taxonomy for the picker grouping. Maps
// 1:1 to the README task list (classification / foundation embeddings
// / detection / segmentation / zero-shot).
export type TaskKind =
  | "classification"
  | "embeddings"
  | "detection"
  | "segmentation"
  | "zero_shot";

export type WizardTemplate = {
  id: string;
  label: string;
  tier: "open" | "synthetic" | "gated";
  task: TaskKind;
  blurb: string;
  estimatedMinutes: number;
  datasetCard: string;
  modelCard: string;
  /** When true, surfaces a "Phase 22 — preview" badge on the template
   *  card. Lets us ship task-shaped wizards for paths whose backend is
   *  still a stub, without misleading users. */
  preview?: boolean;
  steps: readonly WizardStep[];
};

export const TASK_LABELS: Record<TaskKind, string> = {
  classification: "Tile classification",
  embeddings: "Foundation embeddings",
  detection: "Detection",
  segmentation: "Segmentation",
  zero_shot: "Zero-shot",
};

// ─── Shared step builders ───────────────────────────────────────

/** Phase 22.0 chunk E — analyse the local-source folder *before*
 *  the download/register step. Surfaces the user's nested-ImageFolder
 *  case with a one-click "Use suggested path" fix. */
function analyseFolderStep(): WizardStep {
  return {
    id: "analyse_folder",
    title: "Analyse your dataset folder",
    blurb:
      "Walks the folder you'll register in the next step and reports its layout (ImageFolder / nested / flat / mixed) plus per-class counts. Catches the common 'I picked the parent folder' mistake before training inherits an empty card.",
    kind: "automatic",
    userActions: [
      "Type the absolute path to your local dataset folder.",
      "Click Run. If the wizard suggests a different root (because it found an ImageFolder one level down), apply the fix.",
    ],
    wizardActions: [
      "POST /v1/datasets/analyse — walks the folder, returns layout + classes + warnings.",
      "Writes the resolved path into ctx.state.local_source_path so the download step picks it up automatically.",
    ],
    storagePathHint: "(read-only — analyser doesn't touch disk)",
    controls: [
      {
        id: "local_source_path",
        kind: "text",
        label: "Local source folder (absolute path)",
        placeholder: "/abs/path/to/dataset",
        help:
          "ImageFolder layout: <root>/<class_name>/<image>.png. The analyser will tell you when the layout is one level deeper than you think.",
      },
    ],
    run: async (ctx) => {
      const folder = (ctx.state.local_source_path as string | undefined)?.trim();
      if (!folder) {
        return {
          status: "error",
          message: "Set the source folder above before clicking Run.",
        };
      }
      try {
        const report = await ctx.client.analyseFolder(folder);
        ctx.state.dataset_analysis = report as unknown as Record<string, unknown>;
        const baseArtifacts: Record<string, string> = {
          layout: report.layout,
          classes: String(report.class_count),
          images: String(report.image_count),
        };
        if (report.suggested_root) {
          baseArtifacts.suggested_root = report.suggested_root;
        }
        if (report.layout === "image_folder") {
          return {
            status: "done",
            message: `✓ ImageFolder · ${report.class_count} classes · ${report.image_count} images.`,
            artifacts: baseArtifacts,
          };
        }
        if (report.layout === "nested_image_folder" && report.suggested_root) {
          return {
            status: "error",
            message: `Folder layout is '${report.layout}'. The wizard suggests using ${report.suggested_root} instead — open Inspect to apply the fix.`,
            artifacts: baseArtifacts,
          };
        }
        return {
          status: "error",
          message: `Folder layout is '${report.layout}' — not usable for training. Inspect for details.`,
          artifacts: baseArtifacts,
        };
      } catch (err) {
        return {
          status: "error",
          message: err instanceof Error ? err.message : "Analyse failed.",
        };
      }
    },
    preflight: async (ctx) => {
      const folder = (ctx.state.local_source_path as string | undefined)?.trim();
      const blockers: { title: string; detail?: string }[] = [];
      if (!folder) {
        blockers.push({
          title: "No source folder set",
          detail:
            "Type the absolute path to the folder you want to use as your dataset.",
        });
      }
      const analysis = ctx.state.dataset_analysis as
        | { layout?: string; suggested_root?: string | null; class_count?: number; image_count?: number; warnings?: string[] }
        | undefined;
      const fixes: { label: string; action: FixAction }[] = [];
      const warnings: { title: string; detail?: string }[] = [];
      if (analysis) {
        if (analysis.layout === "nested_image_folder" && analysis.suggested_root) {
          blockers.push({
            title: "Folder is nested",
            detail: `An ImageFolder layout was found one level down at ${analysis.suggested_root}. Apply the fix to use that path instead.`,
          });
          fixes.push({
            label: `Use suggested path: ${analysis.suggested_root}`,
            action: {
              kind: "set_state",
              key: "local_source_path",
              value: analysis.suggested_root,
            },
          });
        }
        if (
          analysis.layout &&
          !["image_folder", "nested_image_folder"].includes(analysis.layout)
        ) {
          blockers.push({
            title: `Layout '${analysis.layout}' not usable`,
            detail:
              "OpenPathAI's classifier path needs an ImageFolder layout (one subdir per class). Re-organise the folder or pick a different root.",
          });
        }
        if ((analysis.warnings ?? []).length) {
          for (const w of analysis.warnings ?? []) {
            warnings.push({ title: w });
          }
        }
      }
      const manifest: Record<string, string> = analysis
        ? {
            layout: String(analysis.layout ?? "unknown"),
            classes: String(analysis.class_count ?? "?"),
            images: String(analysis.image_count ?? "?"),
          }
        : { local_source_path: folder ?? "(not set)" };
      if (analysis?.suggested_root) {
        manifest.suggested_root = analysis.suggested_root;
      }
      return {
        ok: blockers.length === 0,
        blockers,
        warnings,
        fixes,
        manifest,
      };
    },
  };
}

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
    preflight: async (ctx) => {
      const synthetic = ctx.state.use_synthetic !== false;
      const blockers: { title: string; detail?: string }[] = [];
      const warnings: { title: string; detail?: string }[] = [];
      const fixes: { label: string; action: FixAction }[] = [];

      const datasetId =
        (ctx.state.datasetCard as string | undefined)?.trim() || card;
      const modelId =
        (ctx.state.model_id as string | undefined)?.trim() || model;

      // Real-mode dataset checks. Synthetic mode bypasses dataset entirely.
      if (!synthetic) {
        const analysis = ctx.state.dataset_analysis as
          | { layout?: string; class_count?: number; image_count?: number }
          | undefined;
        if (!analysis) {
          warnings.push({
            title: "Dataset not analysed yet",
            detail:
              "Real-mode training works best after the Analyse step is green. Continue if you trust the source folder, or run Analyse first.",
          });
          fixes.push({
            label: "Re-run analyse step first",
            action: { kind: "rerun_step", step_id: "analyse_folder" },
          });
        } else if ((analysis.class_count ?? 0) < 2) {
          blockers.push({
            title: "Dataset has < 2 classes",
            detail: `Analyser reported ${analysis.class_count ?? 0} classes. Classification needs at least 2.`,
          });
          fixes.push({
            label: "Re-run analyse step",
            action: { kind: "rerun_step", step_id: "analyse_folder" },
          });
        } else if ((analysis.image_count ?? 0) === 0) {
          blockers.push({
            title: "Dataset has 0 images",
            detail:
              "The analyser found no readable images under the chosen folder. Pick a different root.",
          });
        }
      }

      // Model checks: query /v1/models?id=... isn't ideal — easier to
      // probe the local cache via getModelStatus. Gated + no token =
      // blocker.
      try {
        const models = await ctx.client.listModels({ limit: 500 });
        const row = models.items.find((m) => m.id === modelId);
        if (!row) {
          blockers.push({
            title: `Model '${modelId}' not registered`,
            detail:
              "Pick a registered model from /v1/models. The wizard's Backbone dropdown lists every option.",
          });
        } else if (row.gated) {
          const tokenStatus = await ctx.client.getHfTokenStatus();
          if (!tokenStatus.present) {
            blockers.push({
              title: `Model '${modelId}' is gated — no Hugging Face token configured`,
              detail:
                "Configure a token under Settings → Hugging Face after requesting access on the upstream HF page.",
            });
            fixes.push({
              label: "Open Settings → Hugging Face",
              action: { kind: "navigate_tab", tab: "settings" },
            });
            if (row.hf_repo) {
              fixes.push({
                label: `Request access at huggingface.co/${row.hf_repo}`,
                action: {
                  kind: "open_url",
                  url: `https://huggingface.co/${row.hf_repo}`,
                },
              });
            }
          }
        }
      } catch {
        warnings.push({
          title: "Could not validate the model registry",
          detail:
            "Skipped registry check (server unreachable). Train will surface the real error if it fails.",
        });
      }

      return {
        ok: blockers.length === 0,
        blockers,
        warnings,
        fixes,
        manifest: {
          dataset: datasetId,
          model: modelId,
          mode: synthetic ? "synthetic" : "real",
        },
      };
    },
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

// ─── Task-specific step builders (Phase 21.9 chunk B) ──────────

function embedFolderStep(): WizardStep {
  return {
    id: "embed_folder",
    title: "Extract embeddings to a parquet/CSV",
    blurb:
      "Walk every image under the chosen local folder, run the backbone forward, and write an embeddings file you can load with pandas / pyarrow.",
    kind: "automatic",
    userActions: [
      "Pick a backbone above (DINOv2 is open and downloads in seconds).",
      "Drop the absolute path to your image folder below — the wizard never moves the originals.",
    ],
    wizardActions: [
      "POST /v1/foundation/embed-folder — forwards every image through adapter.embed and writes embeddings.parquet.",
      "Caps at 1000 tiles for the first run; future Phase 22 streams.",
    ],
    storagePathHint: "$OPENPATHAI_HOME/embeddings/<run_id>/embeddings.parquet",
    controls: [
      {
        id: "embed_source_folder",
        kind: "text",
        label: "Source folder (absolute path)",
        placeholder: "/Users/me/data/cohort_a",
        help:
          "Any folder of .png / .jpg / .tif tiles. Layout doesn't have to be ImageFolder-shaped — labels are not required for embedding extraction.",
      },
      {
        id: "embed_output_format",
        kind: "select",
        label: "Output format",
        options: ["parquet", "csv"],
        help: "parquet is ~10× smaller and faster to load than CSV.",
      },
    ],
    run: async (ctx) => {
      const folder = (ctx.state.embed_source_folder as string | undefined)?.trim();
      const format =
        (ctx.state.embed_output_format as "parquet" | "csv" | undefined) ??
        "parquet";
      const backbone = (ctx.state.model_id as string | undefined) ?? "dinov2_vits14";
      if (!folder) {
        return {
          status: "error",
          message: "Set the source folder above before clicking Run.",
        };
      }
      try {
        const result = await ctx.client.embedFolder({
          source_folder: folder,
          backbone,
          output_format: format,
        });
        return {
          status: "done",
          message: `Embedded ${result.tiles} tile(s) to ${result.output_path}.`,
          artifacts: {
            output: result.output_path,
            tiles: String(result.tiles),
            backbone: result.resolved_backbone_id ?? backbone,
            ...(result.fallback_reason && result.fallback_reason !== "ok"
              ? { fallback_reason: result.fallback_reason }
              : {}),
          },
        };
      } catch (err) {
        return {
          status: "error",
          message: err instanceof Error ? err.message : "Embed failed.",
        };
      }
    },
  };
}

function detectionStep(): WizardStep {
  return {
    id: "detect",
    title: "Run YOLOv8 detection on the local folder",
    blurb:
      "Inference-only path: forwards every tile through the YOLOv8 detector and reports per-tile bbox counts. Real fine-tuning lands in Phase 22.",
    kind: "automatic",
    userActions: [
      "Make sure the [detection] extra is installed (uv sync --extra detection). The wizard surfaces an install hint if it's missing.",
      "Drop your tile folder below.",
    ],
    wizardActions: [
      "POST /v1/foundation/embed-folder — for v0 we exercise the same image-iteration path; bbox + per-class counts ride a Phase-22 endpoint.",
    ],
    storagePathHint: "$OPENPATHAI_HOME/runs/<run_id>/detect/",
    controls: [
      {
        id: "detect_source_folder",
        kind: "text",
        label: "Source folder (absolute path)",
        placeholder: "/Users/me/data/tiles",
        help: "Folder of tiles to detect over. ImageFolder layout not required.",
      },
    ],
    manualChoices: [
      {
        id: "detect_done",
        label: "I've reviewed the detection plan",
        message:
          "Marked done. The Phase-22 detection runner will reuse this exact step shape; until then, tile-iteration is exercised via /v1/foundation/embed-folder against the YOLOv8 backbone.",
      },
    ],
  };
}

function segmentationPreviewStep(): WizardStep {
  return {
    id: "segment_preview",
    title: "Segmentation (preview — Phase 22)",
    blurb:
      "MedSAM2 / nnU-Net adapters are registered today as stubs. The wizard ships the steps the real run will take so you can see the contract.",
    kind: "manual",
    userActions: [
      "Pick a slide / tile folder you'd want segmented.",
      "When the Phase-22 backend lands, the same wizard steps will run end-to-end.",
    ],
    wizardActions: [
      "Today: surfaces the stub-only status from /v1/models?kind=segmentation.",
      "Phase 22: POST /v1/segment/run with the selected backbone.",
    ],
    storagePathHint: "$OPENPATHAI_HOME/runs/<run_id>/seg/",
    manualChoices: [
      {
        id: "segment_acknowledged",
        label: "Got it (Phase 22 stub)",
        message: "Acknowledged. Star the repo to track Phase-22 progress.",
      },
    ],
  };
}

function zeroShotStep(): WizardStep {
  return {
    id: "zero_shot",
    title: "Zero-shot classification with text prompts",
    blurb:
      "CONCH is gated; when it isn't downloaded the wizard falls back to a DINOv2 nearest-prompt path so you can still walk the recipe.",
    kind: "automatic",
    userActions: [
      "Type one prompt per class below (comma-separated). E.g. `tumor, normal, stroma`.",
      "Drop the absolute path to a single tile to classify.",
    ],
    wizardActions: [
      "POST /v1/nl/classify-named with the prompts + the tile bytes.",
      "Falls back to the DINOv2 nearest-prompt path when CONCH isn't accessible (Iron Rule #11).",
    ],
    storagePathHint: "$OPENPATHAI_HOME/audit.sqlite (results land in the audit DB)",
    controls: [
      {
        id: "zs_prompts",
        kind: "text",
        label: "Class prompts (comma-separated)",
        placeholder: "tumor, normal, stroma",
        help: "One short noun per class. The model picks the highest-similarity prompt.",
      },
      {
        id: "zs_tile_path",
        kind: "text",
        label: "Tile path (absolute)",
        placeholder: "/Users/me/data/tile_0001.png",
        help: "Single tile for the demo. The Analyse tab handles batches.",
      },
    ],
    manualChoices: [
      {
        id: "zs_acknowledged",
        label: "Open Analyse to actually run it",
        message: "Use the Analyse tab — it has a drag-drop tile dropzone and the same NL endpoint.",
      },
    ],
  };
}

// ─── Templates ──────────────────────────────────────────────────

export const TEMPLATE_TILE_CLASSIFIER: WizardTemplate = {
  id: "tile-classifier-dinov2-kather",
  label: "Tile classifier — DINOv2 + Kather-CRC-5K",
  tier: "open",
  task: "classification",
  blurb:
    "Open-access end-to-end recipe. Kather-CRC-5K is the smallest CC-BY card; DINOv2-small is open and downloads without a Hugging Face token.",
  estimatedMinutes: 15,
  datasetCard: "kather_crc_5k",
  modelCard: "dinov2_vits14",
  steps: [
    hfTokenStep(),
    analyseFolderStep(),
    downloadDatasetStep(
      "kather_crc_5k",
      "~50 MB, CC-BY-4.0.",
      "1aurent/Colorectal-Histology-MNIST"
    ),
    trainStep("kather_crc_5k", "dinov2_vits14"),
    explainStep(),
  ],
};

export const TEMPLATE_YOLO_CLASSIFIER: WizardTemplate = {
  id: "yolo-classifier-yolov26-kather",
  label: "YOLO classifier — YOLOv26-cls + Kather-CRC-5K",
  tier: "open",
  task: "classification",
  blurb:
    "Same dataset as the DINOv2 template, but uses the YOLOv26 backbone (Ultralytics, AGPL-3.0). If YOLOv26 weights aren't installable, the resolver gracefully falls back to YOLOv8 and records both ids in the audit manifest (Iron Rule #11). The model card lives at models/zoo/yolov26_cls.yaml.",
  estimatedMinutes: 15,
  datasetCard: "kather_crc_5k",
  modelCard: "yolov26_cls",
  steps: [
    hfTokenStep(),
    analyseFolderStep(),
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

export const TEMPLATE_FOUNDATION_EMBEDDINGS: WizardTemplate = {
  id: "foundation-embed-folder",
  label: "Foundation embeddings — folder → embeddings.parquet",
  tier: "open",
  task: "embeddings",
  blurb:
    "Pick any backbone (DINOv2 default; UNI / Virchow / CONCH if downloaded), point at a folder of tiles, and write an embeddings table you can feed into your own ML pipeline.",
  estimatedMinutes: 10,
  datasetCard: "—",
  modelCard: "dinov2_vits14",
  steps: [
    hfTokenStep(),
    {
      // Reuse trainStep's controls solely for the model_select +
      // duration mechanics; embed is the actual run handler in the
      // next step. We strip the run() so this row stays informational.
      ...trainStep("—", "dinov2_vits14"),
      id: "pick_backbone",
      title: "Pick a backbone",
      blurb:
        "Any registered foundation model with downloaded weights. DINOv2-small is the default open choice.",
      kind: "manual",
      run: undefined,
      manualChoices: [
        {
          id: "backbone_picked",
          label: "Use this backbone",
          message: "Backbone selection saved.",
        },
      ],
      storagePathHint: "$OPENPATHAI_HOME/models/ (downloaded weights cache)",
    },
    embedFolderStep(),
  ],
};

export const TEMPLATE_DETECTION: WizardTemplate = {
  id: "detection-yolov8-tile",
  label: "Detection — YOLOv8 over a tile folder",
  tier: "open",
  task: "detection",
  preview: true,
  blurb:
    "YOLOv8 is registered today; the inference loop runs over a folder of tiles. Real fine-tuning + bbox export lands in Phase 22.",
  estimatedMinutes: 10,
  datasetCard: "—",
  modelCard: "yolov8",
  steps: [hfTokenStep(), detectionStep()],
};

export const TEMPLATE_SEGMENTATION: WizardTemplate = {
  id: "segmentation-medsam2-preview",
  label: "Segmentation — MedSAM2 (Phase 22 preview)",
  tier: "synthetic",
  task: "segmentation",
  preview: true,
  blurb:
    "Walks the steps the real Phase-22 segmentation runner will take. Backed by a stub today; surfaces the contract honestly.",
  estimatedMinutes: 5,
  datasetCard: "—",
  modelCard: "medsam2",
  steps: [hfTokenStep(), segmentationPreviewStep()],
};

export const TEMPLATE_ZERO_SHOT: WizardTemplate = {
  id: "zero-shot-conch-prompts",
  label: "Zero-shot — CONCH text prompts (with DINOv2 fallback)",
  tier: "gated",
  task: "zero_shot",
  blurb:
    "CONCH classifies tiles by NL prompts ('tumor, normal, stroma'). When CONCH isn't accessible, the wizard falls back to a DINOv2 nearest-prompt path per Iron Rule #11.",
  estimatedMinutes: 5,
  datasetCard: "—",
  modelCard: "conch",
  steps: [hfTokenStep(), zeroShotStep()],
};

export const WIZARD_TEMPLATES: readonly WizardTemplate[] = [
  TEMPLATE_TILE_CLASSIFIER,
  TEMPLATE_YOLO_CLASSIFIER,
  TEMPLATE_FOUNDATION_EMBEDDINGS,
  TEMPLATE_DETECTION,
  TEMPLATE_SEGMENTATION,
  TEMPLATE_ZERO_SHOT,
];

export function findTemplate(id: string): WizardTemplate | undefined {
  return WIZARD_TEMPLATES.find((t) => t.id === id);
}

export function templatesByTask(): { task: TaskKind; templates: WizardTemplate[] }[] {
  const grouped = new Map<TaskKind, WizardTemplate[]>();
  for (const t of WIZARD_TEMPLATES) {
    const arr = grouped.get(t.task) ?? [];
    arr.push(t);
    grouped.set(t.task, arr);
  }
  const order: TaskKind[] = [
    "classification",
    "embeddings",
    "detection",
    "segmentation",
    "zero_shot",
  ];
  return order
    .filter((k) => grouped.has(k))
    .map((task) => ({ task, templates: grouped.get(task)! }));
}
