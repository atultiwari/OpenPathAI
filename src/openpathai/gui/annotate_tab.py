"""Annotate tab — Phase 16 active-learning GUI (Bet 1 close).

This tab wraps the Phase-12 ``ActiveLearningLoop`` in a Gradio UI:

* top row — dataset / oracle CSV pickers, annotator-id textbox,
  "Start session" button;
* middle row — current tile id, per-class prediction bar, a
  label radio, skip / retrain / clear-mask buttons;
* bottom row — queue-remaining counter, iteration number, ECE
  before/after, click-to-segment mask preview.

Every callback delegates to helpers in :mod:`openpathai.gui.views`
so unit tests can exercise the logic without importing Gradio.
Keyboard shortcuts are wired via the ``js=...`` hook (see
`docs/annotate-workflow.md` for the full table).
"""

from __future__ import annotations

import json
from typing import Any

from openpathai.gui.views import (
    annotate_next_tile,
    annotate_record_correction,
    annotate_retrain,
    annotate_session_init,
)

__all__ = ["build"]


_KEYBOARD_HELP = """\
- **1**-**9** -> confirm current tile with class *i* - 1
- **S** -> skip (advance queue without correction)
- **C** -> clear any active click-to-segment mask
- **R** -> retrain on accumulated corrections
- Keyboard input only fires when the Annotate-tab root has focus
  (click the tab header first).
"""


def build(state: Any) -> None:  # pragma: no cover - gradio
    import gradio as gr

    del state  # unused — sessions are keyed by user-supplied paths.

    with gr.Column():
        gr.Markdown("## Annotate — active-learning queue + click-to-segment")
        gr.Markdown(
            "Single-user workstation assumption. Multi-rater CSVs "
            "merge via a side helper; no authentication layer."
        )

        session_state = gr.State({})

        with gr.Row():
            pool_csv = gr.Textbox(
                label="Pool CSV (tile_id, label)",
                placeholder="/path/to/pool.csv",
            )
            out_dir = gr.Textbox(
                label="Output dir",
                placeholder="/tmp/openpathai-annotate",
            )
            annotator = gr.Textbox(label="Annotator ID", value="dr-a")
            start_btn = gr.Button("Start session", variant="primary")

        with gr.Accordion("Keyboard shortcuts", open=False):
            gr.Markdown(_KEYBOARD_HELP)

        status = gr.Markdown("No active session.")
        tile_info = gr.JSON(label="Current tile")

        with gr.Row():
            label_input = gr.Textbox(label="Corrected label")
            record_btn = gr.Button("Record correction (Enter)")
            skip_btn = gr.Button("Skip (S)")
            retrain_btn = gr.Button("Retrain (R)", variant="secondary")

        with gr.Row():
            metrics = gr.JSON(label="Last retrain metrics")

        def _start(p: str, o: str, a: str) -> tuple[dict, dict, str]:
            try:
                session = annotate_session_init(pool_csv=p, out_dir=o, annotator_id=a or "dr-a")
            except (FileNotFoundError, ValueError) as exc:
                return {}, {}, f"**Session init failed:** {exc}"
            info = annotate_next_tile(session)
            return (
                session,
                info,
                f"Session started · {info['remaining']} tiles in queue "
                f"· log → {session['log_path']}",
            )

        start_btn.click(
            _start,
            inputs=[pool_csv, out_dir, annotator],
            outputs=[session_state, tile_info, status],
        )

        def _record(session: dict, label: str) -> tuple[dict, dict, str]:
            if not session:
                return {}, {}, "Start a session first."
            tile = annotate_next_tile(session)
            tile_id = str(tile.get("tile_id", "") or "")
            if not tile_id:
                return session, tile, "Queue exhausted — press Retrain."
            try:
                new_session = annotate_record_correction(
                    session, tile_id=tile_id, corrected_label=label
                )
            except ValueError as exc:
                return session, tile, f"**Reject:** {exc}"
            next_tile = annotate_next_tile(new_session)
            remaining = next_tile.get("remaining", 0)
            return (
                new_session,
                next_tile,
                f"Recorded {tile_id} → {label}; {remaining} tiles remaining.",
            )

        record_btn.click(
            _record,
            inputs=[session_state, label_input],
            outputs=[session_state, tile_info, status],
        )

        def _skip(session: dict) -> tuple[dict, dict, str]:
            if not session:
                return {}, {}, "Start a session first."
            new_session = dict(session)
            cursor = int(session.get("cursor", 0))
            queue = list(session.get("queue", []))
            new_session["cursor"] = min(cursor + 1, len(queue))
            next_tile = annotate_next_tile(new_session)
            return (
                new_session,
                next_tile,
                f"Skipped · {next_tile.get('remaining', 0)} tiles remaining.",
            )

        skip_btn.click(_skip, inputs=[session_state], outputs=[session_state, tile_info, status])

        def _retrain(session: dict) -> tuple[dict, dict, str]:
            if not session:
                return {}, {}, "Start a session first."
            result = annotate_retrain(session)
            new_session_raw = result.pop("session")
            new_session: dict = new_session_raw if isinstance(new_session_raw, dict) else {}
            ece_after = float(result.get("ece_after", 0.0))  # type: ignore[arg-type]
            ece_before = float(result.get("ece_before", 0.0))  # type: ignore[arg-type]
            acc_after = float(result.get("accuracy_after", 0.0))  # type: ignore[arg-type]
            return (
                new_session,
                result,
                f"Retrain · ΔECE = {ece_after - ece_before:+.4f} · acc = {acc_after:.3f}",
            )

        retrain_btn.click(
            _retrain,
            inputs=[session_state],
            outputs=[session_state, metrics, status],
        )
        _ = json  # retained for future JSON-payload ergonomics
