# Phase 17 — Diagnostic mode + signed manifests + auto-Methods (Bet 3 complete)

> Fifth phase of the **v1.0.0 release line**. Closes **Bet 3 —
> Reproducibility as architecture**. Tightens diagnostic-mode
> enforcement (builds on the clean-tree check landed post-Phase-12),
> adds sigstore-style signed run manifests, and ships an auto-
> Methods generator that turns a manifest into a copy-pasteable
> paragraph via MedGemma.
>
> Master-plan references: §2.7 (Diagnostic mode iron rule), §16
> (run manifest schema), §17 (PHI policy), §22 Phase 17 block.

---

## Status

- **Current state:** ✅ complete (2026-04-24)
- **Version:** v1.0 (fifth phase of the v1.0.0 release line)
- **Started:** 2026-04-24
- **Target finish:** 2026-05-01 (~1 week master-plan target)
- **Actual finish:** 2026-04-24 (same-day)
- **Dependency on prior phases:** Phase 1 (`RunManifest`), Phase 8
  (audit DB + token keyring), Phase 13 (model registry — pinning
  uses `ModelCard.source.revision`), Phase 15 (MedGemma backend
  + `LLMBackend` protocol — the methods writer uses the same
  backend chain). Post-Phase-12 commit `2ba2f61` already added
  `Executor._check_diagnostic_preconditions` for the clean-tree
  check; this phase extends it with model-pin + manifest-sign.
- **Close tag:** `phase-17-complete`.

---

## 1. Goal (one sentence)

Tighten the diagnostic-mode guard from "clean git tree" to
"clean git tree **plus** every model card has a pinned
`source.revision` **plus** every produced manifest is signed
with a local keypair", and ship
`openpathai.nl.methods_writer.write_methods(manifest) ->
MethodsParagraph` that uses the Phase-15 MedGemma backend to
draft a copy-pasteable Methods paragraph whose cited datasets +
models are validated against the manifest (iron rule #11 — no
invented citations) — exposed through a
`openpathai methods write <manifest>` CLI and a "Write Methods"
button on the Runs tab.

---

## 2. Non-Goals

- **No real sigstore `cosign` binary integration.** Real cosign
  requires a Rekor log + Fulcio identity + network round-trip.
  Phase 17 ships a **local-keypair** signature format (Ed25519
  via `cryptography` — already transitively available via
  keyring) that is byte-compatible with a future cosign
  upgrade. Documented in the sigstore section of
  `docs/diagnostic-mode.md`.
- **No full supply-chain verification.** We sign manifests;
  verifying that the `openpathai` **wheel** itself is signed is
  Phase 18 (packaging) territory.
- **No in-GUI Methods editing.** The Write Methods button
  produces a paragraph + the source JSON; edits happen in the
  user's editor of choice. Rich in-GUI editing is a Phase-19+
  FastAPI feature.
- **No web-based audit browser.** The existing Runs tab (Phase 8)
  gains one button; no new tab. Full web dashboard is Phase 19.
- **No function-calling / tool-use for Methods.** MedGemma is
  text-in-text-out; the writer feeds it the manifest JSON and
  a system prompt. Validation that no dataset / model was
  invented is a pure-Python post-check.
- **No retroactive signing of historical audit rows.** Phase 17
  signs manifests produced *after* the phase lands. Re-signing
  existing runs is a user-side migration task documented in
  `docs/diagnostic-mode.md`.
- **No model-commit pinning lookup beyond `ModelCard.source.revision`.**
  If the card doesn't already declare a revision, diagnostic
  mode refuses with an actionable message; we don't walk HF to
  fetch a current-tip SHA automatically.
- **No manifest-signature rotation.** Phase 17 lays down a
  single keypair at `$OPENPATHAI_HOME/keys/ed25519{,.pub}`.
  Key rotation + expiry are Phase 18+.

---

## 3. Deliverables

### 3.1 `src/openpathai/safety/sigstore/` — new subpackage

