# Methods writer (Phase 17)

> **Status:** v1.0 · MedGemma-driven · fact-checked against the
> source manifest · iron rule #11 (no invented citations).

The Methods writer turns a run manifest into a copy-pasteable
paragraph suitable for a paper's Methods section. It's part of
Bet 3 (reproducibility as architecture): a reviewer can trust
the paragraph because every dataset + model mention is
validated against the manifest before the paragraph leaves the
function.

---

## Quick start

```bash
openpathai methods write /path/to/manifest.json \\
    --out /tmp/methods.md
```

Outputs JSON metadata to stdout + the paragraph itself on
stderr (so shell redirection lets you split them). The
`--out` path receives the paragraph as Markdown.

---

## The fact-check loop

Every draft goes through:

1. `extract_manifest_entities(manifest)` — walks the manifest
   for any key in `{dataset, dataset_id, datasets, cohort}` or
   `{model, model_id, models, backbone, backbone_id,
   classifier}` and collects the values into two sets.
2. The LLM writes a paragraph.
3. `_fact_check` scans the paragraph for PascalCase / hyphenated
   tokens that look like dataset / model names (heuristic: contain
   a digit or a hyphen — `ResNet-18`, `LC25000`, `Camelyon-16`,
   etc.).
4. Every such token is normalised (hyphens, spaces, underscores
   dropped, lowercased) and checked against the manifest
   vocabularies. Any unmatched token triggers a retry: the
   paragraph is fed back to the LLM with a follow-up message
   naming the offending strings, and the LLM is asked to
   produce a corrected paragraph.
5. After :data:`MAX_ATTEMPTS` (`= 3`) bad attempts, the writer
   raises :class:`MethodsWriterError` with the last LLM output
   so the user can salvage it manually.

---

## What counts as "invented"

- `ResNet-18` → matches `resnet18` in the manifest (hyphen-
  tolerant). Not invented.
- `LC25000` → matches `lc25000`. Not invented.
- `Camelyon-16` → not in the manifest → **invented**.
- `We`, `Methods`, `Results`, `PyTorch`, `CUDA`, `H&E` → in the
  common-words allow-list; not flagged.
- Bare `PyTorch` without a digit / hyphen → skipped (prose,
  not a model-id).

The heuristic is intentionally conservative: it flags likely
dataset / model ids, not every capitalised word. False
positives are fixed by the retry loop; false negatives (real
invented names that look like prose) are rare in practice
because medical-imaging datasets almost always carry a digit
or hyphen.

---

## PHI safety

- The manifest text is hashed (SHA-256, first 16 hex chars) and
  the hash is what lands in audit rows. Raw manifest content is
  never persisted outside the run directory.
- The paragraph itself is returned to the caller; no
  `AuditDB.insert_run` side-effect from `write_methods`.
- If a pathologist's prompt accidentally references patient
  identifiers (shouldn't happen because the prompt is the
  manifest, not the pathologist's notes), the identifiers end
  up in the paragraph but not in the audit DB.

---

## Bring your own backend

`write_methods(manifest, *, backend=...)` accepts any
:class:`openpathai.nl.LLMBackend` conformer — the shipped ones
are `OllamaBackend` (default) and `LMStudioBackend`. Wiring a
custom backend looks like the Phase-15 LLM-backend example:
subclass `OpenAICompatibleBackend` with the correct `base_url`
+ probe path, then pass the instance in.

---

## Deferred for Phase 17

- **Function calling / structured output** — MedGemma's current
  chat-completions path is text-in-text-out. A future phase may
  use JSON-mode when a backend supports it.
- **In-GUI Methods editing** — the paragraph renders in the
  Runs-tab detail accordion (Phase 17 GUI surface), but edits
  happen in the user's editor of choice. Rich in-GUI editing is
  Phase 19 FastAPI territory.
- **Citation-style variants** — today's paragraph is neutral
  prose. Journal-specific templates (Nature, CVPR, JAMA) can
  land as system-prompt presets in a future phase.
