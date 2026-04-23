# Developer guide

Short version for contributors and AI agents. The authoritative working spec
is [CLAUDE.md](https://github.com/atultiwari/OpenPathAI/blob/main/CLAUDE.md)
at the repo root.

## Environment

OpenPathAI uses [uv](https://docs.astral.sh/uv/) for environments and
packaging.

```bash
git clone https://github.com/atultiwari/OpenPathAI.git
cd OpenPathAI

uv venv --python 3.11 .venv
uv sync --extra dev
```

## Verify

```bash
uv run ruff check src tests
uv run pyright src
uv run pytest -q
uv run mkdocs build --strict
uv run openpathai --version
uv run openpathai hello
```

All of these must pass before opening a PR.

## Project structure

```
OpenPathAI/
├── CLAUDE.md                     # iron rules + multi-phase management
├── pyproject.toml                # tier-optional extras: local/colab/runpod/gui/notebook/dev
├── src/openpathai/               # the library (thin layer; no GUI logic)
├── tests/                        # pytest (unit / integration / smoke markers)
├── docs/                         # user docs (mkdocs-material)
│   ├── planning/                 # master plan + phase specs (not published to site)
│   └── setup/                    # user setup guides
└── .github/workflows/            # CI + Pages
```

See the master plan for the full target layout:
[docs/planning/master-plan.md §19](https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/master-plan.md).

## Multi-phase discipline

OpenPathAI ships in ~22 numbered phases. At any moment **one phase is
active**. The phase dashboard lives at
[docs/planning/phases/README.md](https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/README.md).

To contribute:

1. Check the phase dashboard for the active phase.
2. Read that phase's spec file in full.
3. Claim a deliverable.
4. Open a PR closing that deliverable.

New ideas that fall outside the active phase belong in **Discussions**, not
PRs.

Full details: [CONTRIBUTING.md](https://github.com/atultiwari/OpenPathAI/blob/main/CONTRIBUTING.md).

## Coding standards

Highlights (full list in [CLAUDE.md §2](https://github.com/atultiwari/OpenPathAI/blob/main/CLAUDE.md)):

- **Library-first, UI-last.** Business logic lives in
  [`src/openpathai/`](https://github.com/atultiwari/OpenPathAI/tree/main/src/openpathai).
  Never in a GUI callback.
- **Typed nodes, pydantic everywhere.**
- **Content-addressable caching from day one.**
- **Patient-level CV splits by default.**
- **Cross-platform from day one** (macOS-ARM / Linux / Windows / Colab).
- **Every model has a YAML card** stating training data, licence, citation,
  known biases.

## Conventional commits

- `feat: …` — new feature
- `fix: …` — bug fix
- `chore(phase-N): …` — Phase N scaffolding or worklog changes
- `docs: …` — documentation
- `test: …` — tests
- `refactor: …` — non-behaviour changes
- `ci: …` — CI configuration

## Pipeline primitives (Phase 1)

From Phase 1 onward, every OpenPathAI capability is exposed as a typed
pipeline node. The public API lives under
[`openpathai.pipeline`](https://github.com/atultiwari/openpathai/tree/main/src/openpathai/pipeline):

- **`Artifact`** — pydantic base class for every typed pipeline output.
  Implements a deterministic ``content_hash()`` used by downstream cache
  keys.
- **`@node`** — decorator that registers a function as a pipeline node.
  Requires one pydantic ``BaseModel`` input and an ``Artifact`` return
  type. Captures a SHA-256 code hash so edits invalidate cached outputs.
- **`REGISTRY`** — global ``NodeRegistry`` singleton (pass a custom
  `NodeRegistry` to ``node(..., registry=...)`` for test isolation).
- **`ContentAddressableCache`** — filesystem cache keyed by
  ``sha256(node_id + code_hash + canonical_json(input_config) + canonical_json(sorted(upstream_hashes)))``.
- **`Executor`**, **`Pipeline`**, **`PipelineStep`** — walks a DAG,
  respects the cache, produces a **`RunManifest`** + dict of artifacts
  by step id.
- **`RunManifest`** — hashable audit record (pipeline graph hash, per-step
  cache hits/misses, environment, timestamps, metrics). Round-trips
  through JSON.

Minimal end-to-end example:

```python
from pydantic import BaseModel
from openpathai import (
    Artifact, ContentAddressableCache, Executor, NodeRegistry,
    Pipeline, PipelineStep, node,
)


class ValueInput(BaseModel):
    value: int


class IntOut(Artifact):
    value: int


registry = NodeRegistry()


@node(id="demo.double", registry=registry)
def double(cfg: ValueInput) -> IntOut:
    return IntOut(value=cfg.value * 2)


cache = ContentAddressableCache(root="/tmp/demo-cache")
executor = Executor(cache, registry=registry)

pipeline = Pipeline(
    id="demo",
    steps=[PipelineStep(id="a", op="demo.double", inputs={"value": 5})],
)

result = executor.run(pipeline)
print(result.artifacts["a"].value)       # -> 10
print(result.cache_stats)                 # hits=0 misses=1

# Rerun: same args, all cache hits.
result2 = executor.run(pipeline)
print(result2.cache_stats)                # hits=1 misses=0
```

Design rules to keep in mind when adding a new node:

- **Module-scope types.** The pydantic input model and Artifact output
  model should live at module scope so ``typing.get_type_hints`` can
  resolve them during decoration.
- **Only one parameter.** Nodes take exactly one pydantic input model —
  not positional args, not ``**kwargs``.
- **Pure-ish by default.** Node functions should be deterministic given
  their inputs. Anything that touches wall-clock time, network, or
  random state must surface those inputs explicitly so cache invalidation
  is predictable.
- **Artifacts are frozen.** Don't mutate them; produce a new artifact
  instead.

## License

By contributing, you agree your contribution is licensed under the
project's MIT licence.
