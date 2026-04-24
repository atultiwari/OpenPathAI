# Foundation models (Phase 13)

> **Status:** v1.0 line opens · CLI-first · GUI picker lands in Phase 16.

OpenPathAI's foundation layer wraps eight pathology-scale
backbones behind a single
[`FoundationAdapter`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/foundation/adapter.py)
protocol. Each adapter knows its Hugging Face repo id, input
size, embedding dim, license, and gated-access status. When you
request a gated backbone but the local environment can't load it
(no HF token, missing weight file, import error), the **fallback
resolver** silently replaces it with DINOv2-small and records the
decision in the manifest — so a run manifest always records the
model that *actually* ran, not the one you asked for
(master-plan §11.5 clause 3).

---

## Shipped adapters

| id              | gated | embed dim | HF repo                             | status  |
| --------------- | ----- | --------- | ----------------------------------- | ------- |
| `dinov2_vits14` | no    | 384       | `timm/vit_small_patch14_dinov2…`    | shipped |
| `uni`           | yes   | 1024      | `MahmoodLab/UNI`                    | shipped |
| `ctranspath`    | yes   | 768       | — (local weights)                   | shipped |
| `uni2_h`        | yes   | 1536      | `MahmoodLab/UNI2-h`                 | stub    |
| `conch`         | yes   | 512       | `MahmoodLab/CONCH`                  | stub    |
| `virchow2`      | yes   | 1280      | `paige-ai/Virchow2`                 | stub    |
| `prov_gigapath` | yes   | 1536      | `prov-gigapath/prov-gigapath`       | stub    |
| `hibou`         | yes   | 768       | `histai/hibou-B`                    | stub    |

**Stubs register metadata + advertise their HF repo + fall back
cleanly** to DINOv2 on `.build()`. Promotion to a full adapter is
a Phase-13.5 micro-phase when a user asks (or when Phase 15 wires
CONCH's zero-shot surface).

---

## Quick start

```bash
# List the registry.
openpathai foundation list

# Ask the resolver what it would do.
openpathai foundation resolve uni
# → FallbackDecision JSON:
#   { "requested_id": "uni",
#     "resolved_id":  "dinov2_vits14",
#     "reason":       "hf_token_missing",
#     "message":      "uni requires Hugging Face gated access. …" }

# Extract features (future phase: will land as a pipeline node).
python -c "
from openpathai.foundation import default_foundation_registry
reg = default_foundation_registry()
adapter = reg.get('dinov2_vits14')
adapter.build()
print(adapter.embed(my_image_batch).shape)  # → (N, 384)
"

# Fit a linear probe on pre-extracted features.
openpathai linear-probe \\
    --features /tmp/my_bundle.npz \\
    --backbone uni \\
    --out      /tmp/probe_report.json
```

---

## Fallback semantics (iron rule #11, master-plan §11.5)

`resolve_backbone(requested_id, registry=…, allow_fallback=True)`
returns a frozen `FallbackDecision` carrying:

| field              | meaning                                                 |
| ------------------ | ------------------------------------------------------- |
| `requested_id`     | What the caller asked for.                              |
| `resolved_id`      | What will actually be loaded (either the request, or `dinov2_vits14`). |
| `reason`           | `ok` · `hf_token_missing` · `hf_gated` · `weight_file_missing` · `import_error` |
| `message`          | Banner text for CLI / GUI.                              |
| `hf_token_present` | Whether `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN` is set.   |

Pass `allow_fallback=False` (or `--strict` at the CLI) to
hard-fail instead of falling back.

**Audit contract:** every linear-probe run (and, Phase 16+, every
MIL training run) writes the full `FallbackDecision` into the
Phase-8 audit row's `metrics_json`. `openpathai audit show <run>`
will surface `backbone_id` / `resolved_backbone_id` /
`fallback_reason` side-by-side.

---

## Getting gated access

See [Setup — Hugging Face](setup/huggingface.md) for the per-repo
access-request flow. Once the user account accepts the licence
agreement, export either token variant and the resolver picks it
up automatically on the next call:

```bash
export HUGGINGFACE_HUB_TOKEN=hf_...
openpathai foundation resolve uni
# → reason becomes "ok" or "hf_gated" (the latter means token
#   present but access not yet accepted for that repo).
```

---

## Bringing your own adapter

```python
from openpathai.foundation import FoundationAdapter, FoundationRegistry

class MyAdapter:
    id = "my_backbone"
    display_name = "My custom backbone"
    gated = False
    hf_repo = None
    input_size = (224, 224)
    embedding_dim = 256
    tier_compatibility = frozenset({"T1", "T2"})
    vram_gb = 1.0
    license = "MIT"
    citation = "My Paper, 2026."

    def build(self, pretrained=True): ...
    def preprocess(self, image):      ...
    def embed(self, images):          ...

reg = FoundationRegistry()
reg.register(MyAdapter())
```

The ten required attributes + three methods are the whole
interface. The rest of the stack (linear probe, MIL, audit,
fallback) treats your class exactly like the shipped ones.

---

## Deferred for Phase 13

The master-plan deliverable list mentions three items that
explicitly don't ship in this phase:

- **LoRA fine-tuning.** `peft`-based LoRA adapter wiring is ~400
  LOC of its own — lands as a Phase 13.5 micro-phase.
- **UNI on LC25000 beats Phase-3 baseline by ≥ 3 pp AUC.** The
  acceptance bar needs (a) the real LC25000 download, (b) HF
  gated access, (c) a real GPU. All three are user-side; we ship
  the reproducible recipe
  ([`pipelines/foundation_linear_probe.yaml`](https://github.com/atultiwari/OpenPathAI/blob/main/pipelines/foundation_linear_probe.yaml))
  and leave the measurement to user-side validation.
- **Five real gated adapters (UNI2-h / CONCH / Virchow2 /
  Prov-GigaPath / Hibou).** Current status: stub + fallback. Real
  adapters land on demand or alongside Phase 15 (CONCH zero-shot).
