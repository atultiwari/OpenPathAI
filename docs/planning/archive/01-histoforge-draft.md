# HistoForge — Project Plan

**Status:** Draft v0.1
**Owner:** Dr Atul Tiwari, Vedant Research Labs
**Last updated:** 23 April 2026

---

## 1. Product thesis

HistoForge is a **reproducible, auditable, compute-tier-aware workflow environment for computational pathology research**.

It serves three audiences with one codebase:

1. **Pathologist-researcher** — composes pipelines (eventually visually) for exploratory WSI analysis without writing code.
2. **ML engineer** — runs the *same* pipelines headlessly at scale for training, benchmarking, and batch inference.
3. **Regulatory reviewer (future)** — inspects exactly what happened on any given run, down to model hashes and parameter values.

Inspiration is drawn from Karkinos' Path IDE (NGP platform), Aiforia Create, QuPath, and tiatoolbox — but HistoForge is deliberately *not* a clone. Its distinctive bets are listed in §3.

### 1.1 Non-goals (deliberate)

- **No diagnostic claims.** Exploratory / research framing only until a clear CDSCO SaMD path exists.
- **No multi-tenant SaaS.** Self-hosted first; cloud deployment is a later choice, not a design constraint.
- **No real-time collaboration (Figma-style).** Enormous engineering cost, marginal user value.
- **No in-UI deep learning training from scratch.** UI-driven training caps at logistic regression / MIL fine-tuning; serious training happens via the Python API.
- **No mobile app.**

---

## 2. Guiding principles

1. **Library-first, UI-last.** The v1 Python package is the foundation v2 and v3 are built *on top of*. Nothing gets rewritten across versions. Never put real logic inside a notebook cell.
2. **Compute-agnostic code, compute-aware execution.** Pipeline logic knows nothing about where it runs; the execution layer routes to the right tier.
3. **Free-tier by default.** v1 and v1.5 must be fully usable on a MacBook Air + free Colab. Paid tiers are optional accelerators, never requirements.
4. **Reproducibility is architecture, not a feature.** Content-addressable caching, full run manifests, and patient-level splits are baseline from day one.
5. **Open-source, AGPL-3.0.** Same license as originally scoped for HistoForge.
6. **Honest status labelling.** Every run is visibly tagged Exploratory vs Diagnostic; every model card shows its training data, license, and known biases.

---

## 3. HistoForge's three distinctive bets

These are the features that make HistoForge meaningfully different from Path IDE, tiatoolbox-with-scripts, or any other existing option. Everything else in the feature list is table stakes.

### Bet 1 — Active learning loop as first-class workflow

After initial training, the model highlights its most uncertain tiles; the pathologist corrects them; the model retrains on the corrections; repeat. This is Aiforia Create's strongest feature and is notably *absent* from Path IDE. If HistoForge does one thing better than any competitor, make it this.

### Bet 2 — Natural-language workflow construction and annotation

Leveraging CONCH (vision-language foundation model) and local LLMs (MedGemma, already in the stack):

- **"Highlight anything resembling tumor budding"** → heatmap without training, via CONCH zero-shot.
- **"Build me an exploratory pipeline for breast tissue at 20x with UMAP visualization"** → draft pipeline graph the user reviews and edits.
- **Auto-generated Methods sections** from run manifests for publication.

Path IDE is pre-LLM in its architectural assumptions. HistoForge is LLM-native.

### Bet 3 — Research-grade reproducibility and benchmarking built in

Not bolted on later. From v1:

- Content-addressable caching of every intermediate artifact.
- Full run manifest (pipeline hash, model hashes, slide hashes, code commit hash, environment) per run.
- Built-in benchmarks (LC25000, CAMELYON, PANDA, TCGA subsets) with patient-level splits by default.
- Copy-pasteable Methods text.

Path IDE has a run log. HistoForge has an audit trail.

---

## 4. Compute tier architecture

### 4.1 The three tiers

**Tier 1 — Local (MacBook / Windows)**

- Runs: WSI I/O, tissue masking, tiling, small-model inference (ViT-S with MPS), classical ML (sklearn), visualization, pipeline authoring, CONCH zero-shot at modest scale.
- Doesn't run: large foundation model inference at scale, MIL training, anything needing >16 GB VRAM.
- Optimization: aggressive caching so most exploratory work avoids recomputation. MPS acceleration where available.

**Tier 2 — Colab (free tier baseline)**

