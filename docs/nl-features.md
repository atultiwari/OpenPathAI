# Natural-language features (Phase 15)

> **Status:** v1.0 · Bet 2 live · CLI-first · GUI NL prompt box
> + Pipelines chat panel land in Phase 16.

Three library surfaces behind a single `openpathai.nl` package:

* [`classify_zero_shot(image, prompts)`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/nl/zero_shot.py)
  — CONCH text-prompted tile classification.
* [`segment_text_prompt(image, prompt)`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/nl/text_prompt_seg.py)
  — MedSAM2 text-prompted segmentation via CONCH's text encoder.
* [`draft_pipeline_from_prompt(prompt, backend=...)`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/nl/pipeline_gen.py)
  — MedGemma-driven `Pipeline` YAML drafting (iron rule #9 — user
  review required before any run).

All three are local-by-default: we never send pathology images or
prompts to hosted LLMs. The LLM backend layer talks to Ollama
(default) or LM Studio on `localhost`.

---

## PHI guardrail

**Prompts are hashed, not logged.** Every NL-initiated run inserts
one audit row whose `metrics_json` carries `nl_prompt_hash`
(SHA-256, first 16 hex chars) — the raw prompt text never lands
in SQLite. If a pathologist accidentally pastes a patient
identifier into a prompt, the identifier does not leak into the
audit DB.

Raw prompts are still visible at the CLI stdout and in the user's
terminal history; the guardrail is on the persisted audit log.

---

## LLM backends

```bash
openpathai llm status
# id        base_url                     model            reachable
# --------  ---------------------------  ---------------  ---------
# ollama    http://localhost:11434/v1    medgemma:1.5     yes
# lmstudio  http://localhost:1234/v1     medgemma-1.5     no
#
# active backend: ollama (http://localhost:11434/v1 / medgemma:1.5)
```

`openpathai llm pull <model>` wraps `ollama pull`. LM Studio
users install models through their GUI.

### Adding a new backend

Any class conforming to the `LLMBackend` protocol (attribute block
+ `.probe()` + `.chat()`) can register with
`LLMBackendRegistry.register(...)`. The shared
`OpenAICompatibleBackend` base handles the HTTP plumbing — most
providers just need to override `id` / `display_name` / `base_url`
/ `_probe_path`.

### Fallback

When neither backend is reachable, `detect_default_backend()`
raises `LLMUnavailableError` with the install message. The CLI
exits with code 3 and prints the message to stderr. Iron rule
#11 — no silent fallback to some hosted service.

---

## Zero-shot classification

```bash
openpathai nl classify tile.png --prompt "tumor" --prompt "normal"
```

```json
{
  "backbone_id": "conch",
  "resolved_backbone_id": "synthetic_text_encoder",
  "image_width": 256,
  "image_height": 256,
  "predicted_prompt": "tumor",
  "probs": [0.6312, 0.3688],
  "prompts": ["tumor", "normal"]
}
```

Two prompts minimum (softmax needs a partition). No training
required — CONCH's joint vision-language embedding makes the
image-vs-prompt similarity the softmax logits.

**Fallback semantics:** without gated CONCH access, the
text-encoder falls back to a deterministic hash-based stub. The
interface + result type + audit-logging all work; the numerical
predictions are then meaningless for pathology. The audit row's
`resolved_backbone_id = "synthetic_text_encoder"` flags this so
a downstream reviewer can tell at a glance whether a run used the
real CONCH or the stub.

---

## Text-prompted segmentation

```bash
openpathai nl segment tile.png --prompt "gland" --out mask.png
```

```json
{
  "class_names": ["background", "prompt_region"],
  "mask_shape": [1024, 1024],
  "mask_png": "mask.png",
  "metadata": {
    "label_id_selected": 3,
    "prompt_hash": "a1b2c3d4e5f67890",
    "requested_segmenter_id": "medsam2"
  },
  "model_id": "medsam2",
  "resolved_model_id": "synthetic_click"
}
```

The mask PNG uses `mask_value * (255 // max_label)` for visibility
— raw label ids live in the returned `Mask.array`. Same fallback
semantics as Phase 14's promptable stubs: without real MedSAM2
weights, routes through `SyntheticClickSegmenter` with a
deterministic prompt-biased centre click.

---

## Pipeline draft from natural language

```bash
openpathai nl draft "fine-tune resnet18 on lc25000 for 2 epochs" \\
    --out /tmp/drafted.yaml
```

The CLI prompts MedGemma (via the active local backend) with a
system prompt containing the `Pipeline` pydantic schema. On
schema-validation failure the error is fed back and a correction
is requested — up to 3 attempts. If all three attempts fail,
`PipelineDraftError` carries the last LLM output so the user can
salvage it by hand.

**Iron rule #9 (never auto-execute):** `openpathai nl draft`
writes the YAML and exits. Running the pipeline is always a
separate step:

```bash
openpathai run /tmp/drafted.yaml
```

This is enforced at the library layer too —
`draft_pipeline_from_prompt` returns a `PipelineDraft` that
carries the parsed `Pipeline` for inspection; there is no
`run()` shortcut.

---

## Deferred for Phase 15

- **Real CONCH zero-shot accuracy + MedSAM2 mask demo** — need
  gated HF access + real GPU. Ship infrastructure + fallback
  stubs; user-side validation when gated access lands.
- **GUI Analyse-tab NL prompt box + Pipelines chat panel** —
  Phase 16 alongside the Annotate tab.
- **Function calling / agentic refinement** — single-turn only
  in this phase. A future phase may add Tool Use once a user has
  a concrete need.
- **Hosted / cloud LLM backends** (OpenAI, Anthropic, etc.) —
  iron rule: no pathology data leaves the laptop by default.
  Opt-in hosted backends land as a Phase 17 add-on when a user
  explicitly asks.
