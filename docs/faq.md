# FAQ

## Install + runtime

### Does OpenPathAI require a GPU?

No. The torch-training path (`openpathai train`) uses a GPU
when one is available (CUDA or Apple MPS), falls back to CPU
otherwise. Every other CLI command and every GUI tab works
without torch — the `[train]` extra is opt-in.

### Can I run it inside Docker without a GPU?

Yes. `Dockerfile.cpu` skips the CUDA base entirely:

```bash
docker build -f docker/Dockerfile.cpu -t openpathai:cpu .
docker run --rm -p 7860:7860 openpathai:cpu gui --host 0.0.0.0
```

The CPU image is ~350 MB and boots in a few seconds.

### What's the `[audit]` extra for?

The Phase-8 audit DB delete path is guarded by a keyring-
backed token so nobody accidentally wipes history. Installing
`[audit]` pulls `keyring>=24,<26` + `cryptography` and lets the
GUI's Settings → Delete-history accordion work. Everything else
audit-related (inserts, queries, diff) works without the
extra.

### Why are there so many optional extras?

Each extra is a hard dependency of a specific feature
(`[train]` → torch + lightning + timm; `[gui]` → gradio;
`[explain]` → pytorch-grad-cam + captum). Splitting them keeps
the minimal install small (~ 50 MB) and lets users opt in to
the heavy bits only when they need them.

### Does OpenPathAI work on Windows?

Best-effort. CI runs the full test suite on Windows
`python 3.11`, so the library itself is Windows-compatible.
Known footguns (all fixed in `main`):

- `os.replace` on Windows can raise `ERROR_ACCESS_DENIED`
  when Defender holds a file. The cache retries with backoff
  (commit `370a5fb`).
- `pipx` + Microsoft-Store Python sometimes needs `pipx
  ensurepath` + terminal restart.
- `chmod 0600` on the sigstore private key falls back to
  `S_IREAD | S_IWRITE`.

---

## Gated access + fallback

### How do I get access to UNI / CONCH / Virchow2 / MedSAM2?

Visit the model's Hugging Face page, accept the licence, and
wait for MahmoodLab / Paige / wanglab approval (hours to
days). Then:

```bash
export HUGGINGFACE_HUB_TOKEN=hf_...
openpathai foundation resolve uni   # reason should become "ok"
```

Without a token, every gated call routes to the fallback —
DINOv2 for classification, SyntheticClickSegmenter for
promptable segmentation. The CLI / GUI / audit row all record
the actually-used model (iron rule #11).

### What does "fallback" actually do?

`resolve_backbone("uni")` without HF access returns a frozen
`FallbackDecision(resolved_id="dinov2_vits14", reason="hf_token_missing", …)`.
Every downstream consumer (linear probe, Annotate tab, audit
row) then uses DINOv2 instead. The user-facing banner in the
CLI / GUI surfaces the swap so there's no silent degradation.

---

## Reproducibility

### What does "diagnostic mode" actually enforce?

Three checks on `Executor.run()` when `Pipeline.mode ==
"diagnostic"`:

1. Resolvable `git HEAD` commit (the manifest pins it).
2. Clean working tree (`git status --porcelain` empty).
3. Every `ModelCard.source.revision` referenced by the
   pipeline is non-empty.

Failure raises `DiagnosticModeError` with an actionable
message. Opt-out env vars exist
(`OPENPATHAI_DIAGNOSTIC_SKIP_GIT_CHECK`,
`OPENPATHAI_DIAGNOSTIC_SKIP_MODEL_PIN_CHECK`) for niche
scenarios like distroless containers or CI pre-push hooks.

Full spec: [`diagnostic-mode.md`](diagnostic-mode.md).

### How do I rotate my signing keypair?

The Phase-17 keypair lives at
`$OPENPATHAI_HOME/keys/ed25519{,.pub}`. Rotate by deleting
both files + re-signing any manifests you want to keep
canonical:

```bash
rm "$OPENPATHAI_HOME/keys/ed25519"{,.pub}
openpathai manifest sign /path/to/manifest.json   # regenerates the keypair
```

Old signatures remain valid because each `ManifestSignature`
carries its own public key. Verification of an older manifest
uses the old public key it was signed with, not your current
one.

### Can I verify a manifest someone else signed?

Yes — the signature record carries the public key inline. You
don't need access to the signer's keypair:

```bash
openpathai manifest verify colleague-manifest.json
```

Exit 0 on match, 2 on mismatch.

### Does `openpathai methods write` invent citations?

No. The Methods paragraph is fact-checked against the
manifest's dataset + model vocabularies before returning. Any
PascalCase / hyphenated token that looks like a dataset / model
id but isn't in the vocabulary triggers a retry; 3 bad drafts
raise `MethodsWriterError` with the last LLM output so you can
salvage manually.

Matching is hyphen-tolerant (`ResNet-18` ↔ `resnet18`) and
has a small allow-list for common capitalised prose words
(`We`, `Methods`, `PyTorch`, etc.).

---

## PHI + privacy

### Are filenames stored in the audit DB?

No. Phase-8's `hash_filename()` hashes the basename only, so
the audit row stores a SHA-256 hex digest instead of the real
path. Parent directories are separately redacted via
`redact_manifest_path()` (Phase-16 audit-hardening fix).

### Are my NL prompts stored?

Only hashed. Every `openpathai nl classify/segment/draft` call
records a `prompt_hash` (SHA-256, first 16 hex chars). The raw
prompt text never lands in `audit.db`.

### Do cloud LLMs ever see my pathology data?

No. OpenPathAI's NL backend layer probes **localhost-only** —
Ollama at `:11434` and LM Studio at `:1234`. Cloud backends
(OpenAI, Anthropic, Gemini, …) are explicit non-goals for
Phase 15. If a user wants one in a future phase it will ship
as an opt-in extra with a prominent `NOTICE` banner.

---

## Contributing

### Where are the tests?

`tests/` has three tiers:

- `tests/unit/<subsystem>/` — fast, no-network, no-GPU tests.
- `tests/integration/` — end-to-end pipeline runs through the
  executor (torch-gated).
- `tests/fixtures/` — auto-generated synthetic WSIs + tiles.

`uv run pytest --tb=no -q` runs the full suite (takes ~10 s on
a laptop without torch, ~40 s with).

### How do I add a new foundation adapter?

1. Create `src/openpathai/foundation/<name>.py` with a class
   whose attribute block matches the `FoundationAdapter`
   protocol (`id`, `gated`, `hf_repo`, `input_size`,
   `embedding_dim`, `license`, `citation`, +
   `build / preprocess / embed`).
2. Register it in
   `src/openpathai/foundation/registry.py::default_foundation_registry()`.
3. Add a YAML card under `models/zoo/foundation/<name>.yaml`.
4. Write a test in `tests/unit/foundation/`.

See [Foundation models](foundation-models.md) for the full
protocol.

### How do I close a phase?

See `docs/planning/phases/README.md` § "How to move the
needle". Every phase has a spec + acceptance criteria +
worklog; closing flips the status to ✅, tags
`phase-XX-complete`, and updates the dashboard.
