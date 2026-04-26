// Typed HTTP client for the Phase-19 /v1 API.
//
// Every method accepts the bearer token explicitly so the client is a
// pure-function module — no React context, no module-level state. The
// React layer wraps it via ``api-context.tsx`` so components stay
// declarative.

import type {
  ActiveLearningSession,
  AuditRunRow,
  BrowserCorrection,
  CohortQCSummary,
  CohortSummary,
  ComputeHeatmapRequest,
  DatasetCard,
  DatasetDownloadRequest,
  DatasetDownloadResult,
  DatasetStatus,
  ExtrasResponse,
  HFTokenClearResult,
  HFTokenSetResult,
  HFTokenStatus,
  HFTokenTestResult,
  Health,
  HeatmapSummary,
  ModelDownloadResult,
  ModelSizeEstimate,
  ModelStatus,
  ModelSummary,
  NodesResponse,
  Paged,
  Pipeline,
  PipelineEnvelope,
  PipelineValidation,
  RegisterFolderRequest,
  RunAuditDetail,
  RunRecord,
  RunRequest,
  SlideSummary,
  StoragePaths,
  SubmitCorrectionsResult,
  TilePrediction,
  TrainMetricsResponse,
  TrainSubmitRequest,
  Version,
  ZeroShotNamedResult,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

export type RequestOptions = {
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | undefined>;
};

export class ApiClient {
  baseUrl: string;
  token: string | null;

  constructor(baseUrl: string, token: string | null = null) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.token = token;
  }

  withToken(token: string | null): ApiClient {
    return new ApiClient(this.baseUrl, token);
  }

  private buildUrl(path: string, query?: RequestOptions["query"]): string {
    const url = new URL(this.baseUrl + path);
    if (query) {
      for (const [key, value] of Object.entries(query)) {
        if (value !== undefined && value !== null && value !== "") {
          url.searchParams.set(key, String(value));
        }
      }
    }
    return url.toString();
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    options: RequestOptions = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      Accept: "application/json",
    };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const init: RequestInit = {
      method,
      headers,
      signal: options.signal,
    };
    if (body !== undefined) {
      init.body = JSON.stringify(body);
    }
    const response = await fetch(this.buildUrl(path, options.query), init);
    if (response.status === 204) {
      return undefined as T;
    }
    const text = await response.text();
    let payload: unknown = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }
    if (!response.ok) {
      const detail =
        (payload &&
          typeof payload === "object" &&
          "detail" in (payload as Record<string, unknown>) &&
          typeof (payload as Record<string, unknown>).detail === "string"
          ? ((payload as Record<string, unknown>).detail as string)
          : null) ?? `request failed`;
      throw new ApiError(response.status, detail);
    }
    return payload as T;
  }

  // ─── Health + version ────────────────────────────────────────────

  health(options?: RequestOptions): Promise<Health> {
    return this.request("GET", "/v1/health", undefined, options);
  }

  version(options?: RequestOptions): Promise<Version> {
    return this.request("GET", "/v1/version", undefined, options);
  }

  // ─── Catalogs ────────────────────────────────────────────────────

  listNodes(options?: RequestOptions): Promise<NodesResponse> {
    return this.request("GET", "/v1/nodes", undefined, options);
  }

  listModels(
    query?: { kind?: string; q?: string; limit?: number; offset?: number },
    options?: RequestOptions
  ): Promise<Paged<ModelSummary>> {
    return this.request("GET", "/v1/models", undefined, {
      ...options,
      query: { ...query, ...(options?.query ?? {}) },
    });
  }

  listDatasets(
    query?: { q?: string; limit?: number; offset?: number },
    options?: RequestOptions
  ): Promise<Paged<DatasetCard>> {
    return this.request("GET", "/v1/datasets", undefined, {
      ...options,
      query: { ...query, ...(options?.query ?? {}) },
    });
  }

  // ─── Pipelines ───────────────────────────────────────────────────

  listPipelines(
    query?: { limit?: number; offset?: number },
    options?: RequestOptions
  ): Promise<Paged<PipelineEnvelope>> {
    return this.request("GET", "/v1/pipelines", undefined, {
      ...options,
      query: { ...query, ...(options?.query ?? {}) },
    });
  }

  getPipeline(
    pipelineId: string,
    options?: RequestOptions
  ): Promise<PipelineEnvelope> {
    return this.request(
      "GET",
      `/v1/pipelines/${encodeURIComponent(pipelineId)}`,
      undefined,
      options
    );
  }

  putPipeline(
    pipelineId: string,
    body: Pipeline,
    options?: RequestOptions
  ): Promise<PipelineEnvelope> {
    return this.request(
      "PUT",
      `/v1/pipelines/${encodeURIComponent(pipelineId)}`,
      body,
      options
    );
  }

  deletePipeline(pipelineId: string, options?: RequestOptions): Promise<void> {
    return this.request(
      "DELETE",
      `/v1/pipelines/${encodeURIComponent(pipelineId)}`,
      undefined,
      options
    );
  }

  validatePipeline(
    body: Pipeline,
    options?: RequestOptions
  ): Promise<PipelineValidation> {
    return this.request("POST", "/v1/pipelines/validate", body, options);
  }

  // ─── Runs ────────────────────────────────────────────────────────

  listRuns(
    query?: { limit?: number; offset?: number; status?: string },
    options?: RequestOptions
  ): Promise<Paged<RunRecord>> {
    return this.request("GET", "/v1/runs", undefined, {
      ...options,
      query: { ...query, ...(options?.query ?? {}) },
    });
  }

  createRun(body: RunRequest, options?: RequestOptions): Promise<RunRecord> {
    return this.request("POST", "/v1/runs", body, options);
  }

  getRun(runId: string, options?: RequestOptions): Promise<RunRecord> {
    return this.request(
      "GET",
      `/v1/runs/${encodeURIComponent(runId)}`,
      undefined,
      options
    );
  }

  getRunManifest(
    runId: string,
    options?: RequestOptions
  ): Promise<Record<string, unknown>> {
    return this.request(
      "GET",
      `/v1/runs/${encodeURIComponent(runId)}/manifest`,
      undefined,
      options
    );
  }

  cancelRun(runId: string, options?: RequestOptions): Promise<RunRecord> {
    return this.request(
      "DELETE",
      `/v1/runs/${encodeURIComponent(runId)}`,
      undefined,
      options
    );
  }

  // ─── Audit ───────────────────────────────────────────────────────

  listAuditRuns(
    query?: { kind?: string; status?: string; limit?: number },
    options?: RequestOptions
  ): Promise<Paged<AuditRunRow>> {
    return this.request("GET", "/v1/audit/runs", undefined, {
      ...options,
      query: { ...query, ...(options?.query ?? {}) },
    });
  }

  // ─── Phase 20.5 task surfaces ─────────────────────────────────────

  /** ``POST /v1/analyse/tile`` — multipart upload of one tile + model id. */
  async analyseTile(
    image: File | Blob,
    args: { modelName: string; explainer?: string; low?: number; high?: number },
    options?: RequestOptions
  ): Promise<TilePrediction> {
    const form = new FormData();
    form.append("image", image, image instanceof File ? image.name : "tile.png");
    form.append("model_name", args.modelName);
    form.append("explainer", args.explainer ?? "gradcam");
    form.append("low", String(args.low ?? 0.4));
    form.append("high", String(args.high ?? 0.6));
    const headers: Record<string, string> = { Accept: "application/json" };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const response = await fetch(this.buildUrl("/v1/analyse/tile"), {
      method: "POST",
      headers,
      body: form,
      signal: options?.signal,
    });
    const text = await response.text();
    let payload: unknown = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }
    if (!response.ok) {
      const detail =
        (payload &&
          typeof payload === "object" &&
          "detail" in (payload as Record<string, unknown>) &&
          typeof (payload as Record<string, unknown>).detail === "string"
          ? ((payload as Record<string, unknown>).detail as string)
          : null) ?? "analyse failed";
      throw new ApiError(response.status, detail);
    }
    return payload as TilePrediction;
  }

  /** ``POST /v1/analyse/report`` — render the last analysis as a PDF. */
  async analyseReport(options?: RequestOptions): Promise<Blob> {
    const headers: Record<string, string> = { Accept: "application/pdf" };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const response = await fetch(this.buildUrl("/v1/analyse/report"), {
      method: "POST",
      headers,
      signal: options?.signal,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new ApiError(response.status, text || "report failed");
    }
    return response.blob();
  }

  registerDatasetFolder(
    body: RegisterFolderRequest,
    options?: RequestOptions
  ): Promise<DatasetCard> {
    return this.request("POST", "/v1/datasets/register", body, options);
  }

  listCohorts(
    options?: RequestOptions
  ): Promise<Paged<CohortSummary>> {
    return this.request("GET", "/v1/cohorts", undefined, options);
  }

  createCohort(
    body: { id: string; directory: string; pattern?: string | null },
    options?: RequestOptions
  ): Promise<CohortSummary> {
    return this.request("POST", "/v1/cohorts", body, options);
  }

  deleteCohort(cohortId: string, options?: RequestOptions): Promise<void> {
    return this.request(
      "DELETE",
      `/v1/cohorts/${encodeURIComponent(cohortId)}`,
      undefined,
      options
    );
  }

  cohortQc(cohortId: string, options?: RequestOptions): Promise<CohortQCSummary> {
    return this.request(
      "POST",
      `/v1/cohorts/${encodeURIComponent(cohortId)}/qc`,
      undefined,
      options
    );
  }

  startActiveLearningSession(
    body: {
      classes: string[];
      pool_size?: number;
      seed_size?: number;
      holdout_size?: number;
      iterations?: number;
      budget_per_iteration?: number;
      scorer?: string;
      diversity_weight?: number;
      random_seed?: number;
    },
    options?: RequestOptions
  ): Promise<ActiveLearningSession> {
    return this.request(
      "POST",
      "/v1/active-learning/sessions",
      body,
      options
    );
  }

  listActiveLearningSessions(
    options?: RequestOptions
  ): Promise<Paged<ActiveLearningSession>> {
    return this.request(
      "GET",
      "/v1/active-learning/sessions",
      undefined,
      options
    );
  }

  classifyNamed(
    body: {
      image_b64: string;
      classes: string[];
      prompt_template?: string;
    },
    options?: RequestOptions
  ): Promise<ZeroShotNamedResult> {
    return this.request("POST", "/v1/nl/classify-named", body, options);
  }

  submitTrain(
    body: TrainSubmitRequest,
    options?: RequestOptions
  ): Promise<RunRecord> {
    return this.request("POST", "/v1/train", body, options);
  }

  getTrainMetrics(
    runId: string,
    options?: RequestOptions
  ): Promise<TrainMetricsResponse> {
    return this.request(
      "GET",
      `/v1/train/runs/${encodeURIComponent(runId)}/metrics`,
      undefined,
      options
    );
  }

  // ─── Phase 21 — slides + heatmaps + audit-full + corrections ──────

  async uploadSlide(
    file: File | Blob,
    options?: RequestOptions
  ): Promise<SlideSummary> {
    const form = new FormData();
    form.append(
      "file",
      file,
      file instanceof File ? file.name : "slide.tif"
    );
    const headers: Record<string, string> = { Accept: "application/json" };
    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    const response = await fetch(this.buildUrl("/v1/slides"), {
      method: "POST",
      headers,
      body: form,
      signal: options?.signal,
    });
    const text = await response.text();
    let payload: unknown = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }
    if (!response.ok) {
      const detail =
        (payload &&
          typeof payload === "object" &&
          "detail" in (payload as Record<string, unknown>) &&
          typeof (payload as Record<string, unknown>).detail === "string"
          ? ((payload as Record<string, unknown>).detail as string)
          : null) ?? "slide upload failed";
      throw new ApiError(response.status, detail);
    }
    return payload as SlideSummary;
  }

  listSlides(options?: RequestOptions): Promise<Paged<SlideSummary>> {
    return this.request("GET", "/v1/slides", undefined, options);
  }

  getSlide(slideId: string, options?: RequestOptions): Promise<SlideSummary> {
    return this.request(
      "GET",
      `/v1/slides/${encodeURIComponent(slideId)}`,
      undefined,
      options
    );
  }

  deleteSlide(slideId: string, options?: RequestOptions): Promise<void> {
    return this.request(
      "DELETE",
      `/v1/slides/${encodeURIComponent(slideId)}`,
      undefined,
      options
    );
  }

  /** Absolute URL the OpenSeadragon viewer uses as ``tileSources``.
   *
   * The viewer's tile fetches are not always able to inject the bearer
   * header (some proxies / browsers strip it on image loads). When
   * ``withToken`` is set we append ``?token=<bearer>`` so the URL is
   * self-authenticating — the Phase-21 auth dependency honours it
   * alongside the Authorization header.
   */
  slideDziUrl(slideId: string, opts?: { withToken?: boolean }): string {
    const path = `/v1/slides/${encodeURIComponent(slideId)}.dzi`;
    return this.buildUrl(
      path,
      opts?.withToken && this.token ? { token: this.token } : undefined
    );
  }

  computeHeatmap(
    body: ComputeHeatmapRequest,
    options?: RequestOptions
  ): Promise<HeatmapSummary> {
    return this.request("POST", "/v1/heatmaps", body, options);
  }

  listHeatmaps(
    query?: { slide_id?: string; limit?: number; offset?: number },
    options?: RequestOptions
  ): Promise<Paged<HeatmapSummary>> {
    return this.request("GET", "/v1/heatmaps", undefined, {
      ...options,
      query: { ...query, ...(options?.query ?? {}) },
    });
  }

  deleteHeatmap(heatmapId: string, options?: RequestOptions): Promise<void> {
    return this.request(
      "DELETE",
      `/v1/heatmaps/${encodeURIComponent(heatmapId)}`,
      undefined,
      options
    );
  }

  heatmapDziUrl(heatmapId: string, opts?: { withToken?: boolean }): string {
    const path = `/v1/heatmaps/${encodeURIComponent(heatmapId)}.dzi`;
    return this.buildUrl(
      path,
      opts?.withToken && this.token ? { token: this.token } : undefined
    );
  }

  getFullAudit(
    runId: string,
    options?: RequestOptions
  ): Promise<RunAuditDetail> {
    return this.request(
      "GET",
      `/v1/audit/runs/${encodeURIComponent(runId)}/full`,
      undefined,
      options
    );
  }

  submitBrowserCorrections(
    sessionId: string,
    body: { annotator_id?: string; corrections: BrowserCorrection[] },
    options?: RequestOptions
  ): Promise<SubmitCorrectionsResult> {
    return this.request(
      "POST",
      `/v1/active-learning/sessions/${encodeURIComponent(sessionId)}/corrections`,
      body,
      options
    );
  }

  cohortQcHtmlUrl(cohortId: string): string {
    return this.buildUrl(`/v1/cohorts/${encodeURIComponent(cohortId)}/qc.html`);
  }

  cohortQcPdfUrl(cohortId: string): string {
    return this.buildUrl(`/v1/cohorts/${encodeURIComponent(cohortId)}/qc.pdf`);
  }

  // ─── Phase 21.5 chunk C — Hugging Face token ───────────────────

  getHfTokenStatus(options?: RequestOptions): Promise<HFTokenStatus> {
    return this.request("GET", "/v1/credentials/huggingface", undefined, options);
  }

  setHfToken(
    token: string,
    options?: RequestOptions
  ): Promise<HFTokenSetResult> {
    return this.request(
      "PUT",
      "/v1/credentials/huggingface",
      { token },
      options
    );
  }

  clearHfToken(options?: RequestOptions): Promise<HFTokenClearResult> {
    return this.request(
      "DELETE",
      "/v1/credentials/huggingface",
      undefined,
      options
    );
  }

  testHfToken(options?: RequestOptions): Promise<HFTokenTestResult> {
    return this.request(
      "POST",
      "/v1/credentials/huggingface/test",
      undefined,
      options
    );
  }

  // ─── Phase 21.6 — dataset downloads + storage ─────────────────

  downloadDataset(
    name: string,
    body: DatasetDownloadRequest = {},
    options?: RequestOptions
  ): Promise<DatasetDownloadResult> {
    return this.request(
      "POST",
      `/v1/datasets/${encodeURIComponent(name)}/download`,
      body,
      options
    );
  }

  getDatasetStatus(
    name: string,
    options?: RequestOptions
  ): Promise<DatasetStatus> {
    return this.request(
      "GET",
      `/v1/datasets/${encodeURIComponent(name)}/status`,
      undefined,
      options
    );
  }

  getStoragePaths(options?: RequestOptions): Promise<StoragePaths> {
    return this.request("GET", "/v1/storage/paths", undefined, options);
  }

  // ─── Phase 21.7 chunk D — extras status ──────────────────────

  getExtras(options?: RequestOptions): Promise<ExtrasResponse> {
    return this.request("GET", "/v1/extras", undefined, options);
  }

  // ─── Phase 21.8 chunk B — per-model download + status ────────

  getModelStatus(
    modelId: string,
    options?: RequestOptions
  ): Promise<ModelStatus> {
    return this.request(
      "GET",
      `/v1/models/${encodeURIComponent(modelId)}/status`,
      undefined,
      options
    );
  }

  getModelSizeEstimate(
    modelId: string,
    options?: RequestOptions
  ): Promise<ModelSizeEstimate> {
    return this.request(
      "GET",
      `/v1/models/${encodeURIComponent(modelId)}/size-estimate`,
      undefined,
      options
    );
  }

  downloadModel(
    modelId: string,
    options?: RequestOptions
  ): Promise<ModelDownloadResult> {
    return this.request(
      "POST",
      `/v1/models/${encodeURIComponent(modelId)}/download`,
      undefined,
      options
    );
  }
}

export function defaultBaseUrl(): string {
  const env = (
    import.meta as unknown as { env?: Record<string, string | undefined> }
  ).env;
  if (env?.VITE_API_BASE_URL) {
    return env.VITE_API_BASE_URL;
  }
  if (typeof window !== "undefined" && window.location?.origin) {
    // When the canvas is served from the FastAPI app itself, hit the
    // same origin. The Vite dev server falls back to 7870 below.
    return window.location.origin;
  }
  return "http://127.0.0.1:7870";
}
