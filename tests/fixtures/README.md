# Test fixtures

Fixtures are synthesised on demand by `tests/conftest.py` — no binaries
are committed to the repo.

| Fixture | Where | Purpose |
|---|---|---|
| `synthetic_he_tile` | `tests/conftest.py` | 256×256 RGB tile with a pink/purple tissue blob on near-white background. Used by Macenko and Otsu tests. |
| `synthetic_slide_path` | `tests/conftest.py` | 1024×1024 TIFF saved to a session-scoped tmp dir. Used by the `PillowSlideReader` and `GridTiler` tests. |

Both are deterministic (seeded `np.random.default_rng`) so the same
tests pass across machines and across runs.
