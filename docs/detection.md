# Object detection (Phase 14)

> **Status:** v1.0 · CLI-first · GUI Detect-mode toggle lands in Phase 16.

Phase 14 wires detection behind a single
[`DetectionAdapter`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/detection/adapter.py)
protocol, reusing the
[`FallbackDecision`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/foundation/fallback.py)
resolver from Phase 13. The library exposes one real adapter
(YOLOv8 via lazy-imported Ultralytics), three registered stubs
(YOLOv11 / YOLOv26 / RT-DETRv2), and a license-clean synthetic
detector that always works.

---

## AGPL-3.0 notice (iron rule #12)

Ultralytics YOLO is AGPL-3.0. OpenPathAI itself is MIT. The YOLO
adapter lazy-imports `ultralytics` only — we never vendor. Using
this adapter in a proprietary pipeline requires a [commercial
Ultralytics licence](https://ultralytics.com/license).

**What this means in practice:**

- If `ultralytics` isn't installed, the adapter raises
  `ImportError` on `.build()`, which the fallback resolver turns
  into `FallbackDecision(resolved_id="synthetic_blob", reason="import_error")`.
- If you install `ultralytics` and use YOLOv8 for your own
  research work, you inherit AGPL obligations.
- If you need a detector without AGPL contamination, stick to
  `synthetic_blob` (MIT, always loadable) or `rt_detr_v2` (Apache-2.0
  — stub today, promotion on demand).

The NOTICE file lists this explicitly.

---

## Shipped adapters

| id              | license                   | status  | weight source                           |
| --------------- | ------------------------- | ------- | --------------------------------------- |
| `yolov8`        | AGPL-3.0 (upstream)       | shipped | `ultralytics://yolov8n.pt`              |
| `yolov11`       | AGPL-3.0 (upstream)       | stub    | `ultralytics://yolo11n.pt`              |
| `yolov26`       | AGPL-3.0 (upstream)       | stub    | `ultralytics://yolo26n.pt`              |
| `rt_detr_v2`    | Apache-2.0                | stub    | `huggingface://PekingU/rtdetr_v2_r50vd` |
| `synthetic_blob`| MIT                       | shipped | —                                        |

Stubs raise `GatedAccessError` on `.build()`; the fallback
resolver routes them to `yolov8`, which in turn falls back to
`synthetic_blob` if Ultralytics isn't installed.

---

## Quick start

```bash
openpathai detection list                  # registry
openpathai detection resolve yolov26       # FallbackDecision JSON
openpathai detection resolve yolov26 --strict   # hard-fail mode
```

```python
from openpathai.detection import default_detection_registry, resolve_detector

reg = default_detection_registry()
decision = resolve_detector("yolov26", registry=reg)
adapter = reg.get(decision.resolved_id)
adapter.build()

result = adapter.detect(my_image, conf_threshold=0.25)
# result: DetectionResult
# result.boxes: tuple[BoundingBox, ...]
# each box has x, y, w, h, class_name, confidence
```

### Filtering

`DetectionResult` is immutable but supports derived views:

```python
high_conf = result.filter_by_confidence(0.75)
for box in high_conf.boxes:
    print(box.xyxy, box.class_name, box.confidence)
```

---

## Bounding-box schema

```python
class BoundingBox(BaseModel, frozen=True):
    x: float            # top-left x, pixels, ≥ 0
    y: float            # top-left y, pixels, ≥ 0
    w: float            # width, pixels, > 0
    h: float            # height, pixels, > 0
    class_name: str     # non-empty
    confidence: float   # [0, 1]
```

`class_name` is the adapter-declared label (YOLOv8 uses COCO
names; the synthetic detector uses `"blob"` by default).
Downstream consumers (audit, Phase 21 OpenSeadragon viewer)
assume nothing beyond the schema.

---

## Bringing your own detector

Any object that honours the `DetectionAdapter` protocol can be
registered:

```python
class MyDetector:
    id = "my_detector"
    display_name = "My detector"
    gated = False
    weight_source = None
    input_size = (640, 640)
    tier_compatibility = frozenset({"T1", "T2"})
    vram_gb = 0.5
    license = "MIT"
    citation = "Me, 2026."

    def build(self, pretrained=True): ...
    def detect(self, image, *, conf_threshold=0.25): ...

from openpathai.detection import default_detection_registry
reg = default_detection_registry()
reg.register(MyDetector())
```

---

## Deferred for Phase 14

- **Real YOLOv26 on MIDOG ≥ 0.6 F1 acceptance bar.** Needs a
  CUDA GPU, the 25 GB MIDOG22 archive, and `ultralytics`. We
  ship the detector registry + the MIDOG22 dataset card; user-side
  validation closes the loop.
- **Real RT-DETRv2 adapter.** Stub today; promotion when a user
  asks or when Phase 15 wires NL-driven pipeline drafting.
- **Analyse-tab Detect-mode toggle.** Phase 16 alongside the
  Annotate UI.
- **Pipeline-node integration (`detection.yolo`).** ~30 LOC of
  `@node` wrapping; lands in Phase 14.5 or alongside Phase 15.