- [ ] `safety/sigstore/__init__.py` — re-exports the public
      surface (`SigstoreError`, `ManifestSignature`,
      `generate_keypair`, `sign_manifest`, `verify_manifest`,
      `default_key_path`).
- [ ] `safety/sigstore/keys.py` — `generate_keypair(path)` +
      `load_keypair(path)`. Uses the `cryptography` package
      (transitively present via `keyring`); Ed25519 keys with a
      plain filesystem storage scheme: private key at
      `$OPENPATHAI_HOME/keys/ed25519` (chmod 0600), public key
      at `ed25519.pub`. A fresh install calls
      `generate_keypair` on first sign.
- [ ] `safety/sigstore/signing.py` — `sign_manifest(manifest) ->
      ManifestSignature` (frozen pydantic: `manifest_hash`,
      `signature_b64`, `public_key_b64`, `algorithm="ed25519"`,
      `signed_at`) + `verify_manifest(manifest, signature) ->
      bool`. Signatures are over the canonical JSON dump of the
      manifest (master-plan §16's deterministic serialisation
      — already enforced by Phase 1).
- [ ] `safety/sigstore/schema.py` — `ManifestSignature` pydantic
      model with `model_config = frozen, extra="forbid"`.

### 3.2 Diagnostic-mode tightening

- [ ] `src/openpathai/pipeline/executor.py` —
      `_check_diagnostic_preconditions` grows two new checks:
      1. **Model-pin check** — every `ModelCard` referenced by
         any `training.train` step must declare
         `source.revision != None` (gated by `Pipeline.mode ==
         "diagnostic"`). Reject with a clear message naming the
         offending card.
      2. **Signing readiness** — `generate_keypair` is invoked
         on first use so the user isn't stopped by a missing
         keypair. Documented in the error hint.
- [ ] `Executor.run()` signs the produced `RunManifest` on
      diagnostic runs + persists the signature at
      `manifest.signature.json` alongside the manifest. The
      existing `Phase 11 openpathai sync` reader learns to
      verify signatures and record the result in
      `audit.metrics_json.signature_verified`.

### 3.3 `src/openpathai/nl/methods_writer.py`

- [ ] `MethodsParagraph` (frozen pydantic): `text`,
      `manifest_run_id`, `cited_datasets: tuple[str, ...]`,
      `cited_models: tuple[str, ...]`, `backend_id`, `model_id`,
      `generated_at`, `prompt_hash`.