- Constraints: ~11 GB RAM, ~15 GB VRAM (T4 typically), 12-hour maximum runtime, GPU access can be throttled after heavy use.
- Runs: foundation model embedding (UNI, UNI2-h, Virchow2, CONCH, Prov-GigaPath), MIL model training on modest cohorts, clustering runs, LC25000 benchmark sweeps.
- Doesn't run: overnight training, multi-GPU, anything >12h.
- Deployment pattern: HistoForge generates a Colab notebook from a local pipeline YAML. Notebook mounts Google Drive, pulls pipeline config + cached inputs, runs the specified stages, writes results back to Drive.

**Tier 3 — RunPod / Lambda / institutional HPC (v2.5+, deferred)**

- Runs: overnight training, production-scale inference, A100/H100 workloads.
- Deployment pattern: pipeline packaged as Docker container, submitted as a job, results return via S3-compatible storage.
- **Explicitly deferred until there is a concrete workload that needs it.**

### 4.2 Handoff model

**Model A — Explicit handoff (chosen).** Pathologist builds pipeline locally, tags heavy nodes as Tier 2 or Tier 3, exports a deployment bundle, runs it on Colab/RunPod, pulls results back. Synchronous from the user's perspective, asynchronous under the hood. Boring. Always works.

**Model B — Transparent offload (rejected for v1–v3).** Silent routing of tier-tagged nodes to remote compute with invisible auth/data/results handling. Feels magical; painful when it breaks. Deferred to v4 or later.

Rationale: researchers *want* to see exactly what ran where — that's what they put in their Methods section.

### 4.3 Data management across tiers

| Data type | Size | Strategy |
|---|---|---|
| Pipeline definitions, configs | <1 MB | Git. Synced everywhere trivially. |
| Embeddings cache | 10 MB – 10 GB per cohort | Google Drive (Colab-native) or S3/R2 (RunPod). Keyed by content hash. Local `histoforge sync` command pulls what you need. |
| WSI files | 1 – 4 GB each | Don't move. Pipelines take URIs, not paths. Each tier reads from source or caches locally. For RunPod: mount network volume or use cuCIM for remote tile streaming. |

**The embeddings cache design is the single decision that makes the tier model usable.** Compute embeddings once on Colab, explore locally forever.

### 4.4 Environment management

Single `pyproject.toml` with optional dependencies per tier:

```
pip install histoforge[local]    # MPS, basic models
pip install histoforge[colab]    # + CUDA, foundation models
pip install histoforge[runpod]   # + flash-attention, MIL, heavy deps
```

One Dockerfile per tier, built in CI, tagged by HistoForge version.

Pipeline code imports conditionally: if a model is available, register it; if not, it's missing from the dropdown. Same pipeline YAML can reference UNI2-h — on Tier 1 it errors clearly ("Model requires Tier 2+"); on Tier 2 it runs.

---

## 5. Feature inventory

Features are tagged:

- **[C]** = Core (v1 / v2 must have)
- **[T]** = Target (v3)
- **[S]** = Stretch (post-v3 if signal is good)

Each feature also has a tier compatibility note where relevant: T1 (local), T2 (Colab), T3 (RunPod).

### 5.1 Pipeline composition

- **[C]** Typed node graph with validation. Every node declares I/O types via pydantic. Invalid connections impossible.
- **[C]** Supervised workflow mode (`in → stain → mask → tile → emb → clf → heat`).
- **[C]** SSL-exploratory workflow mode (`in → stain → mask → tile → ssl → clust → chm → cl2l → clabel`).
- **[T]** Prompt-based / zero-shot mode via CONCH ("show me regions resembling X"). **Bet 2.**
- **[T]** Sub-graphs / reusable pipeline fragments.
- **[C]** Version-controlled pipelines (git, not fake version numbers).

### 5.2 Data & slide management

- **[C]** Multi-scanner WSI support (Aperio, Hamamatsu, 3DHistech, Philips, Leica, DICOM WSI) via tiatoolbox + OpenSlide.
- **[C]** Slide cohorts — group slides by project, stain, tissue, scanner. Pipelines run over cohorts, not individual slides.
- **[T]** Automatic metadata extraction (scanner, MPP, stain type, ICC profile) shown inline.
- **[T]** QC gate on ingestion: blur, pen marks, tissue folds, out-of-focus regions flagged before pipeline runs.

### 5.3 Annotation & labeling

