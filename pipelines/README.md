# Pipeline YAML recipes

Every file in this directory is a declarative pipeline — a list of
typed `@openpathai.node` steps plus their wiring. Pipelines are loaded
via `openpathai.load_pipeline(path)` (or `openpathai run PATH` from the
CLI) and executed against the Phase 1 `Executor` + `ContentAddressableCache`.

The YAML shape mirrors the `openpathai.pipeline.Pipeline` pydantic
model:

```yaml
id: unique-pipeline-id
mode: exploratory   # or "diagnostic" (v1.0+ — signs the manifest)
steps:
  - id: step_a
    op: namespace.node_id     # must resolve in REGISTRY
    inputs:
      some_field: 42
  - id: step_b
    op: other.node
    inputs:
      upstream: "@step_a"        # whole-artifact reference
      only_field: "@step_a.foo"  # single-field reference
```

Step inputs can be literal JSON-compatible values or `@step` /
`@step.field` references to upstream outputs. The executor topo-sorts
the graph (Kahn's algorithm), content-addresses every step, and emits a
hashable `RunManifest`.

## Shipped recipes

| Recipe | Phase | What it does |
|---|---|---|
| [`supervised_synthetic.yaml`](supervised_synthetic.yaml) | 5 | Trains a tile classifier on the Phase 3 `synthetic_tile_batch` and writes a `TrainingReportArtifact`. Smoke test for the CLI + executor path; works on CPU in under a second. |

Real-cohort recipes (LC25000, PCam, mhist, HISTAI, ...) land with the
Phase 9 cohort driver. Phase 5 only covers the engine-level plumbing.
