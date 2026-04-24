# Diagnostic mode + signed manifests (Phase 17)

> **Status:** v1.0 · Bet 3 closure · local-keypair signatures ·
> future-cosign-compatible schema.

Diagnostic mode is the **strict reproducibility lane** for
OpenPathAI runs. It refuses to start unless the environment is
deterministic, then produces an Ed25519-signed manifest whose
signature can be verified by anyone who has the public key
embedded in the signature record — no network round-trip, no
external service required today.

---

## When to use it

- **Exploratory mode (default)** — interactive work, parameter
  sweeps, teaching. No enforcement; runs produce unsigned manifests.
- **Diagnostic mode** — anything that needs to pass a
  reproducibility audit: paper submissions, compliance reviews,
  multi-site trials, bug reproductions.

Switch via `Pipeline.mode: diagnostic` in your YAML or
programmatically via the `Pipeline(mode="diagnostic", …)` constructor.

---

## What diagnostic mode checks (and refuses on)

| # | Check | Error class | Bypass env var |
| - | --- | --- | --- |
| 1 | Resolvable `git HEAD` commit | `DiagnosticModeError` | `OPENPATHAI_DIAGNOSTIC_SKIP_GIT_CHECK=1` |
| 2 | Clean working tree (`git status --porcelain` empty) | `DiagnosticModeError` | same as above |
| 3 | **Every model input cites a ModelCard with `source.revision` set** | `DiagnosticModeError` | `OPENPATHAI_DIAGNOSTIC_SKIP_MODEL_PIN_CHECK=1` |

Checks 1 + 2 landed in the post-Phase-12 audit fix (commit
`2ba2f61`). Check 3 is the Phase 17 addition: without a pinned
revision, the manifest can't uniquely identify the weights that
produced the run.

### Pinning a model card

Edit the card under `models/zoo/<name>.yaml`:

```yaml
source:
  framework: timm
  identifier: resnet18
  license: Apache-2.0
  # NEW — pin to a specific git SHA or HF revision.
  revision: "abc123deadbeef"
```

The failure message points at the exact card and YAML line to
add. Once all referenced cards are pinned, the diagnostic run
proceeds.

---

## Signed manifests

Every diagnostic run (and any exploratory run that calls
`openpathai manifest sign` explicitly) produces a sibling
`manifest.signature.json` with an Ed25519 signature over the
canonical JSON dump of the manifest.

### Key layout

```
$OPENPATHAI_HOME/keys/
├── ed25519       # 32-byte raw private key; chmod 0600 on POSIX
└── ed25519.pub   # 32-byte raw public key
```

The raw-bytes format is OpenSSH / age-compatible so a future
cosign migration doesn't need a key regeneration. Windows
doesn't honour POSIX perm bits — we flip the read-only bit
(`stat.S_IREAD | S_IWRITE`) instead and document the tradeoff
here.

### Signature format

```json
{
  "manifest_hash": "sha256 hex",
  "signature_b64": "base64 ed25519 signature",
  "public_key_b64": "base64 raw public key",
  "algorithm": "ed25519",
  "signed_at": "2026-04-24T15:30:00+00:00"
}
```

The embedded `public_key_b64` means **verification doesn't need
access to the signing machine's keypair** — anyone with the
manifest + signature pair can verify.

### CLI surface

```bash
# Generate or reuse the local keypair + sign a manifest.
openpathai manifest sign /path/to/manifest.json
# → writes /path/to/manifest.signature.json

# Verify. Exit 0 on ok, 2 on mismatch.
openpathai manifest verify /path/to/manifest.json
```

---

## Methods-paragraph writer (Phase 17)

`openpathai methods write <manifest>` turns a manifest into a
copy-pasteable Methods paragraph via MedGemma (the same local
LLM backend Phase 15 wired). The paragraph is **fact-checked**
against the manifest's datasets + models: any dataset / model
mentioned in the paragraph that isn't in the manifest triggers
an automatic retry (up to 3 attempts). If the LLM keeps
inventing citations after 3 retries, the CLI exits with
`MethodsWriterError` and prints the last attempt so the user
can salvage it manually.

PHI safety:
- Audit rows carry `nl_prompt_hash` (SHA-256) — not the raw
  manifest.
- The paragraph text itself is returned to the caller, not
  auto-persisted.

---

## Relationship to real cosign / Rekor / Fulcio

Phase 17 ships a **local-keypair** signature that is
byte-compatible with a future cosign upgrade:

- `algorithm` is a field (not hard-coded), so a future
  `cosign-v2` variant can coexist.
- `manifest_hash` is canonical (sorted-key JSON, `separators=(",",":"),
  utf-8`), which matches the Rekor-log canonical-JSON rule.
- No identity / OIDC field today; a future phase can add
  `fulcio_certificate` without breaking the existing schema.

The pragmatic reason for not shipping real cosign in Phase 17:
cosign requires a Rekor log + Fulcio OIDC identity flow + a
network round-trip, none of which a single-user workstation
has by default. Local keypairs keep the iron-rule discipline
intact without forcing users through a cloud dependency.

---

## Deferred for Phase 17

- **Real sigstore / cosign network integration** — Phase 18+ when
  a user needs Rekor transparency.
- **Supply-chain verification of the `openpathai` wheel itself** —
  Phase 18 (packaging).
- **Key rotation / expiry** — one keypair per machine today;
  rotation lands with the multi-user FastAPI surface in Phase 19+.
- **Retroactive signing of pre-Phase-17 audit rows** — documented
  migration script is user-side when a user needs it.
- **HF-tip auto-fetching of model revisions** — if a card doesn't
  already declare a `source.revision`, diagnostic mode refuses.
  Walking HF for a current-tip SHA is a cloud dependency we
  deliberately skip.
