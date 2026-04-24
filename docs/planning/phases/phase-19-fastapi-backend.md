# Phase 19 — FastAPI backend for canvas

---

## Status

- **Current state:** ✅ complete (2026-04-24, tag `phase-19-complete`)
- **Version:** v2.0 (first of three phases: 19 backend · 20 React canvas · 21 viewer)
- **Started:** 2026-04-24
- **Target finish:** 2–3 w
- **Actual finish:** 2026-04-24 (same-day)
- **Dependency on prior phases:** Phase 1 (pipeline primitives), Phase 2 (datasets), Phase 3 (models), Phase 7 (safety v1), Phase 8 (audit DB), Phase 9 (cohorts), Phase 12 (active learning), Phase 13 (foundation), Phase 14 (detection/segmentation), Phase 15 (NL + LLM backends), Phase 17 (sigstore + diagnostic).

---

## 1. Goal (one sentence)

> Ship a FastAPI application that exposes the v1 library surface — node
> catalog, model + dataset registries, pipeline CRUD, async run execution,
> audit-log reads, and the NL primitives — as a versioned `/v1` JSON API
> ready for the Phase-20 React canvas to consume.

---

## 2. Non-Goals

- **No React frontend.** That is Phase 20. Phase 19 ships the backend +
  OpenAPI docs only.
- **No OpenSeadragon / DZI tile serving.** That is Phase 21.
- **No multi-tenant user accounts.** Phase 19 is single-tenant (one
  shared bearer token from config). Multi-user auth is a v2.5+ concern.
- **No database migrations.** Re-use the Phase-8 audit SQLite DB as-is;
  new persistence (pipelines, saved drafts) goes to the filesystem under
  `$OPENPATHAI_HOME`.
- **No WebSocket streaming.** Phase 19 ships polling + (optional) SSE
  for run status; WebSockets wait for Phase 20 if React needs them.
- **No sigstore signing of API responses.** Manifest signing stays at
  the library layer (Phase 17); the API returns signatures when they
  already exist, never issues them on response.
- **No GPU scheduling / multi-runner fan-out.** The Phase-19 executor is
  the Phase-10 in-process thread-pool. Distributed execution is v2.5+.
- **No arbitrary Python eval / notebook-over-HTTP.** The only way to
  execute code is via a registered pipeline YAML going through the
  typed executor — iron rule #1 (library-first).

---

## 3. Deliverables (checklist)

