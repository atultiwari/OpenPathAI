# Phase 15 — CONCH zero-shot + NL pipeline drafting + MedGemma backend

> Third phase of the **v1.0.0 release line**. Brings **Bet 2
> (natural-language + zero-shot)** live. Wires an
> OpenAI-compatible LLM backend layer (Ollama + LM Studio),
> CONCH-based zero-shot tile classification with text prompts,
> MedSAM2-style text-prompted segmentation, and a MedGemma-driven
> pipeline-draft helper that produces a pydantic-validated
> `Pipeline` YAML from a one-sentence user description.
>
> Master-plan references: §15 (NL features), §15.1 (LLM backend),
> §15.2 (CONCH zero-shot), §15.3 (MedSAM2 text-prompt seg),
> §15.4 (MedGemma pipeline draft), §22 Phase 15 block.

---

## Status

- **Current state:** 🔄 active
- **Version:** v1.0 (third phase of the v1.0.0 release line)
- **Started:** 2026-04-24
- **Target finish:** 2026-05-08 (~1.5 weeks master-plan target)
- **Actual finish:** (fill on close)
- **Dependency on prior phases:** Phase 1 (manifest), Phase 2
  (dataset registry), Phase 5 (pipeline YAML loader +
  `loads_pipeline`), Phase 8 (audit log for NL-initiated runs),
  Phase 13 (`FoundationAdapter` protocol — CONCH stub from Phase
  13 promotes to real here), Phase 14 (promptable segmentation
  adapters — MedSAM2 stub from Phase 14 gains text-prompt support
  here via CONCH's embedding head).
- **Close tag:** `phase-15-complete`.

---

## 1. Goal (one sentence)

Ship `openpathai.nl` — an OpenAI-compatible LLM backend adapter
(Ollama + LM Studio), CONCH-based zero-shot text-prompted
classification, MedSAM2 text-prompted segmentation via the CONCH
text encoder, and a `draft_pipeline_from_prompt(text)` helper
that asks a local MedGemma instance to produce a pydantic-
validated `Pipeline` YAML — so that `openpathai nl classify
"highlight tumor nests" --image tile.png` + `openpathai nl draft
"fine-tune resnet18 on lc25000 for 2 epochs"` both work end-to-
end on a laptop with Ollama + `medgemma:1.5` installed.

---

## 2. Non-Goals

- **No cloud / hosted LLMs.** Iron rule #13 (implicit —
  master-plan §17 PHI policy) says no pathology data leaves the
  laptop by default. The LLM backend is strictly local
  (Ollama + LM Studio); hosted-OpenAI + Anthropic backends can
  land as an opt-in Phase 17 feature when a user asks.
- **No real CONCH zero-shot accuracy guarantee.** The
  acceptance target "Highlight tumor nests produces a visible
  heatmap on a test slide" requires (a) gated MahmoodLab/CONCH
  access, (b) the CONCH 1.5B weights, (c) a real GPU. Phase 15
  ships the text-encoder + image-encoder adapter interface +
  fallback; the measurement is user-side.
- **No real MedSAM2 text-prompt accuracy guarantee.** Same
  reason — MedSAM2 weights are 400 MB+ and HF-gated. The
  promptable-seg adapter gains a text-prompt code path with a
  synthetic text-to-point router fallback; real measurement is
  user-side.
- **No GUI surface.** The Analyse-tab NL prompt box + the
  Pipelines-tab chat panel are GUI deliverables; they land in
  Phase 16 alongside the Annotate tab. Phase 15 is CLI + library
  only.
- **No function-calling / tool-use wiring.** MedGemma 1.5 is
  used as a text-in-text-out model: given a one-sentence prompt
  + the pipeline-YAML schema, it drafts a YAML string. No
  agentic loop, no tool-calling, no iterative refinement in this
  phase.
- **No CONCH fine-tuning.** Zero-shot inference only. Linear-
  probe on CONCH features uses the Phase 13 `linear_probe`
  pathway unchanged.
- **No audio / speech input.** Text-only prompts.
- **No persistent chat history.** Phase 15's CLI surface is
  single-shot (`openpathai nl draft <prompt>`). Multi-turn chat
  is a Phase-19 FastAPI concern.

---

## 3. Deliverables

### 3.1 `src/openpathai/nl/` — new subpackage

