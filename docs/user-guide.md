# User guide

A top-level tour of the CLI surface + the GUI tabs. Every
feature has a per-phase deep-dive page under the **Deep Dives**
nav section; this page is the guided entry point.

---

## CLI at a glance

Every CLI command is `openpathai <group> [subcommand] [options]`.
Full reference: [`cli.md`](cli.md).

### Core training loop

```bash
openpathai download <dataset>              # fetch + register a dataset
openpathai datasets list                   # registered datasets
openpathai models list                     # registered models (with safety-contract check)
openpathai train --dataset <d> --model <m> --epochs <n>
openpathai analyse <tile> --model <m> --explainer gradcam --pdf <out>
openpathai run <pipeline.yaml>             # full pipeline
```

### Cohorts + WSI

```bash
openpathai cohort build <dir>
openpathai cohort qc <cohort.yaml> --pdf <out>
openpathai train --cohort <cohort.yaml> --class-name A --class-name B
openpathai run <pipeline.yaml> --workers 4 --parallel-mode thread
```

### Foundation backbones + MIL + linear probe

```bash
openpathai foundation list                 # 8 registered backbones
openpathai foundation resolve uni          # FallbackDecision JSON
openpathai mil list
openpathai linear-probe --features <npz> --backbone <id> --out <json>
```

### Detection + segmentation

```bash
openpathai detection list
openpathai detection resolve yolov26       # → synthetic_blob fallback
openpathai segmentation list
openpathai segmentation resolve medsam2    # → synthetic_click fallback
```

### Active learning

```bash
openpathai active-learn --pool <pool.csv> --out <dir> \
    --iterations 3 --budget 8 --sampler hybrid
```

### Natural-language + zero-shot (Phase 15 + 17)

```bash
openpathai llm status                      # probe Ollama / LM Studio
openpathai nl classify <tile> --prompt tumor --prompt normal
openpathai nl segment  <tile> --prompt "gland region" --out <mask.png>
openpathai nl draft    "fine-tune resnet18 on lc25000 for 2 epochs"
openpathai methods write <manifest.json> --out <methods.md>
```

### Reproducibility

```bash
openpathai manifest sign   <manifest.json>    # Ed25519 signature
openpathai manifest verify <manifest.json>    # round-trip check
openpathai diff    <run_a> <run_b>            # audit-DB run diff
openpathai export-colab --pipeline <y.yaml> --out <run.ipynb>
openpathai sync    <manifest.json>            # import a Colab manifest
```

### Housekeeping

```bash
openpathai cache show / clear / invalidate
openpathai audit init / status / list / show / delete
openpathai gui                                # Gradio GUI
openpathai mlflow-ui                          # MLflow UI
```

---

## GUI at a glance

`openpathai gui` → http://127.0.0.1:7860 → nine tabs:

| Tab | What it does |
| --- | --- |
| **Analyse** | Upload a tile, pick a model + explainer, get a calibrated prediction + heatmap + PDF report. Phase-15 zero-shot accordion underneath for text-prompt classification. |
| **Pipelines** | List shipped pipeline YAMLs + a MedGemma-draft chat accordion ("describe what you want" → drafted YAML). |
| **Datasets** | Browse registered datasets (shipped + local), filter by tissue / modality / tier, add a local folder via `register_folder`. |
| **Train** | Train the Tier-A models on a synthetic batch, a registered dataset, or a cohort. Shows per-epoch train / val loss + ECE + macro-F1. |
| **Models** | Safety-contract overview of every model card (training data, intended use, known biases). Issues column flags cards missing required fields. |
| **Runs** | SQLite-backed run history. Click any row for the full manifest JSON + a Colab-export accordion + a "Delete run" confirmation (keyring-gated). |
| **Cohorts** | Load a cohort YAML, run QC, export a summary HTML / PDF. Paths are PHI-redacted in the table. |
| **Annotate** | Pool-CSV + annotator-id session → uncertainty-ranked tile queue → record/skip → one-click retrain → ECE delta. Click-to-segment preview via MedSAM2 fallback. |
| **Settings** | Cache info + clear, audit-DB status + toggle, keyring delete token (Phase 8). |

---

## Common workflows

### "I want to train a classifier on my local tiles"

1. Run `openpathai datasets register` on your tile directory
   (CLI or GUI Datasets → Add local).
2. `openpathai train --dataset <your-id> --model resnet18 --epochs 5`.
3. Open the GUI Runs tab to inspect the run + download the PDF
   report.

### "I want a reproducible paper run"

1. Pin every model card's `source.revision` field.
2. Set `mode: diagnostic` in your pipeline YAML.
3. `openpathai run <pipeline.yaml>` — refuses unless the git
   tree is clean + revisions are pinned + sigstore keypair is
   ready.
4. `openpathai methods write <manifest.json>` — MedGemma writes
   a Methods paragraph that cites only what's in the manifest.
5. Publish the manifest + signature together; any reviewer
   can `openpathai manifest verify` without needing your keypair.

### "I want to annotate an active-learning pool"

1. Export a CSV with `tile_id,label` from your pool.
2. GUI → Annotate tab → fill in paths + your name → Start.
3. Correct each tile; press **R** to retrain when you've
   labelled enough for the ECE to move.
4. The corrections CSV is append-only; merge multiple
   annotators post-hoc.

### "I don't have a GPU; what can I still do?"

Everything except the torch-training paths:

- CLI: `foundation list / resolve`, `mil list`, `detection list`,
  `segmentation list`, `nl classify` (fallback text encoder),
  `active-learn` (synthetic trainer), `manifest sign / verify`,
  `methods write`.
- GUI: every tab loads; `Train` requires the `[train]` extra,
  the rest work without torch.

---

## PHI safety (iron rule #8)

OpenPathAI's audit layer never persists raw filesystem paths
or patient identifiers:

- File paths hash to basenames only.
- NL prompts are stored as `prompt_hash` (SHA-256, 16 hex).
- Cohort-tab slide paths are rendered as `<basename>#<parent-
  hash>` so two slides from the same directory collate
  without leaking the directory itself.

When you write your own `@node`, the Phase-7
`safety.audit.phi` helpers apply automatically — or call
`strip_phi(params)` yourself before logging anything.

---

## When something fails

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: torch` | `[train]` extra not installed | `pipx install "openpathai[train]"` |
| `openpathai gui` → exit 3 | `[gui]` extra not installed | `pipx install "openpathai[gui]"` |
| `openpathai nl draft` → exit 3 | Ollama / LM Studio not running | Follow [`setup/llm-backend.md`](setup/llm-backend.md) |
| `openpathai foundation resolve uni` → `reason: hf_token_missing` | HF access not configured | See [`setup/huggingface.md`](setup/huggingface.md); fallback to DINOv2 is automatic |
| `PipelineYamlError` | YAML schema mismatch | The error message names the offending field; check `docs/cli.md` for the `Pipeline` schema |
| Windows `PermissionError: [WinError 5]` | Cache rename race | Fixed in commit `370a5fb`; update to latest |

More answers: [`faq.md`](faq.md).
