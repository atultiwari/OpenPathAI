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
  epochs?: TrainEpochPoint[];
  best?: { epoch: number; val_accuracy: number };
  mode?: "synthetic" | "lightning";
};

export type TrainEpochPoint = {
  epoch: number;
  train_loss: number;
  val_loss: number | null;
  val_accuracy: number | null;
  ece: number | null;
};

// ─── Phase 21 wire shapes ───────────────────────────────────────

export type SlideSummary = {
  slide_id: string;
  filename: string;
  size_bytes: number;
  width: number;
  height: number;
  mpp: number | null;
  level_count: number;
  backend: string;
  dzi_url: string;
  tile_url_template: string;
};

export type HeatmapSummary = {
  heatmap_id: string;
  slide_id: string;
  model_name: string;
  resolved_model_name: string;
  classes: string[];
  fallback_reason: string | null;
  width: number;
  height: number;
  dzi_url: string;
  tile_url_template: string;
};

export type ComputeHeatmapRequest = {
  slide_id: string;
  model_name?: string;
  classes?: string[];
  tile_grid?: number;
};

export type RunAuditDetail = {
  run_id: string;
  audit: Record<string, unknown> | null;
  runtime: Record<string, unknown> | null;
  manifest: Record<string, unknown> | null;
  cache_stats: Record<string, unknown> | null;
  analyses: Record<string, unknown>[];
  signature: Record<string, unknown> | null;
};

export type BrowserCorrection = {
  tile_id: string;
  predicted_label?: string;
  corrected_label: string;
  iteration?: number;
};

export type SubmitCorrectionsResult = {
  id: string;
  written: number;
  annotator_id: string;
  timestamp: string;
};

export type TierLevel = "Easy" | "Standard" | "Expert";
export type RunMode = "exploratory" | "diagnostic";

// ─── Phase 21.5 chunk C — credentials ───────────────────────────

export type HFTokenSource =
  | "settings"
  | "env_hf_token"
  | "env_hub_token"
  | "none";

export type HFTokenStatus = {
  present: boolean;
  source: HFTokenSource;
  token_preview: string | null;
};

export type HFTokenSetResult = {
  saved: boolean;
  secrets_path: string;
  status: HFTokenStatus;
};

export type HFTokenClearResult = {
  cleared: boolean;
  status: HFTokenStatus;
};

export type HFTokenTestResult = {
  ok: boolean;
  user: string | null;
  reason: string | null;
  status: HFTokenStatus;
};

// ─── Phase 21.6 — dataset download + storage paths ──────────────

export type DatasetDownloadStatus =
  | "downloaded"
  | "manual"
  | "missing_backend"
  | "skipped"
  | "error";

export type DatasetDownloadResult = {
  dataset: string;
  status: DatasetDownloadStatus;
  method: string;
  target_dir: string;
  files_written: number;
  bytes_written: number | null;
  message: string | null;
  extra_required: string | null;
};

export type DatasetStatus = {
  dataset: string;
  present: boolean;
  target_dir: string;
  files: number;
  bytes: number;
};

export type DatasetDownloadRequest = {
  subset?: number;
  allow_patterns?: string[];
  dry_run?: boolean;
  override_url?: string;
  override_huggingface_repo?: string;
  local_source_path?: string;
};

export type StoragePaths = {
  openpathai_home: string;
  datasets: string;
  models: string;
  checkpoints: string;
  dzi: string;
  audit_db: string;
  cache: string;
  secrets: string;
  hf_hub_cache: string;
  pipelines: string;
};
