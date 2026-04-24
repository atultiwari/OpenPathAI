# Safety v1 (Phase 7)

OpenPathAI is research-grade software, not a medical device. Phase 7
ships three safety surfaces that keep that boundary visible throughout
the workflow:

1. A **borderline band** on every classification call — confident
   predictions are labelled, uncertain ones route to human review.
2. A **PDF report** per analysis run, deterministic and PHI-safe.
3. A **model-card contract** enforced at registry load time so no model
   missing its metadata can reach the GUI pickers.

---

## The borderline band

Every classification produces a probability vector. Given two
thresholds `low ≤ high`:

| Winning probability | Decision | Band |
|---|---|---|
| `p < low`  | `negative` — model is confident **against** the predicted class | `low` |
| `low ≤ p ≤ high` | `review` — human adjudication required | `between` |
| `p > high` | `positive` — model is confident about the predicted class | `high` |

```python
from openpathai.safety import classify_with_band

decision = classify_with_band([0.15, 0.62, 0.23], low=0.4, high=0.7)
# BorderlineDecision(predicted_class=1, confidence=0.62, decision='review', band='between', low=0.4, high=0.7)
```

Calibration caveat
:    `classify_with_band` **refuses** uncalibrated inputs unless you pass
     `allow_uncalibrated=True`. Raw softmax on an uncalibrated classifier
     looks decisive but rarely is — the borderline band only earns its
     keep when thresholds are set on post-calibration probabilities
     (e.g. temperature-scaled output out of the Phase 3 training
     pipeline).

GUI surface
:    The **Analyse** tab exposes `low` / `high` sliders, a coloured
     banner (`🟢 POSITIVE` / `🔴 NEGATIVE` / `🟠 NEEDS REVIEW`), and a
     per-class probability bar chart.

CLI surface
:    `openpathai analyse --model resnet18 --tile tile.png --low 0.4 --high 0.7`
     prints the decision line and (with `--pdf out.pdf`) writes a full
     report.

---

## The PDF report

Each analysis run can be exported as a single-file PDF via
[`openpathai.safety.report.render_pdf`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/safety/report.py).
The report contains:

- a header with model / explainer / timestamp,
- the image SHA-256 (we **never** surface the filesystem path),
- thumbnail + explainability overlay,
- the borderline banner,
- per-class probabilities,
- a model-card snippet (training data, licence, citation,
  intended / out-of-scope use, known biases),
- the standard non-medical-device disclaimer.

Determinism
:    Two calls to `render_pdf` with the same `AnalysisResult` produce
     byte-identical PDFs. We use ReportLab's `invariant=True` mode, pin
     the PDF creation date from the result's `timestamp`, and stick to
     the PDF-standard Type-1 fonts so the output is stable across
     macOS, Linux, and Windows.

PHI protection
:    `render_pdf` refuses to emit a PDF if any user-supplied string
     contains `/Users/` or `/home/`. Only the SHA-256 of the image,
     an optional caption, and structured metadata reach the page.

---

## The model-card contract

Six fields on every `ModelCard` are mandatory:

| Field | Purpose |
|---|---|
| `training_data` | What corpus the weights came from. |
| `source.license` | Licence identifier on the pretrained weights. |
| `citation.text` | Citable prose reference. |
| `known_biases` | At least one bias / limitation entry. |
| `intended_use` | What OpenPathAI expects the card to be used for. |
| `out_of_scope_use` | What it must **not** be used for. |

[`validate_card`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/safety/model_card.py) returns a list
of `CardIssue` objects. An empty list means the card is safe to expose.

Registry enforcement
:    `ModelRegistry` calls `validate_card` on every card at load time.
     Incomplete cards are logged at `WARNING` and moved to
     `invalid_cards()`; `names()` and `get()` never return them. Set
     `OPENPATHAI_STRICT_MODEL_CARDS=1` to raise instead.

CLI surface
:    `openpathai models check` runs the contract across every
     registered card and exits non-zero if any fails. Use it in CI.

GUI surface
:    The **Models** tab shows every card, including invalid ones, with
     a `status` column (`ok` / `incomplete`) and an `issues` column
     naming the failing fields. Incomplete cards do not appear in the
     Analyse or Train pickers.
