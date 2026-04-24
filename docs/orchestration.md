# Orchestration (Phase 10)

Phase 10 turns the Phase 9 cohort surface into **parallel, reproducible,
queryable** pipeline execution. Four independent deliverables share
the same primitives (the Phase 1 executor + cache, the Phase 2
`Cohort`, the Phase 8 audit hooks):

1. **Parallel in-process executor** — `ThreadPoolExecutor` fan-out
   within a single `Executor.run` call.
2. **Cohort fan-out** — `Executor.run_cohort(pipeline, cohort)` runs
   the same pipeline once per slide, each slide keyed independently
   in the content-addressable cache.
3. **Snakefile export** — `openpathai run --snakefile demo.smk` writes
   a Snakemake-compatible Snakefile. Users run it with their own
   `snakemake` CLI; we never import or subprocess Snakemake.
4. **MLflow sink** — opt-in secondary sink behind
   `OPENPATHAI_MLFLOW_ENABLED=1`. Mirrors the Phase 8 audit DB rows
   into a local MLflow tracking store for richer metric / artifact
   UIs.

---

## Parallel execution

```bash
# Sequential (Phase 1 behaviour — unchanged default).
openpathai run pipelines/demo.yaml

# ThreadPool over independent DAG nodes at each topological level.
openpathai run pipelines/demo.yaml --workers 4 --parallel-mode thread
```

A step's cache key is `sha256(node_id + code_hash + input_config +
upstream_hashes)`, so a threaded run and a sequential run produce
**byte-identical manifests** and a second run is a 100% cache hit.
The manifest's `steps` list is topologically ordered regardless of
thread-of-completion.

### When to pick thread mode

- **Use threads** when the DAG has multiple independent branches
  at the same level (I/O-bound preprocessing, cohort fan-out).
- **Stick with sequential** when the DAG is linear, or when the
  bottleneck is a single torch training step (the GIL makes
  threaded training *slower*, not faster).

Process-pool parallelism is deferred to Phase 18 where the Docker
tier changes the IPC story.

---

## Cohort fan-out

A pipeline YAML declares its cohort-fan-out slot on a single step:

```yaml
id: supervised-tile-classification
mode: exploratory
cohort_fanout: load_slide_index   # the step whose output is a slide
max_workers: 4
steps:
  - id: load_slide_index
    op: demo.constant
    inputs:
      value: 1
  ...
```

```python
from openpathai.cli.pipeline_yaml import load_pipeline
from openpathai.io import Cohort
from openpathai.pipeline import ContentAddressableCache, Executor

pipeline = load_pipeline("pipelines/supervised_tile_classification.yaml")
cohort = Cohort.from_yaml("pilot.yaml")
executor = Executor(
    ContentAddressableCache(root="~/.openpathai/cache"),
    max_workers=4,
    parallel_mode="thread",
)
result = executor.run_cohort(pipeline, cohort)
print(result.cache_stats)   # aggregated across slides
```

Each per-slide run lands under its own `run_id` in the audit DB and
(when the MLflow sink is on) its own MLflow run — so the Runs tab,
`openpathai audit list`, and `openpathai diff run_a run_b` all work
at slide granularity.

### How the slide gets into the pipeline

When the target step's node declares a `slide` / `slide_ref` /
`cohort_slide` field on its pydantic input model, fan-out injects
the slide's `model_dump()` payload into that slot. Nodes whose input
schema does not declare one of those names are **unchanged** per
slide — the scoped pipeline id (`<base-id>@<slide_id>`) is still
unique so every slide gets its own run row, but the node-level cache
key is shared across slides (cheap: after the first slide everything
is a cache hit).

---

## Snakefile export

```bash
openpathai run pipelines/supervised_tile_classification.yaml \
    --snakefile supervised.smk
```

Writes a self-contained Snakefile and exits **without** running the
pipeline. OpenPathAI never imports or subprocesses Snakemake — users
who own a Snakemake environment run:

```bash
snakemake --snakefile supervised.smk --cores 4
# For cohort-fanout pipelines:
snakemake --snakefile supervised.smk --cores 4 --config SLIDES='a,b,c'
```

Every rule shells back into `openpathai run ... --step <id>` (the
`--step` flag is on the roadmap for Phase 11 where the per-step
entry point lands). For now the generated Snakefile is a readable,
versioned plan document you can cross-reference in a paper's methods.

---

## MLflow sink (opt-in)

```bash
# One-time, per shell:
export OPENPATHAI_MLFLOW_ENABLED=1

openpathai run pipelines/supervised_tile_classification.yaml
openpathai mlflow-ui --host 127.0.0.1 --port 5000
```

Tracking URI defaults to `file://$OPENPATHAI_HOME/mlruns` (override
via `MLFLOW_TRACKING_URI`). Three experiments appear automatically:

- `openpathai.pipeline` — one run per `openpathai run`.
- `openpathai.training` — one run per `openpathai train`.
- `openpathai.analyses` — one row per `openpathai analyse`.

The sink is **secondary**: the Phase 8 audit DB is still the single
source of truth. A failing MLflow call logs a warning and the
pipeline run completes unaffected (same contract as the audit DB
hook itself).

### Cleanup

```bash
# Nuke everything MLflow knows about.
rm -rf ~/.openpathai/mlruns

# Or use MLflow's built-in pruning:
mlflow gc --backend-store-uri file://~/.openpathai/mlruns
```

### Turning the sink off

```bash
unset OPENPATHAI_MLFLOW_ENABLED       # or set it to 0
```

When disabled, **zero** MLflow imports happen — `sys.modules` stays
mlflow-free (verified by `tests/unit/pipeline/test_mlflow_sink.py`).

---

## CLI reference (Phase 10 additions)

| Flag | Purpose |
|---|---|
| `openpathai run --workers N` | Thread-pool size. |
| `openpathai run --parallel-mode {sequential,thread}` | Execution topology. |
| `openpathai run --snakefile PATH` | Export-only — write Snakefile + exit. |
| `openpathai mlflow-ui --host H --port P` | Launch MLflow UI against the local tracking store. |

Every Phase 10 flag inherits the Phase 8 `--no-audit` behaviour: you
can still disable audit logging per-run without touching the
orchestration story.
