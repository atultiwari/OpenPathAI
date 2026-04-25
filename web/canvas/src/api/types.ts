// Wire shapes for the Phase-19 /v1 API. Kept minimal — just the
// fields the canvas actually reads. New fields on the backend pass
// through transparently because every type uses ``unknown``-tolerant
// records where appropriate.

export type Health = {
  status: string;
  api_version: string;
};

export type Version = {
  openpathai_version: string;
  api_version: string;
  commit: string | null;
};

export type JsonSchema = Record<string, unknown> & {
  type?: string;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  enum?: unknown[];
  default?: unknown;
  description?: string;
  items?: JsonSchema;
  minimum?: number;
  maximum?: number;
  format?: string;
};

export type NodeSummary = {
  id: string;
  description: string;
  code_hash: string;
  input_schema: JsonSchema;
  output_schema: JsonSchema;
};

export type NodesResponse = {
  items: NodeSummary[];
  total: number;
};

export type ModelSummary = {
  id: string;
  kind: string;
  display_name: string;
  license: string | null;
  gated: boolean;
  citation: string | null;
  hf_repo: string | null;
  embedding_dim: number | null;
  input_size: [number, number] | null;
  tier_compatibility: string[];
};

export type Paged<T> = {
  items: T[];
  total: number;
  limit?: number;
  offset?: number;
};

export type DatasetCard = {
  name: string;
  display_name?: string;
  modality?: string;
  num_classes?: number;
  classes?: string[];
  [key: string]: unknown;
};

export type PipelineStep = {
  id: string;
  op: string;
  inputs: Record<string, unknown>;
};

export type Pipeline = {
  id: string;
  mode: "exploratory" | "diagnostic";
  steps: PipelineStep[];
  cohort_fanout?: string | null;
  max_workers?: number | null;
};

export type PipelineEnvelope = {
  id: string;
  pipeline: Pipeline;
  graph_hash: string;
};

export type PipelineValidation = {
  valid: boolean;
  errors: string[];
  graph_hash: string | null;
  unknown_ops: string[];
};

export type RunStatus =
  | "queued"
  | "running"
  | "success"
  | "error"
  | "cancelled";

export type RunRecord = {
  run_id: string;
  status: RunStatus;
  submitted_at: string;
  started_at: string | null;
  ended_at: string | null;
  error: string | null;
  metadata: Record<string, unknown>;
};

export type RunRequest = {
  pipeline?: Pipeline;
  saved_pipeline_id?: string;
  parallel_mode?: "sequential" | "thread";
  max_workers?: number;
};

export type AuditRunRow = {
  run_id?: string;
  kind?: string;
  status?: string;
  timestamp_start?: string;
  manifest_path?: string;
  metrics_json?: string | null;
  [key: string]: unknown;
};

// ─── Phase 20.5 task-shaped wire shapes ─────────────────────────

export type TilePrediction = {
  image_sha256: string;
  model_name: string;
  resolved_model_name: string;
  explainer_name: string;
  classes: string[];
  probabilities: number[];
  predicted_class: string;
  confidence: number;
  borderline: boolean;
  heatmap_b64: string;
  thumbnail_b64: string;
  fallback_reason: string | null;
};

export type RegisterFolderRequest = {
  path: string;
  name: string;
  tissue: string[];
  classes?: string[] | null;
  display_name?: string | null;
  license?: string;
  stain?: string;
  overwrite?: boolean;
};

export type CohortSummary = {
  id: string;
  slide_count?: number;
  slide_ids?: string[];
  error?: string;
};

export type CohortQCSummary = {
  id: string;
  summary: { pass: number; warn: number; fail: number };
  slide_count: number;
};

export type ActiveLearningManifest = {
  run_id: string;
  config: Record<string, unknown>;
  started_at: string;
  finished_at: string;
  acquisitions: Array<{
    iteration: number;
    selected_tile_ids: string[];
    ece_before: number;
    ece_after: number;
    accuracy_after: number;
    train_loss: number;
  }>;
  initial_ece: number;
  final_ece: number;
  final_accuracy: number;
  acquired_tile_ids: string[];
};

export type ActiveLearningSession = {
  id: string;
  manifest: ActiveLearningManifest;
};

export type ZeroShotNamedResult = {
  classes: string[];
  prompts: string[];
  probs: number[];
  predicted_prompt: string;
  resolved_backbone_id: string;
};

export type TrainSubmitRequest = {
  dataset: string;
  model: string;
  epochs?: number;
  batch_size?: number;
  learning_rate?: number;
  seed?: number;
  synthetic?: boolean;
  duration_preset?: "Quick" | "Standard" | "Thorough";
};

export type TrainMetricsResponse = {
  run_id: string;
  status: RunStatus;
  metadata: Record<string, unknown>;
  error: string | null;
  result?: Record<string, unknown>;
};
