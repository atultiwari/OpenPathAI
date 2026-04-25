// Phase 21.5 — static content surfaced by <TabGuide tab="…"/>.
//
// Each guide answers four questions a brand-new user asks the first
// time they open the screen:
//   1. What is this for?
//   2. What's the 3-step path?
//   3. Which Python node does the work, in case I want to script it?
//   4. What gets cached, and where does the audit trail live?
//
// Keep entries short — the goal is to remove ambiguity, not to write
// a manual. The full per-screen documentation lives under docs/.

export type TabGuideId =
  | "quickstart"
  | "analyse"
  | "slides"
  | "datasets"
  | "train"
  | "cohorts"
  | "annotate"
  | "models"
  | "runs"
  | "audit"
  | "pipelines"
  | "settings";

export type TabGuideEntry = {
  title: string;
  purpose: string;
  steps: readonly string[];
  pythonNode?: string;
  cachedAndAudited?: string;
  docsHref?: string;
  docsLabel?: string;
};

export const TAB_GUIDES: Record<TabGuideId, TabGuideEntry> = {
  quickstart: {
    title: "Quickstart",
    purpose:
      "Pick a template and the wizard walks you through your first end-to-end run — HF token (optional) → dataset download → train → explain. Two templates ship today: DINOv2 + Kather-CRC-5K (open) and YOLOv26 + Kather-CRC-5K (with graceful fallback to YOLOv8).",
    steps: [
      "Pick the DINOv2 or YOLO template (you can switch anytime).",
      "Run each step — the wizard tells you what *you* do vs what *it* does, and where artifacts land on disk.",
      "When the train step finishes, hop to Analyse to drop a tile and read the explanation.",
    ],
    pythonNode: "openpathai.data.downloaders + openpathai.training.node.train",
    cachedAndAudited:
      "Datasets land at $OPENPATHAI_HOME/datasets/<name>/, model weights at $OPENPATHAI_HOME/models/, checkpoints at $OPENPATHAI_HOME/checkpoints/<run_id>/. Wizard state persists in localStorage so a refresh resumes mid-flow.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/quickstart.md",
    docsLabel: "Quickstart docs",
  },
  analyse: {
    title: "Analyse",
    purpose:
      "Drop a single tile, pick a model, and get a top-k prediction with a Grad-CAM / IG / attention heatmap overlay. Use this for one-shot reads — for batch scoring, build a pipeline.",
    steps: [
      "Pick a model from the dropdown (synthetic backbones work without HF; foundation models need a token).",
      "Drag-drop a tile or paste a base64 image; pick an explainer (Grad-CAM is the safe default).",
      "Read the predicted class, confidence, borderline flag, and overlay. The result is also written to the audit log.",
    ],
    pythonNode: "openpathai.analyse.classify_tile (FastAPI: POST /v1/analyse/tile)",
    cachedAndAudited:
      "Predictions are content-addressed by sha256(image, model_id) and written to the audit DB with the resolved model name + any fallback reason.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/phase-20.5-canvas-task-surfaces.md",
    docsLabel: "Phase 20.5 spec",
  },

  slides: {
    title: "Slides",
    purpose:
      "Upload a whole-slide image, view it pyramid-style with OpenSeadragon, and overlay heatmaps. The DZI generator caps the base level at 8192 px on the longer axis so multi-gigapixel WSIs still render on a laptop.",
    steps: [
      "Drop a slide (.tif / .svs / .ndpi / .mrxs / .scn / OpenSlide-supported). Real WSIs are downsampled to fit memory; native dimensions are preserved in the metadata.",
      "Click into the slide to open the viewer. Pan / zoom with the mouse; the viewer fetches DZI tiles as you move.",
      "Optionally compute a heatmap overlay (Phase-21 deterministic palette today; real per-tile inference is parked).",
    ],
    pythonNode:
      "openpathai.io.wsi.open_slide → openpathai.server.dzi.generate (POST /v1/slides, GET /v1/slides/{id}.dzi)",
    cachedAndAudited:
      "Slide bytes are content-addressed; DZI pyramids cache under $OPENPATHAI_HOME/dzi/. Bearer token can ride on the URL via ?token= for OSD tile fetches.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/phase-21-openseadragon-viewer.md",
    docsLabel: "Phase 21 spec",
  },

  datasets: {
    title: "Datasets",
    purpose:
      "Browse YAML-carded datasets and register new ones. Cards capture license, classes, modality, citation — Iron Rule #10 (every model has a card) extends to datasets.",
    steps: [
      "Pick a built-in dataset (LC25000, Kather-CRC-5K, HISTAI-*) or use Register folder to point at a local directory.",
      "Set tissue, classes, license; the card YAML is written under data/datasets/.",
      "The dataset id is now usable from Train, Cohorts, and any pipeline node that takes a dataset reference.",
    ],
    pythonNode:
      "openpathai.data.registry.register_folder + DatasetCard pydantic model",
    cachedAndAudited:
      "Card YAMLs ship in-tree; local datasets are referenced by absolute path with a content hash for reproducibility.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/phase-07-safety-and-local-datasets.md",
    docsLabel: "Phase 7 spec",
  },

  train: {
    title: "Train",
    purpose:
      "Launch a Lightning training run on a registered dataset + model. Synthetic mode runs end-to-end with no dataset on disk — useful for smoke-testing the pipeline before committing GPU time.",
    steps: [
      "Pick dataset + model + duration preset (Quick / Standard / Thorough). Toggle synthetic if you just want a green run.",
      "Click Launch. Epoch metrics stream into the chart; the best checkpoint is kept under $OPENPATHAI_HOME/checkpoints/.",
      "When the run finishes, jump to Runs → click the row → Run-audit modal shows the manifest, signature, and cache hits.",
    ],
    pythonNode: "openpathai.training.node.train (op id: training.train)",
    cachedAndAudited:
      "Train batches are content-hashed; runs land in the SQLite audit DB with the full manifest, signed in diagnostic mode.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/phase-03-model-zoo-training.md",
    docsLabel: "Phase 3 spec",
  },

  cohorts: {
    title: "Cohorts",
    purpose:
      "Group slides into named cohorts for QC, training, or reporting. Patient-level CV splits are enforced by the underlying split helper (Iron Rule #4).",
    steps: [
      "Create a cohort, drop slides into it (drag from Slides or paste slide ids).",
      "Run QC — every slide gets a pass / warn / fail and a stain-normalised reference panel.",
      "Export the QC report as HTML / PDF, or pipe the cohort id into Train.",
    ],
    pythonNode:
      "openpathai.data.cohort.CohortTileDataset + openpathai.qc.cohort_report",
    cachedAndAudited:
      "Cohort manifests + QC reports are signed in diagnostic mode; HTML/PDF exports include the cohort hash in the footer.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/phase-09-cohorts-qc-train-driver.md",
    docsLabel: "Phase 9 spec",
  },

  annotate: {
    title: "Annotate",
    purpose:
      "Tile-level correction loop: predict, correct, retrain. The screen surfaces low-confidence tiles for the active-learning acquirer (Bet 1).",
    steps: [
      "Run inference on a slide → uncertainty-ranked tiles surface here.",
      "Confirm or correct each tile's class. MedSAM2-assisted polygon mode is available for segmentation tasks.",
      "Submit corrections — the next training iteration uses them as the new acquired pool.",
    ],
    pythonNode:
      "openpathai.active_learning.acquire + openpathai.annotation.write_corrections",
    cachedAndAudited:
      "Each correction is written with annotator id + timestamp into the audit DB. Iron Rule #9 — never auto-execute LLM-generated annotations.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/phase-16-annotate-gui.md",
    docsLabel: "Phase 16 spec",
  },

  models: {
    title: "Models",
    purpose:
      "Browse the model zoo. Every entry has a YAML card with license, citation, training data, and tier compatibility. Gated models (UNI, CONCH, Virchow, Prov-GigaPath) need a Hugging Face token configured under Settings.",
    steps: [
      "Filter by tier (Easy / Standard / Expert) or modality (classifier / detector / segmenter / foundation).",
      "Click into a card to see input size, embedding dim, license, and citation.",
      "If gated, follow the HF link to request access; once granted, paste the token in Settings.",
    ],
    pythonNode: "openpathai.models.registry.default_model_registry()",
    cachedAndAudited:
      "Cards live in models/zoo/. Resolved model id (and any fallback) is recorded on every Analyse / Train run.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/phase-13-foundation-mil.md",
    docsLabel: "Phase 13 spec",
  },

  runs: {
    title: "Runs",
    purpose:
      "Live and historical pipeline runs. Polls the backend every two seconds while you watch — once a run lands, click in for the manifest + signature + cache stats.",
    steps: [
      "Find a run by status pill (queued / running / success / error).",
      "Click the row to open the manifest viewer.",
      "Click Audit to open the full run-audit modal (signed manifest, cache hits, analyses).",
    ],
    pythonNode: "openpathai.server.routes.runs (GET /v1/runs)",
    cachedAndAudited:
      "Every run produces a JSON manifest validated against the schema; diagnostic-mode runs are sigstore-signed.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/phase-19-fastapi-backend.md",
    docsLabel: "Phase 19 spec",
  },

  audit: {
    title: "Audit",
    purpose:
      "SQLite-backed run history. PHI is never written here — filenames are hashed on entry. Use this to diff two runs or to chase a specific analysis result back to its source.",
    steps: [
      "Browse the latest 100 runs (paged).",
      "Click an entry to inspect the redacted payload + metrics.",
      "Use openpathai diff <run_a> <run_b> from the CLI for a structural comparison.",
    ],
    pythonNode: "openpathai.audit.AuditDB + openpathai diff CLI",
    cachedAndAudited:
      "Backing store: $OPENPATHAI_HOME/audit.sqlite. Iron Rule #8 — no PHI in plaintext; deletion is keyring-gated.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/phase-08-audit-history-diff.md",
    docsLabel: "Phase 8 spec",
  },

  pipelines: {
    title: "Pipelines",
    purpose:
      "Power-user surface. Compose typed nodes into a DAG, validate, save, run. Every node is a Python function decorated with @openpathai.node — the canvas is just a thin shell over the registry exposed by GET /v1/nodes.",
    steps: [
      "Drag a node from the palette on the left, or pick a starter from the toolbar.",
      "Wire outputs to inputs by dragging from one handle to another. Edit per-node fields in the Inspector on the right.",
      "Validate → Save → Run. Runs land in the Runs tab and the audit DB with the graph hash.",
    ],
    pythonNode: "openpathai.pipeline (REGISTRY + @node decorator)",
    cachedAndAudited:
      "Each node's output is content-addressed by sha256(node_id + code_hash + input_config + input_artifact_hashes). Cache lives at ~/.openpathai/cache/.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/phase-20-react-canvas.md",
    docsLabel: "Phase 20 spec",
  },

  settings: {
    title: "Settings",
    purpose:
      "Per-tab configuration: API base URL + bearer token live here, plus version info and (after Phase 21.5/C lands) the Hugging Face token.",
    steps: [
      "Verify the API base URL points at your running openpathai serve instance.",
      "Bearer token is held in this tab's session memory only — closing the tab clears it.",
      "Version info confirms which build the canvas is talking to.",
    ],
    pythonNode: "openpathai.server.app + openpathai.server.routes.health",
    cachedAndAudited:
      "Tokens are never sent to localStorage. Bearer is sessionStorage-only; HF token (Phase-21.5/C) will live in $OPENPATHAI_HOME/secrets.json with mode 0600.",
    docsHref:
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/setup/huggingface.md",
    docsLabel: "HF setup guide",
  },
};