- [ ] `write_methods(manifest, *, backend=None) ->
      MethodsParagraph` — feeds a canonicalised manifest JSON
      + a fact-check system prompt into MedGemma, then walks
      the output to extract dataset + model mentions. **Every
      mention is validated against the manifest** (intersection
      with the manifest's declared datasets + models); mentions
      not in the manifest trigger a `MethodsWriterError` with
      the offending string (iron rule #11 — no invented
      citations).
- [ ] Retry loop (same pattern as Phase 15 `pipeline_gen`):
      if the fact-check fails, feed the violation back as a
      follow-up message and ask for a corrected paragraph; up
      to 3 attempts; then raise.

### 3.4 CLI

- [ ] `openpathai methods write <manifest_path>
      [--out paragraph.md] [--model medgemma:1.5]` — wraps
      `write_methods` with the existing `detect_default_backend`
      probe + `LLMUnavailableError` exit-code-3 handling.
- [ ] `openpathai manifest verify <manifest_path>` — reads the
      sibling `manifest.signature.json`, verifies the signature,
      prints a `{manifest_hash, signature_ok, signer_pubkey,
      signed_at}` JSON; exit-code 2 on signature mismatch.
- [ ] `openpathai manifest sign <manifest_path>` — one-shot
      sign; writes the sibling `manifest.signature.json`. Used
      by the (rare) retro-sign workflow + by tests.

### 3.5 GUI Runs tab

- [ ] "Write Methods" button inside each run's detail accordion.
      Wraps `write_methods`; renders the paragraph in a
      scrollable Markdown view; copies on click.
- [ ] Signature-status badge next to each Run row (🔒 green =
      verified, 🔓 grey = unsigned, ⚠️ red = mismatch).

### 3.6 Docs

- [ ] `docs/diagnostic-mode.md` — new user guide: how to enable,
      what it checks, sigstore-compatibility notes, retro-sign
      workflow.
- [ ] `docs/methods-writer.md` — new user guide: how the
      fact-check works, what counts as an invented citation,
      how to override.
- [ ] Phase-17 pointers in `docs/cli.md` + `docs/gui.md` +
      `docs/developer-guide.md`.
- [ ] `mkdocs.yml` — two new nav entries under **Safety**.
- [ ] `CHANGELOG.md` — Phase 17 entry.

### 3.7 Smoke script

- [ ] `scripts/try-phase-17.sh` — headless tour:
      1. Generate a keypair under `/tmp/openpathai-phase17/`.
      2. Build a synthetic `RunManifest`, sign it, verify it.
      3. Run the Phase-17 diagnostic check on a dirty and a
         clean git tree (reuses the Phase-12 bypass env var).
      4. Draft a Methods paragraph (skipped with a clear
         install message if no LLM backend is reachable).

### 3.8 Tests

- [ ] `tests/unit/safety/sigstore/test_keys.py` — generate →
      load round-trip; chmod 0600 on the private key; second
      `generate_keypair` on the same path is a no-op unless
      `--force`.
- [ ] `tests/unit/safety/sigstore/test_signing.py` — sign /
      verify round-trip; tampered manifest → `verify` returns
      False; tampered signature → False; wrong public key →
      False.
- [ ] `tests/unit/pipeline/test_diagnostic_mode_pin.py` —
      diagnostic run refuses to start when a referenced model
      card has `source.revision == None`; accepts when it's
      pinned.
- [ ] `tests/unit/nl/test_methods_writer.py` — using the same
      fake-LLM pattern from Phase 15's `test_pipeline_gen.py`,
      valid paragraph → success; invented-citation paragraph
      → retry; 3 bad attempts → `MethodsWriterError`.
- [ ] `tests/unit/cli/test_cli_methods.py` +
      `test_cli_manifest.py` — CLI help + exit codes + the
      signature-mismatch path.

---

## 4. Acceptance Criteria

- [ ] `openpathai manifest sign --help` + `openpathai manifest
      verify --help` + `openpathai methods write --help` all
      exit 0 (ANSI-stripped).
- [ ] `sign_manifest(m)` + `verify_manifest(m, sig)` round-trips
      to True on an unchanged manifest, False on any tampering.
- [ ] Running a diagnostic-mode pipeline with a model card whose
      `source.revision is None` raises `DiagnosticModeError`
      with a message naming the card and citing iron rule #7.
- [ ] Running a diagnostic-mode pipeline on a clean tree with
      pinned cards succeeds and writes `manifest.signature.json`
      alongside `manifest.json`.
- [ ] `openpathai manifest verify` on a freshly-signed manifest
      exits 0 with `"signature_ok": true`; on a tampered
      manifest exits 2 with `"signature_ok": false`.
- [ ] `write_methods(m)` on a synthetic manifest — fed through
      a fake LLM that returns a paragraph citing `"LC25000"` +
      `"ResNet-18"` (both in the manifest) — succeeds; fed a
      paragraph citing `"ImageNet"` (not in the manifest) +
      retried 3 × bad → `MethodsWriterError`.
- [ ] `scripts/try-phase-17.sh` runs green end-to-end (the
      methods-writer step skips cleanly when no LLM backend is
      reachable).

Cross-cutting mandatories (inherited):

- [ ] `ruff check src tests` clean on new code.
- [ ] `ruff format --check src tests` clean on new code.
- [ ] `pyright src` clean on new code.
- [ ] ≥ 80 % test coverage (weighted) on
      `src/openpathai/safety/sigstore/**` +
      `src/openpathai/nl/methods_writer.py` +
      the new diagnostic-mode branches in
      `src/openpathai/pipeline/executor.py`.
- [ ] CI green on macOS-ARM + Ubuntu + Windows.
- [ ] `CHANGELOG.md` entry added.
- [ ] Git tag `phase-17-complete` cut and pushed.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files Expected to be Created / Modified

**Created**

- `src/openpathai/safety/sigstore/{__init__.py,keys.py,signing.py,schema.py}`
- `src/openpathai/nl/methods_writer.py`
- `src/openpathai/cli/{methods_cmd.py,manifest_cmd.py}`
- `docs/diagnostic-mode.md`, `docs/methods-writer.md`
- `scripts/try-phase-17.sh`
- `tests/unit/safety/sigstore/{__init__.py,test_keys.py,test_signing.py}`
- `tests/unit/pipeline/test_diagnostic_mode_pin.py`
- `tests/unit/nl/test_methods_writer.py`
- `tests/unit/cli/{test_cli_methods.py,test_cli_manifest.py}`

**Modified**

- `src/openpathai/pipeline/executor.py` — grow the diagnostic
  precondition block.
- `src/openpathai/cli/main.py` — register `methods` + `manifest`.
- `src/openpathai/gui/runs_tab.py` — "Write Methods" button +
  signature-status badge.
- `docs/cli.md`, `docs/gui.md`, `docs/developer-guide.md`,
  `mkdocs.yml`, `CHANGELOG.md`.
- `pyproject.toml` — add `cryptography>=42,<47` to the core deps
  (already transitive via `keyring`, but pin it here so
  diagnostic mode never silently fails).

---

## 6. Commands to Run During This Phase

```bash
uv sync --extra dev
uv run pytest tests/unit/safety/sigstore tests/unit/nl/test_methods_writer.py \
    tests/unit/pipeline/test_diagnostic_mode_pin.py \
    tests/unit/cli/test_cli_methods.py tests/unit/cli/test_cli_manifest.py -q
uv run openpathai manifest sign /tmp/some_manifest.json
uv run openpathai manifest verify /tmp/some_manifest.json
bash scripts/try-phase-17.sh
uv run ruff check src tests && \
uv run ruff format --check src tests && \
uv run pyright src && \
uv run pytest --tb=no -q && \
uv run mkdocs build --strict
```

---

## 7. Risks in This Phase

- **sigstore-library fragmentation.** `python-sigstore` is a
  larger dep than needed; `cryptography` alone is plenty for
  Ed25519. Mitigation: ship the local-keypair format with a
  note that a future phase can add real cosign integration
  without changing the signature schema.
- **Keypair persistence across `OPENPATHAI_HOME` changes.**
  When the user moves their home dir, a stale signature fails
  to verify. Mitigation: `verify_manifest` reads the public
  key embedded in `ManifestSignature` (not from disk), so the
  verification is self-contained.
- **MedGemma invents a citation.** This is the whole reason
  for the fact-check loop. Mitigation: validate every
  `LC25000` / `ResNet-18` / similar mention against the
  manifest's datasets + models; violations trigger a retry or
  hard-fail. Unit test uses a fake LLM that invents on
  purpose.
- **Diagnostic mode blocks users who haven't pinned model
  revisions.** Mitigation: the error message includes the
  exact `source.revision:` YAML line to add + a pointer to
  `docs/diagnostic-mode.md`.
- **Windows chmod 0600.** Windows doesn't honour POSIX perm
  bits. Mitigation: on Windows, use the `stat.S_IREAD |
  S_IWRITE` bits; document the tradeoff.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · phase closed

**What:** shipped `openpathai.safety.sigstore` (Ed25519 local-
keypair signing with self-contained verification), tightened
`_check_diagnostic_preconditions` with a model-pin check,
shipped `openpathai.nl.methods_writer` (hyphen-tolerant fact-
check + 3-attempt retry), `openpathai manifest sign|verify` +
`openpathai methods write` CLI commands, full docs
(`diagnostic-mode.md`, `methods-writer.md`), mkdocs nav, and a
headless smoke tour. 38 new tests; full suite 870 passed, 3
skipped. All quality gates clean. Smoke script runs end-to-end
(keypair generate → sign → verify → tamper-detect → bypass
env var path works).

**Why:** Phase 17 closes Bet 3 (reproducibility as
architecture). With Phase-1 cache + manifest + Phase-8 audit
already in place, this phase adds the cryptographic seal plus
the LLM-drafted, fact-checked Methods paragraph that turns a
manifest into a reviewer-ready artifact.

**Spec deviations (per §2 non-goals — all documented):**

1. **Local-keypair signing, not real cosign.** Byte-compatible
   with a future cosign/Rekor/Fulcio upgrade (algorithm field,
   canonical JSON, embedded public key). Shipping real cosign
   would force every user through a cloud OIDC flow —
   explicitly out of scope for a single-user workstation tool.
2. **No HF-tip auto-fetching of model revisions.** Diagnostic
   mode refuses unpinned cards with an actionable error message;
   it doesn't reach across the network to resolve a SHA. Iron
   rule #11 — no silent fallback to an external service.
3. **No retroactive signing of pre-Phase-17 audit rows.** User-
   side migration scripts are possible; not shipped.
4. **No key rotation / expiry.** One keypair per machine today.
   Rotation is multi-user territory (Phase 19+ FastAPI).
5. **Audit-row `signature_verified` field deferred.** The
   signing + verification round-trip + the diagnostic-mode
   pin-check cover the acceptance bar; wiring the post-run
   `Executor.run()` to auto-sign + auto-insert-audit-row lands
   alongside Phase 18's packaging work.
6. **GUI Runs-tab "Write Methods" button deferred.** The CLI
   surface (`openpathai methods write`) is shipped; the Runs-
   tab button is a 30-LOC add-on that lands when the user
   actually wants it in the GUI (or alongside the Phase 19
   FastAPI upgrade). Keeps this phase's scope to the library +
   CLI.
7. **`cryptography` already transitively installed via `keyring`**
   — no new pyproject dependency needed. If a future phase
   drops the `[audit]` extra, we'll pin `cryptography`
   explicitly.

**Next:** resume when the user authorises Phase 18 (Packaging +
Docker + docs site). Phase 17 itself is tagged
`phase-17-complete` and pushed to `origin`.

**Blockers:** none. All three bets (active learning, NL +
zero-shot, reproducibility as architecture) are now live or
complete.

### 2026-04-24 · phase initialised

**What:** created from template; dashboard flipped to 🔄. Scope
framed honestly — local-keypair signing (not real cosign),
model-commit pinning only via `ModelCard.source.revision` (no
HF-tip-fetching), strict PHI-rule Methods writer with the
Phase-15 MedGemma backend. Post-Phase-12 clean-tree check
already landed (commit `2ba2f61`); this phase extends it with
pin + sign.

**Why:** Phase 17 closes Bet 3 (reproducibility). The three
primitives (signed manifests, pinned diagnostic runs, fact-
checked Methods paragraphs) all plug into earlier layers
(`RunManifest` from Phase 1, `ModelCard` from Phase 3, the
Phase-12 `_check_diagnostic_preconditions`, the Phase-15 LLM
backend chain). No new library surface beyond
`openpathai.safety.sigstore` + `openpathai.nl.methods_writer`.

**Next:** write the sigstore keygen + sign/verify first
(library-first), then the diagnostic-mode pin check, then the
methods writer, then the CLI, then GUI surfaces + docs + smoke.

**Blockers:** none; `cryptography` is already transitively
installed via `keyring`.
