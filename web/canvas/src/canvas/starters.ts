// Starter pipeline templates surfaced from the Pipelines toolbar.
//
// Each starter targets ops that are *actually* registered today (see
// src/openpathai/{demo,training,explain}/*). When real Hugging Face
// nodes (CONCH zero-shot, UNI features, DINOv2 embed) ship in Phase 22+
// we add them here too — the dropdown filters out any starter whose
// ops are missing from the live catalog so a fresh laptop never sees
// a broken template.

import type { CanvasState } from "./types";

export type StarterTier = "open" | "gated" | "synthetic";

export type StarterPipeline = {
  id: string;
  label: string;
  tier: StarterTier;
  blurb: string;
  build: () => CanvasState;
};

function helloCanvas(): CanvasState {
  return {
    pipelineId: "hello_canvas",
    mode: "exploratory",
    nodes: [
      {
        id: "constant_a",
        type: "openpathai",
        position: { x: 80, y: 120 },
        data: { op: "demo.constant", inputs: { value: 21 } },
      },
      {
        id: "constant_b",
        type: "openpathai",
        position: { x: 80, y: 260 },
        data: { op: "demo.constant", inputs: { value: 21 } },
      },
      {
        id: "double_a",
        type: "openpathai",
        position: { x: 360, y: 120 },
        data: {
          op: "demo.double",
          inputs: { value: { ref: "constant_a", field: "value" } },
        },
      },
      {
        id: "mean_ab",
        type: "openpathai",
        position: { x: 640, y: 200 },
        data: {
          op: "demo.mean",
          inputs: {
            a: { ref: "double_a", field: "value" },
            b: { ref: "constant_b", field: "value" },
          },
        },
      },
    ],
    edges: [
      {
        id: "e1",
        source: "constant_a",
        target: "double_a",
      },
      {
        id: "e2",
        source: "double_a",
        target: "mean_ab",
      },
      {
        id: "e3",
        source: "constant_b",
        target: "mean_ab",
      },
    ],
  };
}

function trainTileClassifier(): CanvasState {
  return {
    pipelineId: "train_tile_classifier_synthetic",
    mode: "exploratory",
    nodes: [
      {
        id: "train_1",
        type: "openpathai",
        position: { x: 200, y: 180 },
        data: {
          op: "training.train",
          inputs: {
            // training.train accepts a TrainingNodeInput; users edit the
            // schema-driven form in the Inspector. We seed only the
            // safest defaults that work on a fresh laptop with no
            // dataset on disk.
            train_batch_hash: "",
            val_batch_hash: "",
            checkpoint_dir: "",
          },
        },
      },
    ],
    edges: [],
  };
}

function trainPlusGradcam(): CanvasState {
  return {
    pipelineId: "train_then_gradcam",
    mode: "exploratory",
    nodes: [
      {
        id: "train_1",
        type: "openpathai",
        position: { x: 120, y: 200 },
        data: {
          op: "training.train",
          inputs: {
            train_batch_hash: "",
            val_batch_hash: "",
            checkpoint_dir: "",
          },
        },
      },
      {
        id: "gradcam_1",
        type: "openpathai",
        position: { x: 520, y: 200 },
        data: {
          op: "explain.gradcam",
          inputs: {
            target_digest: "",
            target_class: 0,
            kind: "gradcam",
            model_card: { ref: "train_1", field: "model_card" },
          },
        },
      },
    ],
    edges: [
      {
        id: "e1",
        source: "train_1",
        target: "gradcam_1",
      },
    ],
  };
}

export const STARTER_PIPELINES: readonly StarterPipeline[] = [
  {
    id: "hello_canvas",
    label: "Hello canvas (no-ML smoke test)",
    tier: "open",
    blurb:
      "Three demo nodes wired into a tree. Validates the pipeline machinery — runs in milliseconds with no model or dataset.",
    build: helloCanvas,
  },
  {
    id: "train_tile_classifier",
    label: "Train a tile classifier (synthetic)",
    tier: "synthetic",
    blurb:
      "Single training.train node; flip the Inspector's `synthetic` flag on to run end-to-end without a dataset on disk.",
    build: trainTileClassifier,
  },
  {
    id: "train_then_gradcam",
    label: "Train → Grad-CAM",
    tier: "synthetic",
    blurb:
      "Chains training.train with explain.gradcam. Same synthetic seed as above, plus a class-discriminative heatmap on a held-out tile.",
    build: trainPlusGradcam,
  },
];

export function starterOps(starter: StarterPipeline): readonly string[] {
  const built = starter.build();
  return Array.from(new Set(built.nodes.map((n) => n.data.op)));
}
