# Cohorts (Phase 9)

A cohort is a named, hashable, ordered group of slides — master-plan
§9.4. Pipelines, QC, and real-cohort training all take cohorts as
their primary unit, not individual slides. The
[`Cohort`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/io/cohort.py)
pydantic model hashes deterministically on its sorted slide list plus
metadata, so the Phase 1 content-addressable cache works naturally at
cohort scope.

## Cohort YAML shape

```yaml
id: demo
slides:
  - slide_id: a
    path: /data/slides/a.svs
    patient_id: pt-01
    label: normal
    mpp: 0.25
    magnification: 40X
  - slide_id: b
    path: /data/slides/b.svs
    patient_id: pt-02
    label: tumour
metadata:
  project: pilot
```

Every field except `id`, `slide_id`, and `path` is optional. Labels
are free-text on `SlideRef.label`; the Train tab treats each distinct
label as a class.

## Build a cohort

**From a directory** — walks the top level, picks up any file whose
suffix matches `.svs / .ndpi / .mrxs / .tif / .tiff / .scn / .vsi`:

```bash
openpathai cohort build /data/slides \
    --id pilot \
    --output pilot.yaml
# Optional: --pattern "*.svs"
```

**From Python:**

```python
from openpathai.io import Cohort

cohort = Cohort.from_directory("/data/slides", "pilot")
cohort.to_yaml("pilot.yaml")
reloaded = Cohort.from_yaml("pilot.yaml")
assert cohort.content_hash() == reloaded.content_hash()
```

**From the GUI** — open the **Cohorts** tab, expand **Build cohort
from directory**, fill in directory + id + output path, click submit.

## Run QC

Every check in [`openpathai.preprocessing.qc`](preprocessing.md) runs
on every slide's thumbnail. See [preprocessing](preprocessing.md) for
the individual checks; the cohort-scope driver is:

```bash
openpathai cohort qc pilot.yaml --output-dir pilot-qc --pdf
# Writes pilot-qc/cohort-qc.html (always) and pilot-qc/cohort-qc.pdf (with --pdf).
```

From Python:

```python
import numpy as np
from openpathai.io import Cohort, open_slide

def thumbnail(slide):
    with open_slide(slide.path) as reader:
        info = reader.info()
        return np.asarray(
            reader.read_region((0, 0), (info.width, info.height), level=reader.levels - 1),
            dtype=np.uint8,
        )[..., :3]

cohort = Cohort.from_yaml("pilot.yaml")
report = cohort.run_qc(thumbnail)
print(report.summary())  # {"pass": ..., "warn": ..., "fail": ...}
```

From the GUI: **Cohorts** tab → **Run QC** accordion. Both HTML and
PDF are written to the output directory; the PDF is byte-deterministic
(same `invariant=True` pattern as the Phase 7 safety report).

## Training on a cohort

The Phase 3 `LightningTrainer` now accepts either an
`InMemoryTileBatch` (the synthetic smoke path) or a pre-built
`torch.utils.data.Dataset` (the cohort path). The CLI exposes both:

```bash
# Real-cohort training (labels come from SlideRef.label).
openpathai train --cohort pilot.yaml --model resnet18 --epochs 1 --device cpu

# Or from a shipped / locally-registered dataset card.
openpathai train --dataset kather_crc_5k --model resnet18 --epochs 1 --device cpu

# Or the classic Phase 3 synthetic smoke path.
openpathai train --synthetic --model resnet18 --num-classes 4 --epochs 1
```

The GUI **Train** tab has a **Dataset source** radio with the same
three options.

---

## Caching + reproducibility

Because `Cohort.content_hash()` is deterministic, the Phase 1
executor's content-addressable cache is cohort-scoped for free — a
second `openpathai run pipeline.yaml` over the same cohort YAML hits
100% cache.

## Running a pipeline across a cohort (Phase 10)

Pipelines that declare `cohort_fanout: <step_id>` run once per slide
via `Executor.run_cohort`. The per-slide runs cache independently, so
a re-run over an unchanged cohort is 100% cache hits:

```python
from openpathai.cli.pipeline_yaml import load_pipeline
from openpathai.io import Cohort
from openpathai.pipeline import ContentAddressableCache, Executor

pipeline = load_pipeline("pipelines/supervised_tile_classification.yaml")
cohort = Cohort.from_yaml("pilot.yaml")
executor = Executor(
    ContentAddressableCache(root="~/.openpathai/cache"),
    max_workers=4, parallel_mode="thread",
)
result = executor.run_cohort(pipeline, cohort)
print(result.cache_stats)
```

Each per-slide run lands in the Phase 8 audit DB (and, opt-in,
MLflow) under its own `run_id`. Full orchestration docs:
[Orchestration (Phase 10)](orchestration.md).