- [ ] `[server]` extra in `pyproject.toml` pulling `fastapi` + `uvicorn[standard]`.
- [ ] `src/openpathai/server/__init__.py` — package marker + `create_app()` re-export.
- [ ] `src/openpathai/server/config.py` — `ServerSettings` pydantic model (host, port, token, cors origins, OPENPATHAI_HOME).
- [ ] `src/openpathai/server/auth.py` — bearer-token dependency + 401 handler.
- [ ] `src/openpathai/server/app.py` — `create_app(settings)` factory; mounts `/v1` router; wires CORS + OpenAPI metadata.
- [ ] `src/openpathai/server/schemas.py` — shared response models (pagination envelope, error envelope, health, version).
- [ ] `src/openpathai/server/routes/health.py` — `/v1/health`, `/v1/version`.
- [ ] `src/openpathai/server/routes/nodes.py` — `/v1/nodes`, `/v1/nodes/{id}`: returns node id + input + output JSON schemas (from pydantic) so the React canvas can auto-derive node palettes.
- [ ] `src/openpathai/server/routes/models.py` — `/v1/models`, `/v1/models/{id}`: unified view across classification zoo + foundation + detection + segmentation registries.
- [ ] `src/openpathai/server/routes/datasets.py` — `/v1/datasets`, `/v1/datasets/{id}`: dataset cards.
- [ ] `src/openpathai/server/routes/pipelines.py` — CRUD against `$OPENPATHAI_HOME/pipelines/`. `POST /v1/pipelines/validate` for dry-run. YAML is the storage format; JSON is the wire format.
- [ ] `src/openpathai/server/routes/runs.py` — `POST /v1/runs` (async enqueue), `GET /v1/runs`, `GET /v1/runs/{run_id}` (status + cached NodeRunRecord list), `GET /v1/runs/{run_id}/manifest`, `DELETE /v1/runs/{run_id}` (cancel if queued/running).
- [ ] `src/openpathai/server/routes/audit.py` — read-only passthrough to the Phase-8 audit DB (`/v1/audit/runs`, `/v1/audit/analyses`, `/v1/audit/runs/{id}/diff/{other_id}`).
- [ ] `src/openpathai/server/routes/nl.py` — `POST /v1/nl/classify`, `/v1/nl/segment`, `/v1/nl/draft-pipeline`. `draft-pipeline` **never** triggers a run — iron rule #9.
- [ ] `src/openpathai/server/routes/manifest.py` — `POST /v1/manifest/sign`, `POST /v1/manifest/verify` via Phase-17 sigstore.
- [ ] `src/openpathai/server/jobs.py` — in-process `JobRunner` (thread-pool) with `submit`, `get`, `list`, `cancel`. Jobs have `run_id`, `status`, `started_at`, `ended_at`, `error`, `manifest_path`.
- [ ] `src/openpathai/server/phi.py` — response-serialisation boundary helpers that redact paths + patient_ids before JSON goes out (iron rule #8).
- [ ] `src/openpathai/cli/serve_cmd.py` — `openpathai serve` → uvicorn with the factory.
- [ ] `tests/unit/server/*` — httpx AsyncClient tests for every route; token-auth, CORS, 404, 422, 401, 403; async job lifecycle.
- [ ] `docs/api.md` — user-facing API reference; OpenAPI URL.
- [ ] `docs/planning/phases/phase-19-fastapi-backend.md` — this file.
- [ ] `docs/planning/phases/README.md` — dashboard updated (flip 19 → active / complete).
- [ ] `CHANGELOG.md` — Phase 19 entry.

---

## 4. Acceptance Criteria

- [ ] `openpathai serve --port 7870 --token test` boots a live app in < 3 s.
- [ ] `GET /v1/health` returns 200 without auth; every other endpoint returns 401 without a valid `Authorization: Bearer <token>` header.
- [ ] `GET /v1/nodes` returns the full `@openpathai.node` catalog; each node has `id`, `input_schema` (JSON schema), `output_schema`, `code_hash`, and a short description.
- [ ] `GET /v1/models` returns models from **all** registries (classification zoo, foundation, detection, segmentation) flattened with a `kind` field; filter query `?kind=foundation` narrows.
- [ ] `GET /v1/datasets` returns the registered dataset cards.
- [ ] `POST /v1/pipelines` validates the payload via the Phase-1 `Pipeline` pydantic model; invalid payloads return 422 with field-level errors.
- [ ] `GET /v1/pipelines/{id}` returns the YAML round-tripped to JSON.
- [ ] `POST /v1/runs` enqueues a job and returns 202 with `{run_id, status: "queued"}` in ≤ 50 ms; `GET /v1/runs/{run_id}` transitions to `running` then `success`; `GET /v1/runs/{run_id}/manifest` returns a PHI-redacted `RunManifest` JSON.
- [ ] `POST /v1/runs` with `mode: "diagnostic"` enforces clean git tree + model pins; dirty tree returns 409.
- [ ] `POST /v1/nl/draft-pipeline` returns the drafted YAML and the `prompt_hash`; **no `run_id` is issued**, **no prompt is echoed back**.
- [ ] `GET /v1/audit/runs?limit=10` returns rows from the Phase-8 audit DB; `manifest_path` field is already redacted.
- [ ] Response bodies never contain absolute filesystem paths (checked via a regex test): no `/Users/`, `/home/`, `C:\`, `~/`. Only `<basename>#<hash>` forms.
- [ ] CORS allows `http://localhost:5173` (Vite default) by default; configurable.
- [ ] OpenAPI docs at `/docs` render without error; schema at `/openapi.json` validates.
- [ ] ≥ 80 % test coverage on `src/openpathai/server/*`.
- [ ] `ruff check` clean on new code.
- [ ] `pyright` clean on new code.
- [ ] `uv run pytest` green.
- [ ] CI green on macOS-ARM + Ubuntu (Windows best-effort).
- [ ] `CHANGELOG.md` Phase-19 entry added.
- [ ] `docs/api.md` published.
- [ ] Git tag `phase-19-complete` cut.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files Expected to be Created / Modified

Created:

- `src/openpathai/server/__init__.py`
- `src/openpathai/server/app.py`
- `src/openpathai/server/config.py`
- `src/openpathai/server/auth.py`
- `src/openpathai/server/schemas.py`
- `src/openpathai/server/jobs.py`
- `src/openpathai/server/phi.py`
- `src/openpathai/server/routes/__init__.py`
- `src/openpathai/server/routes/health.py`
- `src/openpathai/server/routes/nodes.py`
- `src/openpathai/server/routes/models.py`
- `src/openpathai/server/routes/datasets.py`
- `src/openpathai/server/routes/pipelines.py`
- `src/openpathai/server/routes/runs.py`
- `src/openpathai/server/routes/audit.py`
- `src/openpathai/server/routes/nl.py`
- `src/openpathai/server/routes/manifest.py`
- `src/openpathai/cli/serve_cmd.py`
- `tests/unit/server/conftest.py`
- `tests/unit/server/test_health.py`
- `tests/unit/server/test_auth.py`
- `tests/unit/server/test_nodes.py`
- `tests/unit/server/test_models.py`
- `tests/unit/server/test_datasets.py`
- `tests/unit/server/test_pipelines.py`
- `tests/unit/server/test_runs.py`
- `tests/unit/server/test_audit.py`
- `tests/unit/server/test_nl.py`
- `tests/unit/server/test_manifest.py`
- `tests/unit/server/test_phi_boundary.py`
- `docs/api.md`

Modified:

- `pyproject.toml` — add `[server]` extra + fastapi + uvicorn deps.
- `src/openpathai/cli/main.py` — register `serve` command.
- `CHANGELOG.md` — Phase 19 entry.
- `docs/planning/phases/README.md` — flip status.

---

## 6. Commands to Run During This Phase

```bash
# Sync the new [server] extra
uv sync --extra dev --extra server

# Unit tests
uv run pytest tests/unit/server -v

# Boot the server locally
uv run openpathai serve --port 7870 --token dev

# Hit the health check
curl -s http://localhost:7870/v1/health

# Open the interactive docs
open http://localhost:7870/docs
```

---

## 7. Risks in This Phase

- **Risk:** node input/output pydantic schemas include internal types (`SlideRef`, `ModelCard`) that serialise with filesystem paths.
  **Mitigation:** `server/phi.py` runs every response through `strip_phi` + `redact_manifest_path` before returning; a regex-based test asserts no `/Users/`, `/home/`, `C:\` in any response body.
- **Risk:** the async job runner is complex and error-prone.
  **Mitigation:** use `concurrent.futures.ThreadPoolExecutor` (mature stdlib) instead of hand-rolling; single-process only, one job at a time by default, capacity configurable.
- **Risk:** `POST /v1/runs` with a malicious pipeline YAML executes arbitrary code via `@node` side effects.
  **Mitigation:** iron rule #1 — every node is typed + registered; there is no raw-Python path. Node IDs are validated against the registry before dispatch; unknown IDs 422.
- **Risk:** CORS misconfiguration exposes the token-authenticated endpoints to every origin.
  **Mitigation:** default CORS allows only `http://localhost:5173` + `http://127.0.0.1:5173`; production overrides via env var.
- **Risk:** FastAPI + Gradio share the uvicorn port; concurrent `openpathai gui` and `openpathai serve` fights over 7860.
  **Mitigation:** default `serve` port is 7870; docs call out the split; CLI refuses to start if the configured port is in use.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · phase-19 closed (same-day)
**What:** Full Phase 19 shipped. `[server]` extra + `src/openpathai/server/`
package (app factory, settings, auth, jobs, phi middleware) + nine
`/v1` routers + `openpathai serve` CLI + 45 httpx/TestClient tests
(all green — 946 total suite). `docs/api.md` published. README
dashboard flipped to ✅. Tag `phase-19-complete` cut.
**Why:** user authorised Phase 19 implementation after confirming all
6 must-fix + 8 warnings + docker.yml workflow were resolved.
**Next:** Phase 20 — React + React Flow canvas consuming the
`/v1/nodes`, `/v1/models`, `/v1/pipelines`, `/v1/runs` endpoints.
**Blockers:** none.

### 2026-04-24 · phase-19 initialised
**What:** Spec drafted from `PHASE_TEMPLATE.md` after pre-Phase-19 audit
closed (tag `phase-18-audit-complete`). README dashboard flipped to 🔄.
**Why:** user authorised Phase 19 implementation after confirming all
6 must-fix + 8 warnings + docker.yml workflow were resolved.
**Next:** add `[server]` extra; scaffold `src/openpathai/server/`.
**Blockers:** none.
