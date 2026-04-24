# Segmentation (Phase 14)

> **Status:** v1.0 · closed-vocab + promptable · GUI Segment-mode
> toggle lands in Phase 16.

Two protocols, one registry:

* [`SegmentationAdapter`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/segmentation/adapter.py)
  — closed-vocabulary (U-Net / nnU-Net / SegFormer / HoVer-Net /
  Attention U-Net). Input image → mask with a predefined class list.
* `PromptableSegmentationAdapter` — SAM2 / MedSAM / MedSAM2 /
  MedSAM3 family. Input image + point/box prompt → mask.

Shared fallback semantics identical to Phase 13 + Phase 14
detection: every gated / weight-backed adapter falls back to a
license-clean synthetic segmenter so the library surface stays
usable on any CI cell.

---

## Shipped adapters

### Closed-vocab

| id                 | license                   | status  | weight source                             |
| ------------------ | ------------------------- | ------- | ----------------------------------------- |
| `tiny_unet`        | MIT                       | shipped | — (pure-torch random init)                |
| `synthetic_tissue` | MIT                       | shipped | —                                          |
| `attention_unet`   | MIT                       | stub    | `huggingface://pathology/attention_unet`  |
| `nnunet_v2`        | Apache-2.0                | stub    | `huggingface://MIC-DKFZ/nnunet-v2`        |
| `segformer`        | NVIDIA Source Code Lic.   | stub    | `huggingface://nvidia/mit-b0`             |
| `hover_net`        | AGPL-3.0 (upstream)       | stub    | `local://hover_net.pth`                   |

### Promptable

| id                | license     | status  | weight source                                |
| ----------------- | ----------- | ------- | -------------------------------------------- |
| `synthetic_click` | MIT         | shipped | —                                             |
| `sam2`            | Apache-2.0  | stub    | `huggingface://facebook/sam2.1-hiera-large`  |
| `medsam`          | Apache-2.0  | stub    | `huggingface://wanglab/medsam-vit-base`      |
| `medsam2`         | Apache-2.0  | stub    | `huggingface://wanglab/MedSAM2`              |
| `medsam3`         | TBD         | stub    | — (not yet released)                          |

---

## Quick start — closed-vocab

```bash
openpathai segmentation list
openpathai segmentation resolve nnunet_v2          # → synthetic_tissue fallback
```

```python
from openpathai.segmentation import default_segmentation_registry, resolve_segmenter

reg = default_segmentation_registry()
decision = resolve_segmenter("nnunet_v2", registry=reg)
adapter = reg.get(decision.resolved_id)
adapter.build()

result = adapter.segment(my_image)
# result: SegmentationResult
# result.mask: Mask (array + class_names)
print(result.mask.array.shape, result.mask.class_names)
```

## Quick start — promptable

```bash
openpathai segmentation resolve medsam2            # → synthetic_click fallback
```

```python
from openpathai.segmentation import default_segmentation_registry, resolve_segmenter

reg = default_segmentation_registry()
decision = resolve_segmenter("medsam2", registry=reg)
adapter = reg.get(decision.resolved_id)
adapter.build()

result = adapter.segment_with_prompt(my_image, point=(y, x))
# result.mask.array is 1 where the clicked component was grown, 0 elsewhere
```

---

## Mask schema

```python
class Mask(BaseModel, frozen=True):
    array: np.ndarray          # (H, W) integer label map; write-locked
    class_names: tuple[str, ...]  # ordered; class_id 0 is background by convention
```

`Mask.array` is set to `writeable=False` at construction so
downstream consumers can trust it. `Mask.class_id("tissue")`
resolves a name to its integer id; `Mask.shape` returns the
(H, W) tuple.

`SegmentationResult` wraps a `Mask` plus image dimensions,
requested vs resolved model ids, and an optional metadata dict
(promptable adapters use `metadata["label_id_selected"]` to
record which connected component the prompt hit).

---

## License notes (iron rule #12)

- **HoVer-Net weights are AGPL-3.0.** The `hover_net` stub
  registers the model metadata + citation but requires the user
  to bring their own weights. OpenPathAI does not redistribute.
- **SegFormer upstream is NVIDIA Source Code License.** Stub only;
  non-commercial use only.
- **All other stubs** are Apache-2.0 or MIT upstream; real
  adapters will ship when a user asks.

The fallback resolvers ensure that every code path — every CLI
call, every pipeline-node import, every GUI callback — can
complete without any AGPL or gated-licence import, at the cost
of reduced capability (the synthetic segmenters are not
production tools).

---

## Deferred for Phase 14

- **nnU-Net on GlaS ≥ 0.85 Dice acceptance bar.** Needs a GPU + the
  Warwick GlaS archive + real nnU-Net weights. Dataset card + stub
  shipped; user-side validation closes the loop.
- **MedSAM2 visible-mask-from-click demo.** Needs HF-gated
  MedSAM2 weights (400 MB+). The synthetic-click fallback ships a
  deterministic equivalent for CI and license-clean demos.
- **Real adapters for all nine non-shipped entries.** Promotion
  on demand or alongside Phase 15 (which wires MedSAM2 text-prompt
  segmentation through CONCH).
- **Analyse-tab Segment toggle / Annotate-tab click-to-segment
  UI.** Phase 16 alongside the real Annotate tab.
- **Pipeline primitives (`segmentation.unet`, `segmentation.nnunet`,
  `segmentation.medsam2`).** ~30 LOC of `@node` wrapping each;
  lands alongside Phase 15 NL-driven pipeline drafting.
