# Datasets

OpenPathAI describes every dataset by a YAML card. Shipped cards live
under `data/datasets/`; user-registered cards live under
`~/.openpathai/datasets/`. The registry discovers both sets
automatically — user cards take precedence on name collisions.

```shell
# Browse the shipped list (Phase 5 CLI)
openpathai datasets list --source shipped

# Browse what you've registered yourself (Phase 7 CLI)
openpathai datasets list --source local

# Combined — with a `src=shipped|local` column
openpathai datasets list
```

---

## Shipped cards

| Name | Tissue | Classes | Size | Licence | Notes |
|------|--------|---------|------|---------|-------|
| **kather_crc_5k** | colon | 8 | ~140 MB | CC-BY-4.0 | **Canonical smoke-test dataset** for OpenPathAI — tiny, permissive licence. Trains a ResNet-18 end-to-end in ~10 min on a laptop CPU. |
| lc25000 | lung, colon | 5 | 1.8 GB | CC-BY-4.0 | Clean regression benchmark. Patient IDs not published; use slide-level CV. |
| mhist | colon | 2 | 358 MB | CC-BY-NC-SA-4.0 | Tiny (~3k tiles); excellent for CI and rapid iteration. |
| pcam | breast, lymph_node | 2 | 6.3 GB | CC0-1.0 | PatchCamelyon — standard metastasis-detection baseline. |
| histai_breast | breast | 1 | 800 GB (WSI) | CC-BY-4.0 (verify) | Cohort-scale WSI dataset. Gated. |
| histai_metadata | mixed | 1 | 205 MB | CC-BY-4.0 (verify) | Slide-level metadata registry. Gated. |

Start with `kather_crc_5k` on a new machine — it downloads quickly
(~140 MB), and a ResNet-18 smoke run validates the whole stack end to
end before you commit to a larger cohort.

---

## Register your own dataset

Phase 7 surfaces a first-class workflow for adding a local folder as a
card. The layout expected on disk:

```
<root>/
  <class_a>/
    tile_0001.png
    tile_0002.png
  <class_b>/
    ...
```

Supported extensions: `.png .jpg .jpeg .tif .tiff`.

### From the CLI

```shell
openpathai datasets register /path/to/tree \
    --name my_demo \
    --tissue colon \
    --license CC-BY-4.0
```

### From Python

```python
from openpathai.data import register_folder

card = register_folder(
    "/path/to/tree",
    name="my_demo",
    tissue=("colon",),
    modality="tile",
)
```

### From the GUI

Open the **Datasets** tab, expand **Add local dataset**, fill in the
folder path + name + tissue, click **Register local dataset**. The
registry table refreshes with your new card in the `source=local`
column.

### What it does

`register_folder`:

1. scans every direct subdirectory of `<root>` and treats each one as
   a class;
2. counts images, computes a path+size fingerprint (not a content
   hash — Phase 9's job);
3. writes a `DatasetCard` YAML with `download.method="local"` and
   `download.local_path=<root>` to `~/.openpathai/datasets/<name>.yaml`;
4. returns the loaded card.

The registry picks up the file on the next call.

### Removing a card

```shell
openpathai datasets deregister my_demo
```

...or click **Deregister** on the GUI. Shipped cards are never touched.

---

## Training directly from a card (Phase 9)

Local-method cards (anything written by `register_folder`, plus
`kather_crc_5k` once the Zenodo archive is unzipped under
`~/.openpathai/datasets/kather_crc_5k/<class>/*.png`) are trainable
directly:

```bash
openpathai train --dataset kather_crc_5k --model resnet18 --epochs 1 --device cpu
```

The Train tab in the GUI has the same capability — pick **Dataset
card (local)** on the **Dataset source** radio.

Non-local methods (`kaggle`, `zenodo`, `http`, `huggingface`) will
land alongside the Phase 10 orchestration work; for now
`build_torch_dataset_from_card` raises a `NotImplementedError` with a
Phase-10 pointer.

---

## Downloading shipped cards

The Phase 5 `openpathai download` command handles Kaggle-hosted
datasets today. Zenodo and HuggingFace paths land in later phases. For
now, Zenodo-hosted cards (like `kather_crc_5k`) include manual
instructions in the card's `download.instructions_md` field — run
`openpathai datasets show kather_crc_5k` to see them.