- [ ] `nl/__init__.py` — re-exports the public surface
      (`LLMBackend`, `OllamaBackend`, `LMStudioBackend`,
      `LLMBackendRegistry`, `detect_default_backend`,
      `LLMUnavailableError`, `ZeroShotResult`, `classify_zero_shot`,
      `segment_text_prompt`, `draft_pipeline_from_prompt`,
      `PipelineDraft`).
- [ ] `nl/llm_backends/__init__.py` + `base.py` — `LLMBackend`
      protocol + frozen `ChatMessage` / `ChatResponse` /
      `BackendCapabilities` pydantic models.
- [ ] `nl/llm_backends/openai_compat.py` — shared OpenAI-chat-
      completions HTTP adapter. Takes `base_url` + `model` and
      exposes `.chat(messages, temperature, response_format) ->
      ChatResponse`. Uses `httpx` (already a Phase-3 dep) so we
      don't pull the full `openai` SDK.
- [ ] `nl/llm_backends/ollama.py` — `OllamaBackend(base_url,
      model)` subclass. Default `base_url = http://localhost:11434/v1`.
      Has a `probe()` method that hits `GET /api/tags` and
      returns whether the named model is installed.
- [ ] `nl/llm_backends/lmstudio.py` — `LMStudioBackend(base_url,
      model)`. Default `base_url = http://localhost:1234/v1`.
      Probe via `GET /v1/models`.
- [ ] `nl/llm_backends/registry.py` — `LLMBackendRegistry` +
      `detect_default_backend()` — tries ollama then lmstudio,
      returns the first reachable backend with the configured
      model loaded; raises `LLMUnavailableError` with an
      actionable install message otherwise.
- [ ] `nl/zero_shot.py` — CONCH zero-shot classifier:
      - `classify_zero_shot(image, prompts: Sequence[str], *,
        adapter=None, temperature=100.0) -> ZeroShotResult`.
        `ZeroShotResult` is a frozen pydantic model carrying
        `probs`, `prompts`, `predicted_prompt`, `image_width`,
        `image_height`, `backbone_id`, `resolved_backbone_id`.
      - Uses the Phase-13 CONCH adapter (stub today; this
        module promotes CONCH to a real adapter with a
        text-encoder method).
      - Fallback path: if the real CONCH isn't available,
        uses a synthetic `TextEncoderStub` that hashes
        prompts into 512-D vectors so the interface + result
        type are exercisable on any CI cell.
- [ ] `nl/text_prompt_seg.py` — MedSAM2 text-prompt
      segmentation:
      - `segment_text_prompt(image, prompt: str, *,
        segmenter=None, text_encoder=None) -> SegmentationResult`.
      - Uses the CONCH text encoder to map `prompt` → embedding,
        feeds that into MedSAM2 as the text-prompt vector. When
        MedSAM2 isn't loadable, falls back to the Phase-14
        `SyntheticClickSegmenter` with a centre-pixel prompt
        (strict fallback so the call always returns a valid
        `SegmentationResult`).
- [ ] `nl/pipeline_gen.py` — MedGemma-driven pipeline draft:
      - `draft_pipeline_from_prompt(prompt: str, *,
        backend=None) -> PipelineDraft`. `PipelineDraft` carries
        `prompt`, `yaml_text`, `pipeline` (parsed via Phase-5
        `loads_pipeline`), `backend_id`, `model_id`,
        `generated_at`.
      - Embeds the Pipeline pydantic schema into the system
        prompt so MedGemma outputs valid YAML.
      - Retries on schema-validation failure up to 3 times with
        a "you produced invalid YAML; here's the error" follow-
        up turn.

### 3.2 CLI — two new command groups

- [ ] `openpathai llm status` — probe Ollama + LM Studio, print
      a table of `(backend, reachable, model_present, base_url)`.
- [ ] `openpathai llm pull <model>` — shell out to `ollama pull`
      when ollama is the active backend; actionable message
      otherwise.
- [ ] `openpathai nl classify <image> --prompt "…" [--prompt
      "…"]` — runs zero-shot classify. Prints a JSON
      `ZeroShotResult`.
- [ ] `openpathai nl segment <image> --prompt "…"` — runs text-
      prompted segmentation. Writes the mask PNG + prints a
      `SegmentationResult` JSON.
- [ ] `openpathai nl draft "<free text>" [--out pipeline.yaml]
      [--model medgemma:1.5]` — drafts a pipeline YAML. Prints
      the YAML + the parsed `Pipeline` id.
- [ ] Both command groups register in `src/openpathai/cli/main.py`
      next to Phase-14's `detection` + `segmentation`.

### 3.3 Settings / audit integration

