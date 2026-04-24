# Preprocessing (Phase 9)

OpenPathAI ships preprocessing primitives as small, pure-Python
numpy functions — no OpenCV, no scikit-image at runtime. They sit
under [`openpathai.preprocessing`](https://github.com/atultiwari/OpenPathAI/tree/main/src/openpathai/preprocessing).

## QC checks

Four focused checks, one per common slide-quality failure mode.
Every check takes an `(H, W, 3)` uint8 RGB thumbnail (or tile) and
returns a
[`QCFinding`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/preprocessing/qc/findings.py).

| Check        | Detects              | Score              | Threshold (default) |
|--------------|----------------------|--------------------|---------------------|
| `blur`       | Out-of-focus / shake | Variance of Laplacian (higher = sharper) | `≥ 80.0` passes |
| `pen_marks`  | Saturated ink hues   | Fraction of ink-band, high-saturation pixels | `≤ 0.02` passes |
| `folds`      | Elongated dark streaks | Fraction of pixels in top-gradient tail | `≤ 0.05` passes |
| `focus`      | Systemic defocus      | Mean Sobel magnitude | `≥ 2.0` passes |

### Severity ladder

`QCFinding.severity` is one of `info` / `warn` / `fail`. `fail`
findings are disqualifying (blur / pen-marks); `warn` findings are
cautionary (folds / focus) because they often surface edge-case
slides rather than unusable ones.

### Custom thresholds

```python
from openpathai.preprocessing.qc import blur_finding

finding = blur_finding(thumbnail, threshold=40.0)
```

### Running every check

```python
from openpathai.preprocessing.qc import run_all_checks

for finding in run_all_checks(thumbnail):
    print(finding.badge, finding.check, finding.score, finding.passed)
```

### Cohort-scope aggregation

See [Cohorts](cohorts.md). The one-liner is:

```python
report = cohort.run_qc(thumbnail_extractor)
report.summary()  # → {"pass": N, "warn": N, "fail": N}
```

Both HTML and PDF renderers are available from
`openpathai.preprocessing.qc.{render_html, render_pdf}` and are
byte-deterministic given the same input — the PDF reuses the Phase 7
ReportLab `invariant=True` + pinned-creation-date pattern.

---

## Stain references

`data/stain_references/*.yaml` ships tissue-specific Macenko bases.
The four initial cards:

| Name            | Tissue              | Source            | Licence lineage               |
|-----------------|---------------------|-------------------|-------------------------------|
| `he_default`    | any                 | Macenko 2009      | Public-domain paper reference |
| `he_colon`      | colon               | LC25000-derived   | CC-BY-4.0 (LC25000)           |
| `he_breast`     | breast / lymph node | PatchCamelyon     | CC0-1.0 (PCam)                |
| `he_lung`       | lung                | LC25000-derived   | CC-BY-4.0 (LC25000)           |

Each YAML records `source_card` (the dataset the basis was fitted
from) and `licence` (lineage, not the basis itself — fitted stain
matrices are factual measurements, not copyrightable works).

### Using a reference

```python
from openpathai.preprocessing import MacenkoNormalizer

normaliser = MacenkoNormalizer.from_reference("he_colon")
normalised = normaliser.transform(tile_rgb)
```

### Registering your own

Drop a YAML card at `~/.openpathai/stain_references/<name>.yaml`
matching the shipped schema. Fields:

```yaml
name: custom_ihc_panel
display_name: "Custom IHC panel"
stain_kind: "IHC"
tissue: [kidney]
stain_matrix:
  - […three floats…]
  - […three floats…]
max_concentrations: [1.9, 1.0]
source_card: null
license: "unspecified"
citation:
  text: "Internal fit, project X (2026)."
```

The registry picks up user YAMLs on the next call to
`default_stain_registry()`.

### Phase 9 scope reminder

Phase 9 **ships** pre-computed references but does not ship a UI for
fitting new references from a user-supplied slide — that lands
alongside IHC in Phase 14.
