# Active learning (Phase 12)

> **Status:** v0.5 · CLI prototype · GUI lands in Phase 16.

OpenPathAI's active-learning loop turns a small pool of labelled
tiles + a larger pool of *unlabelled* tiles into a progressively
better classifier by asking an oracle to label only the tiles the
current model is least sure about. Phase 12 ships the loop as a
command-line tool with a **simulated oracle** — a CSV of ground-truth
labels the researcher exports ahead of time — so the entire flow
runs offline in seconds.

Phase 16 will swap the CSV oracle for a Gradio-based Annotate tab
where a pathologist corrects predictions interactively; the library
surface below is unchanged.

---

## The loop

```
[1] Train on a seed set     (openpathai active-learn --seed-size …)
[2] Score the unlabeled pool for uncertainty
[3] Pick the next batch     (--scorer + --sampler)
[4] Query the oracle        (--pool CSV rows double as truth)
[5] Fold corrections in → retrain
[6] Measure ECE on holdout  → emit audit row
[7] Repeat until --iterations exhausted
```

A final `manifest.json` captures every acquisition round, every
acquired tile id, ECE before/after, and accuracy-after — downstream
`openpathai diff` + GUI Runs tab see the AL iterations as normal
pipeline runs (their `metrics_json` carries the AL-specific fields).

---

## Running the loop

```bash
# 1. Prepare a two-column CSV: tile_id,label
#    (The same CSV serves as pool + ground-truth oracle.)
cat > /tmp/pool.csv <<'EOF'
tile_id,label
tile-0000,lung_aca
tile-0001,lung_n
tile-0002,lung_scc
# …
EOF

# 2. Run the loop.
openpathai active-learn \
    --pool /tmp/pool.csv \
    --out  /tmp/al-run \
    --iterations 3 \
    --budget 8 \
    --seed-size 12 \
    --scorer max_softmax \
    --sampler hybrid \
    --annotator-id simulated-oracle \
    --seed 1234
```

The command completes in seconds on any machine — no torch install is
required for Phase 12. Output:

```
/tmp/al-run/
├── manifest.json       ← ActiveLearningRun pydantic dump
└── corrections.csv     ← one row per acquired label
```

### Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `--pool` | *(required)* | Pool CSV — `tile_id,label` columns. |
| `--out` | *(required)* | Output directory (created if missing). |
| `--dataset`, `--model` | `synthetic`, `prototype-synthetic` | Free-text tags written to the manifest. |
| `--scorer` | `max_softmax` | `max_softmax` · `entropy` · `mc_dropout`. |
| `--sampler` | `uncertainty` | `uncertainty` · `diversity` · `hybrid`. |
| `--seed-size` | `12` | Number of seed-set examples. |
| `--budget` | `8` | New labels acquired per iteration. |
| `--iterations` | `3` | AL iterations to run. |
| `--holdout` | `0.25` | Fraction of the pool reserved for ECE evaluation. |
| `--annotator-id` | `simulated-oracle` | Logged on every correction row. |
| `--seed` | `1234` | Deterministic seed — split, sampling, trainer. |

---

## The oracle CSV (PHI guardrail)

The oracle reader pulls **only** `tile_id` + `label`. Any additional
columns (`patient_id`, `slide_id`, free-text notes, …) are silently
ignored so they cannot accidentally propagate into the audit DB or
the corrections CSV. The unit test
`tests/unit/active_learning/test_oracle.py::test_extra_columns_are_ignored`
locks this guarantee.

---

## What gets written

### `manifest.json`

```jsonc
{
  "run_id": "al-<uuid>",
  "config": { /* frozen ActiveLearningConfig */ },
  "started_at": "2026-04-24T13:04:00+00:00",
  "finished_at": "…",
  "acquisitions": [
    { "iteration": 0, "selected_tile_ids": ["tile-0095", …],
      "ece_before": 0.041, "ece_after": 0.032,
      "accuracy_after": 0.87, "train_loss": 1.23 },
    …
  ],
  "initial_ece": 0.041,
  "final_ece":   0.022,
  "final_accuracy": 0.96,
  "acquired_tile_ids": ["tile-0017", "tile-0088", …]
}
```

### `corrections.csv`

```
tile_id,predicted_label,corrected_label,annotator_id,iteration,timestamp
tile-0095,lung_aca,lung_aca,dr-a,0,2026-04-24T13:05:00+00:00
tile-0105,lung_scc,lung_n,dr-a,0,2026-04-24T13:05:00+00:00
…
```

Append-only. Phase 16 will read this file to pre-populate the
Annotate tab's history; Phase 17's sigstore manifests will sign it.

### Audit rows

Each iteration inserts one row into `~/.openpathai/audit.db`:

* `kind = "pipeline"` (the AL kind lands with Phase 17's audit
  extensions — the current schema's `CHECK` constraint limits the
  field to `pipeline | training`).
* `graph_hash = sha256(config_hash + iter)` — unique per iteration,
  so `openpathai diff` can compare iteration *n* vs *n+1*.
* `metrics_json` carries `al_iteration`, `al_scorer`, `al_sampler`,
  `al_budget`, `annotator_id`, `ece_before`, `ece_after`,
  `accuracy_after`, `train_loss`.

---

## Troubleshooting

**"My ECE went up!"** Expected occasionally when the budget is tiny
and the seed set is class-imbalanced. Try `--seed-size 20 --budget 10`
and re-run. The loop only guarantees that on a well-calibrated
synthetic oracle ECE does not increase *on average*; a single bad
iteration can still regress.

**"Budget exceeds unlabeled pool size."** Shrink `--budget` or
`--seed-size`, or pass a larger pool CSV. The pre-flight math is
`len(pool) × (1 - holdout) − seed_size`.

**"CSVOracle has no label for tile …"** The sampler picked a tile id
that is not present in the pool CSV. This is a sanity check — every
tile id the loop sees must have a ground-truth label in the CSV.

---

## From simulated oracle to real pathologist (Phase 16 preview)

The `Oracle` protocol has exactly one method:

```python
def query(
    self,
    tile_ids: Sequence[str],
    *,
    predictions: Mapping[str, str],
    iteration: int,
) -> list[LabelCorrection]: ...
```

Phase 16's `GUIOracle` will wrap a queue-backed Gradio callback:
the Annotate tab displays the N tiles, the pathologist clicks, and
the callback returns one `LabelCorrection` per tile. Nothing else in
the loop — uncertainty, diversity, corrections CSV, audit —
changes.