- [ ] `openpathai settings set llm.backend {ollama,lmstudio,auto}`
      — persists to `$OPENPATHAI_HOME/settings.toml` under a new
      `[llm]` section. (Settings store is already wired in
      Phase 7.)
- [ ] Every NL-initiated run (classify / segment / draft)
      inserts one audit row via `log_analysis` / `log_pipeline`
      whose `metrics_json` carries `nl_backend_id`,
      `nl_model_id`, `nl_prompt_hash` (SHA-256 of the prompt,
      not the raw text — PHI rule #8).
- [ ] `openpathai audit show <run_id>` automatically surfaces
      the NL metadata via the existing JSON dump path (no
      schema change needed).

### 3.4 Docs

- [ ] `docs/setup/llm-backend.md` — already exists as a stub;
      expand to cover the Phase-15 auto-detection + `openpathai
      llm status` flow.
- [ ] `docs/nl-features.md` — user guide: zero-shot classify,
      text-prompt segment, pipeline draft. Includes a worked
      example against the DINOv2 fallback (works without gated
      access).
- [ ] Phase-15 pointers in `docs/cli.md` + `docs/developer-guide.md`.
- [ ] `mkdocs.yml` — one new nav entry under Models, keep the
      Setup section's LLM-backend pointer.
- [ ] `CHANGELOG.md` — Phase 15 entry (Added / Quality /
      Deviations).

### 3.5 Smoke script

- [ ] `scripts/try-phase-15.sh` — 5-step tour:
      1. `openpathai llm status` — prints backend table.
      2. Synthetic zero-shot classify: two prompts + a tiny
         tile → prints `ZeroShotResult`.
      3. Synthetic text-prompt segment: prompt + tile →
         produces a valid mask via the fallback router.
      4. `openpathai nl draft "train resnet18 on lc25000 for 2
         epochs"` (skipped if MedGemma not reachable; prints a
         clear actionable message).
      5. Print the resulting audit rows.

### 3.6 Tests

- [ ] `tests/unit/nl/test_llm_backends.py` — LLM backend
      registry + `detect_default_backend()` under a mock httpx
      transport. Asserts `LLMUnavailableError` with an
      actionable message when neither backend is reachable.
- [ ] `tests/unit/nl/test_openai_compat.py` — mocked
      `ChatResponse` round-trip; schema validation on the
      response.
- [ ] `tests/unit/nl/test_zero_shot.py` — fallback text-encoder
      stub produces deterministic `ZeroShotResult`; top-1
      prompt matches the argmax of deterministic
      hash-distances.
- [ ] `tests/unit/nl/test_text_prompt_seg.py` — fallback
      router returns a non-empty `SegmentationResult` mask;
      prompt-hash metadata lands in the result.
- [ ] `tests/unit/nl/test_pipeline_gen.py` — mocked MedGemma
      response returns a valid YAML string → `PipelineDraft`
      parses cleanly; invalid YAML → retry loop kicks in;
      3 bad responses → raises `PipelineDraftError`.
- [ ] `tests/unit/cli/test_cli_nl.py` + `test_cli_llm.py` —
      CLI help, argument validation, end-to-end with the
      fallback backends.

---

## 4. Acceptance Criteria

- [ ] `openpathai llm status --help` exits 0 and lists
      `{ollama, lmstudio}` (ANSI-stripped).
- [ ] `openpathai nl classify --help` + `openpathai nl segment
      --help` + `openpathai nl draft --help` all exit 0.
- [ ] `openpathai nl classify <tile> --prompt "tumor" --prompt
      "normal"` returns a valid JSON `ZeroShotResult` whose
      `probs` sums to 1 within 1e-6.
- [ ] `openpathai nl segment <tile> --prompt "gland"` writes a
      mask PNG + prints a `SegmentationResult` whose mask
      shape matches the input.
- [ ] Mocked MedGemma draft test produces a YAML string that
      round-trips through `openpathai.cli.pipeline_yaml.loads_pipeline`.
- [ ] `detect_default_backend()` raises `LLMUnavailableError`
      with an actionable install message when neither Ollama
      nor LM Studio is reachable; HTTP 404 / connection-refused
      are both treated as "backend unavailable".
- [ ] Audit row per NL-initiated run carries
      `nl_backend_id` + `nl_model_id` + `nl_prompt_hash`.
- [ ] `scripts/try-phase-15.sh` runs green end-to-end.

Cross-cutting mandatories (inherited):

- [ ] `ruff check src tests` clean on new code.
- [ ] `ruff format --check src tests` clean on new code.
- [ ] `pyright src` clean on new code.
- [ ] ≥ 80 % test coverage (weighted) on `src/openpathai/nl/**`.
- [ ] CI green on macOS-ARM + Ubuntu + Windows.
- [ ] `CHANGELOG.md` entry added.
- [ ] Git tag `phase-15-complete` cut and pushed.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files Expected to be Created / Modified

**Created**

- `src/openpathai/nl/{__init__.py,zero_shot.py,text_prompt_seg.py,pipeline_gen.py}`
- `src/openpathai/nl/llm_backends/{__init__.py,base.py,openai_compat.py,ollama.py,lmstudio.py,registry.py}`
- `src/openpathai/cli/{llm_cmd.py,nl_cmd.py}`
- `docs/nl-features.md`
- `scripts/try-phase-15.sh`
- `tests/unit/nl/{__init__.py,test_llm_backends.py,test_openai_compat.py,test_zero_shot.py,test_text_prompt_seg.py,test_pipeline_gen.py}`
- `tests/unit/cli/{test_cli_llm.py,test_cli_nl.py}`

**Modified**

- `src/openpathai/cli/main.py` — register `llm` + `nl` sub-commands.
- `docs/cli.md`, `docs/developer-guide.md`, `docs/setup/llm-backend.md`, `mkdocs.yml`, `CHANGELOG.md`, `NOTICE`.
- `pyproject.toml` — add `[nl]` extra pinning `httpx>=0.27,<1` (already transitively present but documented here).

---

## 6. Commands to Run During This Phase

```bash
uv sync --extra dev --extra nl
uv run pytest tests/unit/nl tests/unit/cli/test_cli_llm.py tests/unit/cli/test_cli_nl.py -q
uv run openpathai llm status
uv run openpathai nl draft "fine-tune resnet18 on lc25000 for 2 epochs"
bash scripts/try-phase-15.sh
uv run ruff check src tests && \
uv run ruff format --check src tests && \
uv run pyright src && \
uv run pytest --tb=no -q && \
uv run mkdocs build --strict
```

---

## 7. Risks in This Phase

- **Ollama / LM Studio not installed on the CI cell.** That's
  the normal case — backends are local-only, not CI-installable.
  Mitigation: every backend-hitting test mocks the HTTP layer
  via `respx` / monkeypatching `httpx`.
- **MedGemma generates invalid YAML.** Mitigation: embed the
  pydantic schema in the system prompt + retry-on-validation-
  failure loop with the parser's error as follow-up context.
  After 3 bad responses, raise `PipelineDraftError` with the
  last LLM output so the user can salvage it manually.
- **CONCH text encoder isn't available.** Real CONCH weights
  are gated. Mitigation: fallback text-encoder stub that hashes
  prompts into fixed-dim vectors. Tests assert the interface
  and the deterministic hash; a user with real gated access
  gets the real behaviour with no code change.
- **PHI leak via prompt text.** Pathologists might paste patient
  identifiers into an NL prompt. Mitigation: audit row stores
  only `nl_prompt_hash` (SHA-256) — never the raw text. The
  `docs/nl-features.md` guide calls this out explicitly.
- **Scope creep into Phase 16.** The GUI NL prompt box + the
  Pipelines chat panel are explicitly deferred. Mitigation:
  worklog checklist item at close — no `src/openpathai/gui/*`
  edits.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · phase initialised

**What:** created from template; dashboard flipped to 🔄.
Scope framed honestly — ship the LLM-backend layer + CONCH
zero-shot + MedSAM2 text-prompt seg + MedGemma pipeline draft
behind clean library interfaces, with fallback stubs
exercisable on any CI cell. Real gated-access + real-GPU
acceptance bars deferred to user-side validation.

**Why:** Phase 15 closes Bet 2 (NL + zero-shot). The three
primitives (backend adapter, zero-shot classify, pipeline
draft) each plug into an earlier phase's protocol layer:
backend → Phase-13 FallbackDecision uniformity; classify →
Phase-13 FoundationAdapter promotion (CONCH stub → real);
pipeline draft → Phase-5 `loads_pipeline` validator.

**Next:** write the LLM backend protocol + Ollama adapter + the
registry, then zero-shot classify, then text-prompt seg, then
pipeline draft, then CLI, then docs + smoke.

**Blockers:** none; Ollama + medgemma:1.5 already installed
locally per the user's setup.