- **[C]** Polygon, region, brush, point annotations.
- **[C]** Class taxonomy management with hierarchies (e.g., Epithelium → Normal / Dysplastic / Malignant).
- **[C]** Annotation import/export: GeoJSON, QuPath .geojson, ASAP XML, COCO.
- **[T]** **Active learning loop — Bet 1.** Uncertainty-ranked tiles, pathologist corrects, model retrains, repeat.
- **[S]** Inter-annotator agreement tooling (Cohen's kappa, Dice).

### 5.4 Models & embeddings

- **[C]** Pluggable embedding registry: UNI, UNI2-h, Virchow2, CONCH, Prov-GigaPath, Hibou, DINO, DINOv2, CTransPath, any timm ViT.
- **[C]** Embedding caching keyed by `(slide_id, tile_coords, model_id, preprocessing_hash)`. Never recompute. **Biggest performance win available.**
- **[C]** Tier compatibility metadata on every model (VRAM, CUDA/MPS/CPU support, expected tile size, magnification).
- **[T]** Model zoo with provenance cards: architecture, training data, license, known tissue biases, benchmark scores.
- **[T]** On-device inference: MPS/CoreML for Mac, CUDA for everything else. Clean abstraction.
- **[S]** Fine-tuning / LoRA adaptation (FEATHER-style lightweight heads look promising).

### 5.5 Classifiers & aggregation

- **[C]** Tile-level classifiers: logistic regression, SVM, gradient boosting, small MLP.
- **[T]** MIL aggregation for slide-level labels: CLAM, TransMIL, ABMIL. **This is SOTA for WSI classification and Path IDE doesn't expose it.**
- **[T]** Calibration & uncertainty: conformal prediction or temperature scaling. Heatmaps show confidence, not raw scores.
- **[S]** Multi-task heads (tumor y/n + grade + subtype in one embedding pass).

### 5.6 Clustering & discovery

- **[C]** K-means, DBSCAN, HDBSCAN, hierarchical, Leiden. (HDBSCAN and Leiden are missing from Path IDE and genuinely better for tissue discovery.)
- **[C]** UMAP / t-SNE visualization of clusters. Clickable points → source tile display.
- **[T]** Cluster validation (silhouette, Davies-Bouldin, stability across slides).
- **[S]** Phenotype discovery reports — auto-generated narrative summaries via local LLM.

### 5.7 Reproducibility, provenance, audit

- **[C]** Content-addressable caching. Every intermediate artifact keyed by hash of (inputs + code + config).
- **[C]** Full run manifest per run: pipeline graph hash, all parameter values, model hashes, input slide hashes, code commit hash, environment, timestamps, outputs. JSON/YAML.
- **[C]** Exploratory vs Diagnostic mode flags enforced architecturally. Diagnostic mode requires signed pipelines, version-pinned models, audit logs. Exploratory mode is permissive.
- **[T]** Diff two runs — visual diff of pipeline graphs and parameters.
- **[S]** Signed, immutable run records with hash-chained logs.

### 5.8 Evaluation & benchmarking

- **[C]** Built-in benchmarks: LC25000, CAMELYON16/17, PANDA, TCGA subsets. One command runs your pipeline against them.
- **[C]** Metrics dashboard: AUC, accuracy, F1, Dice (for segmentation), slide-level and tile-level breakouts.
- **[C]** Cross-validation framework with **patient-level splits by default**, stratified by site/scanner. (Tile-level splits are the classic beginner mistake.)
- **[T]** Statistical comparison: DeLong for AUC differences, bootstrap CIs.
- **[S]** Community benchmark leaderboard.

### 5.9 Output & integration

- **[C]** Heatmap output as GeoTIFF / DZI. Works in any OpenSeadragon viewer.
- **[C]** Annotation export to QuPath, ASAP, Slim Viewer.
- **[C]** Programmatic API — everything the UI does, the CLI / Python API does. No UI-only features. Ever.
- **[T]** DICOM-SR structured reporting output. (Regulatory future direction.)
- **[S]** DICOM-WSI output for processed slides.

### 5.10 UI & UX

- **[T]** React Flow canvas (v3).
- **[T]** Live thumbnail preview per node.
- **[T]** Inline documentation per node parameter (hover → description, recommended values, citations).
- **[C]** Pathologist-tuned defaults even in v1 CLI (Macenko reference slides per tissue, tile sizes per magnification, recommended models per tissue type).
- **[C]** Dark mode + high-contrast from day one.
- **[T]** Keyboard-first navigation.

### 5.11 Collaboration

- **[T]** Multi-user pipeline sharing (pipeline = YAML file, URL, or git repo).
- **[S]** Pipeline marketplace / community library.
- **[S]** Comments and review workflow.

### 5.12 AI-native features (Bet 2 expansion)

- **[T]** Natural-language pipeline construction via local LLM.
- **[T]** Natural-language annotation via CONCH zero-shot.
- **[T]** Auto-generated Methods sections from run manifests.
- **[S]** Intelligent parameter suggestion based on similar prior runs.

---

## 6. Version roadmap

### v1 — Library + notebook driver

**Goal:** a clean, importable Python package with every pipeline primitive working end-to-end on one slide, driven by a Jupyter notebook. All Tier 1.

**Deliverables:**

- `histoforge/` Python package (see §7 for structure).
- Typed node interfaces (pydantic) for every primitive.
- YAML pipeline config schema.
- Content-addressable cache (filesystem).
- Jupyter notebook demonstrating supervised and SSL-exploratory pipelines on one slide.
- Pathologist-tuned defaults for H&E breast, GI, derm tissue types.
- Unit tests covering the cache, the type system, and each primitive.
- Published to GitHub, AGPL-3.0, with README + CONTRIBUTING.

**Explicit non-goals for v1:** CLI, Snakemake, Colab export, active learning, CONCH zero-shot, UI of any kind.

**Success criterion:** I can open the notebook on my MacBook Air, point it at a TCGA slide, run the exploratory pipeline, and see a cluster heatmap. Then change one parameter and rerun — the cached stages should skip.

### v1.5 — Evaluation harness + Colab export

**Goal:** benchmark the v1 pipeline on LC25000 (and a small TCGA subset) reproducibly, using Colab free tier for the foundation model embedding step.

**Deliverables:**

- `histoforge.benchmarks` module with LC25000 loader (patient-level splits) and metrics dashboard.
- `histoforge export-colab` command that generates a Colab notebook pinned to the current pipeline config.
- Embedding cache sync to/from Google Drive.
- Tier compatibility metadata on every model in the embedding registry.
- Cross-validation framework.
- Benchmark run comparing at least three embedding models (UNI2-h, Virchow2 if access granted, DINOv2 as open baseline) on LC25000.

**Explicit non-goals for v1.5:** RunPod, MIL, CONCH, UI.

**Success criterion:** I can run a full LC25000 benchmark overnight using Colab free tier, get a results JSON back to my laptop, and the whole thing is reproducible from a single config file.

### v2 — CLI + pipeline orchestration

**Goal:** stop using notebooks as the driver. Proper CLI, Snakemake DAG, MLflow experiment tracking. Still no UI.

**Deliverables:**

- `histoforge run` CLI using Typer.
- Snakemake rules for every pipeline stage, with content-addressable caching for free.
- MLflow integration for experiment tracking.
- Full run manifest generation.
- Parallel slide processing across a cohort.
- Active learning loop prototype (CLI-driven — the UI version comes in v3). **Bet 1 begins.**
- MIL aggregation (CLAM first, TransMIL second). **Path IDE gap.**
- Calibration & uncertainty on classifier outputs.

**Explicit non-goals for v2:** canvas UI, RunPod (unless a concrete need appears), CONCH zero-shot.

**Success criterion:** I can run a benchmark across a 100-slide TCGA cohort with one CLI command, with parallel execution, full audit trail, and nothing recomputed that was already cached.

### v2.5 — RunPod tier (conditional)

**Trigger to start:** a concrete workload that actually needs >12h GPU time or A100/H100 hardware. Until then, skip.

**Deliverables if triggered:**

- Docker image per tier.
- `histoforge submit-runpod` command.
- S3/R2-compatible results storage.
- Cost tracking per run.

### v3 — HistoForge canvas

**Goal:** the Path IDE-competitive visual pipeline builder.

**Deliverables:**

- FastAPI backend wrapping v2's pipeline engine.
- React + React Flow canvas frontend (matches Path IDE's nodes, minimap, live preview pattern).
- Node registry auto-derived from v1's pydantic schemas.
- OpenSeadragon WSI viewer with heatmap overlay alignment.
- Tier badges on nodes, cost tracking visible in UI.
- Run audit modal (like Path IDE's Image 10).
- Active learning UI loop. **Bet 1 completes.**
- Natural-language pipeline construction. **Bet 2 begins.**
- Auto-generated Methods section export.

**Explicit non-goals for v3:** multi-tenant hosting, real-time collaboration, mobile.

**Success criterion:** a pathologist who has never seen the codebase can drag-drop an SSL-exploratory pipeline, run it, view the overlay, and export a Methods paragraph — all in one session.

### v4 and beyond (speculative)

- Transparent tier offload (Model B).
- Pipeline marketplace.
- DICOM-SR / DICOM-WSI output.
- Multi-user pipeline sharing.
- CDSCO SaMD conversation (if clinical traction emerges).

---

## 7. Package architecture (v1)

Target layout, designed so v2 and v3 add thin layers without rewrites:

```
histoforge/
├── __init__.py
├── io/                    # WSI reading via tiatoolbox + OpenSlide
│   ├── wsi.py
│   └── cohort.py          # Cohort abstraction
├── preprocessing/
│   ├── stain.py           # Macenko, Reinhard, Vahadane
│   ├── mask.py            # Otsu + smarter variants
│   └── qc.py              # blur, pen marks, folds (v1.5+)
├── tiling/
│   └── tiler.py           # magnification-aware, stride-aware
├── embedding/
│   ├── registry.py        # plugin pattern for models
│   ├── timm_backbone.py   # any timm ViT
│   ├── uni.py             # UNI, UNI2-h
│   ├── virchow.py
│   ├── conch.py           # vision-language (Bet 2)
│   └── dinov2.py          # open baseline
├── classifier/
│   ├── sklearn_wrap.py    # logistic reg, SVM, GBM
│   └── mlp.py
├── clustering/
│   ├── kmeans.py
│   ├── hdbscan_wrap.py
│   └── leiden.py
├── heatmap/
│   ├── generator.py
│   └── overlay.py         # DZI / GeoTIFF output
├── cache/
│   └── content_addressable.py   # hash-based caching
├── pipeline/
│   ├── graph.py           # typed DAG
│   ├── schema.py          # pydantic I/O types
│   ├── executor.py        # walks the DAG, respects cache
│   └── manifest.py        # run manifest generation
├── benchmarks/            # v1.5
│   ├── lc25000.py
│   ├── camelyon.py
│   ├── panda.py
│   └── splits.py          # patient-level CV
├── config/
│   └── defaults.py        # pathologist-tuned defaults per tissue
└── ext/
    └── colab.py           # notebook export (v1.5)
```

Matching `tests/` layout mirrors this. Every module has a unit test file.

### 7.1 The node type system

Every pipeline primitive is a function with pydantic-typed inputs and outputs:

```python
class TilingInput(BaseModel):
    masked_slide: MaskedSlideArtifact
    tile_size_px: int = 256
    magnification: Literal["5X", "10X", "20X", "40X"] = "20X"
    stride_pct: float = 0.5

class TilingOutput(BaseModel):
    tiles: TileSetArtifact
    metadata: TilingMetadata

@histoforge.node(
    id="tiling.standard",
    tier_compatibility={"T1", "T2", "T3"},
)
def standard_tiler(cfg: TilingInput) -> TilingOutput:
    ...
```

The `@histoforge.node` decorator registers the function so v2's Snakemake and v3's canvas can both discover it. This is the single design decision that lets three versions coexist without rewrites.

### 7.2 The cache design

Key for any intermediate artifact:
```
sha256(function_id + code_hash + serialized_input_config + input_artifact_hashes)
```

Artifact storage: local filesystem in v1, pluggable backend (S3, R2, Google Drive) in v1.5+.

Cache hit = skip. Cache miss = compute + store. Invalidation = delete by key.

---

## 8. Dev environment & tooling

- Python 3.11.
- Package manager: `uv` (fast, and the direction the ecosystem is moving).
- Formatter + linter: `ruff`.
- Type checker: `pyright`.
- Test runner: `pytest` with coverage.
- Pre-commit hooks: ruff, pyright, pytest-on-changed-files.
- CI: GitHub Actions — test on macOS (ARM), Linux (x86). Windows best-effort.
- Docs: `mkdocs-material` from v1.
- Versioning: semver, released via GitHub Releases.
- License: AGPL-3.0 (consistent with earlier HistoForge scoping).

---

## 9. Dependencies (v1 core)

| Purpose | Library | Why |
|---|---|---|
| WSI I/O | `tiatoolbox`, `openslide-python` | Covers every major scanner format |
| Image ops | `numpy`, `pillow`, `opencv-python-headless` | Standard |
| ML backbone | `torch`, `timm`, `torchvision` | Foundation model ecosystem |
| Foundation models | `huggingface_hub` | UNI, CONCH, etc. (gated — requires institutional email) |
| Classical ML | `scikit-learn` | Logistic regression, clustering |
| Clustering extras | `hdbscan`, `leidenalg`, `umap-learn` | Beyond what Path IDE exposes |
| Config & types | `pydantic` v2 | Node I/O schemas |
| Caching | `joblib` (or custom) | Content-addressable artifacts |
| CLI (v2) | `typer` | Clean CLI |
| Orchestration (v2) | `snakemake` | De facto standard for research pipelines |
| Experiment tracking (v2) | `mlflow` | Open, self-hostable |
| Notebook export (v1.5) | `nbformat`, `papermill` | Colab integration |

**Foundation model access note:** UNI, UNI2-h, Virchow2, and CONCH are gated on Hugging Face. Approval requires a matching institutional email — your `vedantresearchlabs.com` domain qualifies; Gmail does not. Start the approval requests during v1 development so weights are available for v1.5 benchmarking. DINOv2 (open) is the fallback baseline that works without gated access.

---

## 10. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Colab throttles free-tier GPU access mid-benchmark | High | Medium | Save intermediate state every N slides; design benchmarks to be resumable. Document the pattern. |
| Foundation model gated access denied | Medium | High | DINOv2 as open baseline. Still publishable research. UNI2-h becomes a "nice to have" not a blocker. |
| WSI files too large for Google Drive free tier (15 GB) | High | Medium | WSIs stay local; only tile embeddings sync to Drive. This is already the v4.3 data strategy. |
| Environment parity (MPS vs CUDA behaviour differences) | Medium | Medium | CI tests on both. Explicit `@requires_cuda` decorator on stages that don't work on MPS. |
| Scope creep — trying to do v2 features in v1 | High | High | Feature freeze after CLAUDE.md finalisation. New ideas go to a v4+ backlog. |
| Conflict with PathAssist Phase 2 priority | Certain | Low | HistoForge v1 is ~2–3 weeks part-time, uses different muscles (image processing vs clinical NLP). Explicitly time-boxed. |
| Active learning loop (Bet 1) harder than estimated | Medium | Medium | Prototype CLI-first in v2 before committing to UI loop in v3. De-risked incrementally. |
| Natural-language features (Bet 2) unreliable | Medium | Low | Frame as "AI draft, human reviews" everywhere. Never auto-execute generated pipelines. |

---

## 11. Open questions to resolve before CLAUDE.md

These are genuine decisions, not rhetorical questions:

1. **Module granularity — one package or a monorepo of packages?** My recommendation: single package with clear submodules for v1; split into `histoforge-core`, `histoforge-ui`, `histoforge-server` if/when v3 happens.
2. **Pipeline config format — YAML or TOML?** My recommendation: YAML (more ecosystem tooling for pipelines, researchers read it easily).
3. **Should v1 include *any* CLI, even a minimal one, to avoid teaching bad notebook-driver habits?** My recommendation: yes, a one-command `histoforge run-demo` that executes the bundled demo pipeline. No more than that.
4. **Benchmark dataset storage — do we bundle small test fixtures or require download?** My recommendation: bundle 2–3 tiny tiles for unit tests; require download for real benchmarks.
5. **Documentation hosting — GitHub Pages or Read the Docs?** My recommendation: GitHub Pages via `mkdocs-material` gh-deploy (simpler CI).
6. **Issue tracker & project board — GitHub Projects or something else?** My recommendation: GitHub Projects, keeps everything in one place.

---

## 12. Next actions

1. **Atul reviews this plan** — flag anything wrong, missing, or scoped too aggressively. In particular: do the three Bets resonate, or would a different set of differentiators excite you more?
2. **Resolve open questions §11.**
3. **Start foundation model gated access requests** on Hugging Face (UNI2-h, CONCH, Virchow2) using `@vedantresearchlabs.com` email. These take days to weeks.
4. **Write `CLAUDE.md` for HistoForge v1** — translate §7 into the actionable spec Claude Code will work against. This is the next deliverable once the plan is locked.
5. **Create the GitHub repository** (private until v1.0, then flip to public AGPL-3.0).
6. **v1 build begins** in parallel with PathAssist Phase 2, time-boxed to 2–3 weeks of part-time effort.

---

*End of plan.*
