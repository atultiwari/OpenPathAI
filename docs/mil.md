# Multiple-Instance Learning (Phase 13)

> **Status:** v1.0 line · CLI + library surface · MIL GUI picker in Phase 16.

A MIL aggregator turns a **bag** of per-tile features into a
slide-level prediction + per-tile attention weights (for heatmap
rendering in Phase 14+). Phase 13 ships two aggregators end-to-end
and registers three more as stubs.

---

## Shipped aggregators

| id         | status  | notes                                                 |
| ---------- | ------- | ----------------------------------------------------- |
| `abmil`    | shipped | Gated-attention MIL (Ilse et al. 2018).               |
| `clam_sb`  | shipped | CLAM single-branch w/ instance clustering (Lu 2021).  |
| `clam_mb`  | stub    | Multi-branch variant — Phase 13.5 promotion pending.  |
| `transmil` | stub    | Nyström-attention — Phase 13.5.                       |
| `dsmil`    | stub    | Dual-stream max attention — Phase 13.5.               |

Stubs raise `NotImplementedError` with a pointer to the worklog
on `.fit()` / `.forward()` / `.slide_heatmap()`. They're in the
registry so `openpathai mil list` shows the full deliverable
list.

---

## Quick start

```python
from openpathai.mil import ABMILAdapter, CLAMSingleBranchAdapter

# One bag per slide: each bag is (n_tiles, embedding_dim).
bags   = [tile_features[slide] for slide in slides]
labels = [slide_label[slide]   for slide in slides]

adapter = ABMILAdapter(embedding_dim=384, num_classes=2)
report  = adapter.fit(bags, labels, epochs=10, lr=1e-3)
# → MILTrainingReport: aggregator_id, final_train_loss, train_loss_curve, …

# Per-slide prediction + attention.
out = adapter.forward(bags[0])
# → MILForwardOutput: logits (num_classes,), attention (N,)

# Attention-weighted slide heatmap for Phase 14+ viewer.
heatmap = adapter.slide_heatmap(bags[0], tile_coords)  # (Y, X) np.ndarray
```

### CLAM instance loss

`CLAMSingleBranchAdapter` adds an **instance-level clustering
loss** on top of the ABMIL attention: top-k attention tiles are
pushed toward the bag label and bottom-k tiles away. Two knobs:

```python
CLAMSingleBranchAdapter(
    embedding_dim=384,
    num_classes=2,
    instance_loss_weight=0.3,  # scales the clustering loss
    top_k=8,                   # how many tiles feed the clustering loss
)
```

---

## Bag shape contract

Every aggregator expects a bag as a 2-D `np.ndarray` or
`torch.Tensor` of shape `(n_tiles, embedding_dim)`. Labels are
1-D integer arrays, one label per bag. Bags may have different
`n_tiles` across slides — each forward pass runs on a single bag,
so ragged batches are fine.

When `n_tiles < top_k` (CLAM), the top-k / bottom-k index sets
overlap and the instance loss is effectively a no-op that
iteration — the bag-level cross-entropy still trains cleanly.

---

## Heatmap assembly

```python
heatmap = adapter.slide_heatmap(bag, coords)
```

`coords` is a 2-D `(n_tiles, 2)` array of `(y, x)` grid positions
(in tile units, not pixels). The returned float32 array has shape
`(y_max+1, x_max+1)` and carries attention weights directly — the
sum over cells equals 1 because attention is softmax-normalised.

Phase 14 will add a pipeline node `mil.slide_heatmap` that
expands this to pixel resolution via DZI + OpenSeadragon overlay.

---

## Deferred for Phase 13

- **CLAM-MB / TransMIL / DSMIL** — registered stubs; real
  implementations each take ~100–200 LOC and lands as a Phase-13.5
  micro-phase when a user asks.
- **MIL + Phase-9 cohort driver integration.** Currently `.fit()`
  accepts in-memory bag lists. The `openpathai train --cohort`
  wiring that fans a cohort out into per-slide bag → aggregator
  lands in Phase 16 alongside the Annotate-tab pipeline.
- **Heatmap rendering on a real WSI.** The `.slide_heatmap()`
  method returns a tile-level grid today; the pixel-accurate
  DZI overlay is Phase 14 territory.
