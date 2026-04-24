# CLI reference

Phase 5 ships a single entry point — `openpathai` — that wraps every
capability landed in Phases 1–4. Every subcommand is a thin veneer
over a library function, so anything you can do from the shell you can
also do from Python.

```bash
uv run openpathai --help
```

## Subcommands

### `openpathai hello`

Phase 0 smoke command — prints a liveness message. Handy for
verifying that the CLI installation works end-to-end.

### `openpathai models list [--family FAMILY] [--framework FRAMEWORK] [--tier TIER]`

Lists every model card under `models/zoo/` (shipped) plus any in
`~/.openpathai/models/` (user overrides).

```bash
uv run openpathai models list --family vit
```

### `openpathai datasets list [--modality M] [--tissue T] [--tier TIER]`

Lists every dataset card with its size + gated status.

### `openpathai datasets show NAME`

Prints the full YAML card to stdout, including the download
instructions and partial-download hints.

### `openpathai download NAME [--yes] [--subset N] [--root DIR]`

Stages a dataset under `~/.openpathai/datasets/NAME/`. Without
`--yes`, the command prints the size warning and the gated-access
instructions and exits with code 2, so no large transfer ever starts
by accident. `--subset N` triggers a POC-sized fetch when the backend
supports allow-list globs (primarily Hugging Face).

### `openpathai cache show | clear | invalidate KEY`

Inspect and prune the Phase 1 content-addressable cache.

```bash
uv run openpathai cache show
uv run openpathai cache clear --older-than-days 30
uv run openpathai cache invalidate abcd1234...
```

### `openpathai run PIPELINE.yaml [--output-dir DIR]`

Parses a pipeline YAML (`openpathai.cli.pipeline_yaml.load_pipeline`)
and executes it via the Phase 1 executor. The run manifest + a
per-step artifact summary land under `DIR/` (defaults to
`./runs/<uuid>/`).

```bash
uv run openpathai run pipelines/supervised_synthetic.yaml
```

### `openpathai train --model MODEL --num-classes N [options] [--synthetic]`

Tier-A supervised training. Phase 3 wired the `--synthetic` path
end-to-end; real-cohort training lands alongside Phase 9.

### `openpathai analyse --tile PATH --model MODEL [--target-layer LAYER] [--explainer KIND]`

Runs an inference + explainability pass on a single tile and writes a
heatmap PNG + overlay. Requires the `[train]` extra (torch + timm).

```bash
uv run openpathai analyse \\
    --tile tile.png --model resnet18 --num-classes 4 \\
    --explainer gradcam --target-layer layer4
```

### `openpathai export-colab --out PATH [--pipeline YAML] [--run-id ID]` (Phase 11)

Render a self-contained Colab reproduction notebook for a pipeline.
See [Colab export + sync](colab.md) for the round-trip.

```bash
uv run openpathai export-colab \\
    --pipeline pipelines/supervised_synthetic.yaml \\
    --out /tmp/demo.ipynb

# With lineage back to a specific local audit row:
uv run openpathai export-colab \\
    --pipeline pipelines/supervised_synthetic.yaml \\
    --run-id run-abcdef012345 \\
    --out /tmp/demo.ipynb
```

### `openpathai sync MANIFEST_PATH [--show]` (Phase 11)

Import a `RunManifest` JSON (usually downloaded from Colab) into the
local audit DB. `--show` prints the audit-row shape without writing.
Idempotent on re-import.

```bash
uv run openpathai sync ~/Downloads/manifest.json --show
uv run openpathai sync ~/Downloads/manifest.json
```

### `openpathai active-learn --pool CSV --out DIR […]` (Phase 12)

Run a simulated-oracle active-learning loop on a two-column
`tile_id,label` CSV. See [Active learning](active-learning.md) for
the full walkthrough; core flags:

| Flag | Default | Meaning |
| --- | --- | --- |
| `--pool` | *(required)* | Pool CSV (also serves as the oracle). |
| `--out` | *(required)* | Output dir for `manifest.json` + `corrections.csv`. |
| `--scorer` | `max_softmax` | `max_softmax` \| `entropy` \| `mc_dropout`. |
| `--sampler` | `uncertainty` | `uncertainty` \| `diversity` \| `hybrid`. |
| `--iterations`, `--budget`, `--seed-size` | `3, 8, 12` | Loop sizing. |
| `--annotator-id`, `--seed` | `simulated-oracle, 1234` | Logged on every correction. |

```bash
uv run openpathai active-learn \\
    --pool   /tmp/pool.csv \\
    --out    /tmp/al-run \\
    --iterations 3 --budget 8 --seed-size 12 \\
    --sampler hybrid
```

### `openpathai foundation list | resolve <id>` (Phase 13)

List registered foundation backbones or ask the fallback resolver
what would actually load for a given id. See
[Foundation models](foundation-models.md) for the full surface.

```bash
uv run openpathai foundation list
uv run openpathai foundation resolve uni          # JSON FallbackDecision
uv run openpathai foundation resolve uni --strict # hard-fail mode
```

### `openpathai mil list` (Phase 13)

Prints shipped vs stub MIL aggregators
([ABMIL, CLAM-SB, stubs: CLAM-MB / TransMIL / DSMIL]). See
[MIL](mil.md) for the library surface.

### `openpathai linear-probe --features <npz> --backbone <id>` (Phase 13)

Fits a linear probe on a pre-extracted feature bundle (`.npz` with
`features_train` + `labels_train` + `class_names`). Writes a
`LinearProbeReport` JSON and inserts one audit row carrying
`backbone_id` / `resolved_backbone_id` / `fallback_reason`.

```bash
uv run openpathai linear-probe \\
    --features /tmp/features.npz \\
    --backbone dinov2_vits14 \\
    --out      /tmp/probe.json
```

## Pipeline YAML format

See [`pipelines/README.md`](https://github.com/atultiwari/OpenPathAI/blob/main/pipelines/README.md)
for the shape. A minimal reference ships as
[`pipelines/supervised_synthetic.yaml`](https://github.com/atultiwari/OpenPathAI/blob/main/pipelines/supervised_synthetic.yaml).

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generic failure (e.g. `cache invalidate` on a missing key) |
| 2 | User error — missing required flag, unknown dataset/model, unconfirmed large download |
| 3 | Missing optional backend (install via the relevant extra) |
| 4 | Feature not implemented yet (e.g. Zenodo download — lands in Phase 9) |
