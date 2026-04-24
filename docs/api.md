# OpenPathAI API (Phase 19 — v2.0 backbone)

> **Status:** Phase 19 ships the backend. The Phase-20 React canvas is
> what actually drives most of these endpoints — Phase 19 on its own is
> usable via `curl` / the `/docs` interactive explorer.

---

## Quick start

```bash
# Install
uv sync --extra server
# …or: pip install "openpathai[server]"

# Launch (loopback, auto-generated token printed to stderr)
openpathai serve

# Pin the token so scripts can reuse it
export OPENPATHAI_API_TOKEN="$(openssl rand -hex 32)"
openpathai serve --port 7870

# Interactive API explorer
open http://127.0.0.1:7870/docs

# Health probe (no auth)
curl http://127.0.0.1:7870/v1/health

# Authenticated request
curl -H "Authorization: Bearer $OPENPATHAI_API_TOKEN" \
     http://127.0.0.1:7870/v1/nodes
```

---

## Auth

Every endpoint under `/v1` except `/v1/health` + `/v1/version` requires a
`Authorization: Bearer <token>` header. The token is set at startup via:

1. `--token <value>` on the CLI; or
2. the `OPENPATHAI_API_TOKEN` environment variable; or
3. a fresh random token auto-generated on startup (printed to stderr).

The server uses `secrets.compare_digest` so invalid tokens cannot be
timed-attacked one character at a time.

**Non-goal:** multi-user / role-based auth. One token per deployment;
revoke by restarting with a new one. Multi-tenant auth is a v2.5+ item.

---

## Endpoints (v1)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/health` | Liveness probe (no auth). |
| `GET` | `/v1/version` | Installed `openpathai` version + API version. |
| `GET` | `/v1/nodes` | Every registered `@openpathai.node`, with its pydantic input / output JSON schemas. |
| `GET` | `/v1/nodes/{id}` | One node definition. |
| `GET` | `/v1/models` | Flat merge of the classifier zoo + foundation / detection / segmentation registries. `?kind=foundation` filters. |
| `GET` | `/v1/models/{id}` | One model by id (searches every registry). |
| `GET` | `/v1/datasets` | Dataset cards. |
| `GET` | `/v1/datasets/{id}` | One dataset card. |
| `GET` | `/v1/pipelines` | List saved pipelines (on disk under `$OPENPATHAI_HOME/pipelines/`). |
| `GET` | `/v1/pipelines/{id}` | Retrieve a saved pipeline (YAML-backed, JSON on the wire). |
| `PUT` | `/v1/pipelines/{id}` | Create or replace a saved pipeline. |
| `DELETE` | `/v1/pipelines/{id}` | Delete a saved pipeline. |
| `POST` | `/v1/pipelines/validate` | Validate a pipeline payload without persisting it. |
| `POST` | `/v1/runs` | Enqueue a pipeline for async execution. 202 Accepted. |
| `GET` | `/v1/runs` | List recent in-memory job records. |
| `GET` | `/v1/runs/{run_id}` | Poll run status. |
| `GET` | `/v1/runs/{run_id}/manifest` | Full `RunManifest` (PHI already stripped). 409 if still running. |
| `DELETE` | `/v1/runs/{run_id}` | Cancel a queued / running run. |
| `GET` | `/v1/audit/runs` | Phase-8 audit DB — recent runs. |
| `GET` | `/v1/audit/runs/{id}` | One audit row. |
| `GET` | `/v1/audit/analyses` | Phase-8 audit DB — analyses. |
| `POST` | `/v1/nl/draft-pipeline` | MedGemma-drafted pipeline YAML. **Never runs it** (iron rule #9). |
| `POST` | `/v1/nl/classify` | CONCH zero-shot classification (base64 tile). |
| `POST` | `/v1/nl/segment` | MedSAM2 text-prompted mask (RLE-encoded). |
| `POST` | `/v1/manifest/sign` | Sign a manifest payload via Phase-17 Ed25519. |
| `POST` | `/v1/manifest/verify` | Verify a signed manifest payload. |

Full JSON schemas live at `/openapi.json`. Interactive explorer at
`/docs` (Swagger) and `/redoc`.

---

## Iron rules

### #1 library-first

Every route is a thin shell over a library call. There is no raw-Python
path; `/v1/runs` dispatches through the same typed `Executor` the CLI
uses. `POST /v1/nl/draft-pipeline` never chains into `/v1/runs` — the
drafted YAML is returned to the caller for human review (#9).

### #8 no PHI in plaintext

Two layers:

1. **Schema layer** — pydantic response models omit raw filesystem path
   fields or route them through `redact_manifest_path`. The Cohorts tab
   pattern (hash `patient_id`, keep basename + parent hash) applies.
2. **Network layer** — a response-body middleware scans every JSON body
   for Unix (`/Users/`, `/home/`, `/root/`) and Windows (`C:\…`) paths
   and rewrites them to `basename#<sha256[:8]>`. JSON escape sequences
   (`"is:\n"`, `"x:\t"`) are exempted so dataset prose doesn't
   false-positive.

Tests at `tests/unit/server/test_phi_boundary.py` regex-assert that no
raw path survives to the wire on any route.

### #9 never auto-execute LLM-generated pipelines

`POST /v1/nl/draft-pipeline` returns the YAML + `prompt_hash` only. The
raw prompt is never echoed back (it may contain PHI). Clients must
explicitly call `POST /v1/pipelines/validate` + `PUT /v1/pipelines/{id}`
+ `POST /v1/runs` to actually run the drafted pipeline. That three-step
gap is the human-review checkpoint.

### #11 no silent fallbacks

`/v1/runs/{id}/manifest` returns the same `RunManifest` the library
produces — the `resolved_*_id` + `fallback_reason` fields are
preserved. Any run that fell back to a substitute model carries that
fact through to the audit DB and to the React canvas.

---

## CORS

Default CORS allows:

- `http://localhost:5173` (Vite dev)
- `http://127.0.0.1:5173`
- `http://localhost:4173` (Vite preview)
- `http://127.0.0.1:4173`

Add more with `--cors-origin https://your-domain.example`. Credentials
are allowed (cookies can be sent), which matters when the Phase-20
canvas is served from the same origin.

---

## Concurrency

The Phase-19 executor is a `concurrent.futures.ThreadPoolExecutor` with
`max_concurrent_runs=1` by default. Pipelines that internally fan out
(e.g. `parallel_mode="thread"`) still get their inner concurrency; the
outer limit caps how many distinct `POST /v1/runs` requests can be
in-flight simultaneously. Raise via `ServerSettings` or a future
`--max-workers` CLI flag.

Distributed execution (RunPod / k8s job runners) is a v2.5+ item
— Phase 19 keeps everything single-process for simplicity.

---

## Deployment notes

- Loopback by default (`127.0.0.1`). Pass `--host 0.0.0.0` only behind
  a trusted reverse proxy; iron rule #8 requires same-host NL traffic
  unless `OPENPATHAI_ALLOW_REMOTE_LLM=1`.
- The server reuses the Phase-8 audit DB at `$OPENPATHAI_HOME/audit.db`
  and the Phase-17 keypair at `$OPENPATHAI_HOME/keys/`.
- No database migrations — pipelines are YAML on disk, runs are
  in-memory (until Phase 22+).

---

## Future phases

- **Phase 20** — React + React Flow canvas consuming every endpoint
  listed above. Auto-generates node palettes from `/v1/nodes`.
- **Phase 21** — OpenSeadragon WSI viewer + heatmap overlay + run-audit
  modal; adds DZI tile serving at `/v1/slides/{id}/tiles/…`.
