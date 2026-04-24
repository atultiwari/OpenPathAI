"""Runs tab — browse / filter the Phase 8 audit DB from the GUI.

Every callback delegates to an :mod:`openpathai.gui.views` helper that
is itself a thin wrapper around :mod:`openpathai.safety.audit`. The
tab never touches SQLite directly, so tests can exercise the helpers
without gradio.
"""

from __future__ import annotations

from typing import Any

from openpathai.gui.views import (
    audit_detail,
    audit_rows,
    audit_summary,
    run_diff_rows,
)

RUNS_HEADERS: list[str] = [
    "run_id",
    "kind",
    "mode",
    "status",
    "timestamp_start",
    "timestamp_end",
    "tier",
    "git_commit",
    "pipeline_yaml_hash",
]

DIFF_HEADERS: list[str] = ["field", "kind", "before", "after"]


def _rows_as_list(  # pragma: no cover - gradio
    *,
    kind: str | None = None,
    status: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
) -> list[list[str]]:
    rows = audit_rows(
        kind=kind,
        status=status,
        since=since,
        until=until,
        limit=limit,
    )
    return [[row[key] for key in RUNS_HEADERS] for row in rows]


def _detail(run_id: str) -> dict[str, Any]:  # pragma: no cover - gradio
    if not run_id:
        return {}
    return audit_detail(run_id.strip())


def _diff(run_a: str, run_b: str) -> list[list[str]]:  # pragma: no cover - gradio
    run_a = (run_a or "").strip()
    run_b = (run_b or "").strip()
    if not run_a or not run_b:
        return []
    return run_diff_rows(run_a, run_b)


def _summary_md() -> str:  # pragma: no cover - gradio
    summary: dict[str, Any] = audit_summary()
    size_mib = float(summary.get("size_bytes", 0) or 0) / (1024 * 1024)
    per_kind_raw = summary.get("runs_per_kind") or {}
    per_kind: dict[str, int] = per_kind_raw if isinstance(per_kind_raw, dict) else {}
    lines = [
        f"- **Path:** `{summary.get('path', '')}`",
        f"- **Schema version:** {summary.get('schema_version', '?')}",
        f"- **Size:** {size_mib:.3f} MiB",
        f"- **Runs:** {summary.get('runs', 0)} (analyses: {summary.get('analyses', 0)})",
    ]
    if per_kind:
        detail = ", ".join(f"{k}={v}" for k, v in sorted(per_kind.items()))
        lines.append(f"- **Per kind:** {detail}")
    token_raw = summary.get("token") or {}
    token: dict[str, str] = token_raw if isinstance(token_raw, dict) else {}
    lines.append(f"- **Token backend:** {token.get('store', '?')}")
    lines.append(f"- **Token set:** {token.get('set', '?')}")
    return "\n".join(lines)


def _delete_history(  # pragma: no cover - gradio
    before: str,
    token: str,
    confirm: bool,
) -> tuple[list[list[str]], str]:
    before = (before or "").strip()
    token = (token or "").strip()
    if not before:
        return _rows_as_list(), "Enter an ISO-8601 cutoff date before deleting."
    if not token:
        return _rows_as_list(), "Enter the delete token."
    if not confirm:
        return _rows_as_list(), "Check 'Yes, delete permanently' to proceed."

    from openpathai.safety.audit import AuditDB, KeyringTokenStore

    store = KeyringTokenStore()
    if not store.verify(token):
        return _rows_as_list(), "Delete refused: token mismatch."
    db = AuditDB.open_default()
    deleted = db.delete_before(before)
    return (
        _rows_as_list(),
        f"Deleted {deleted['runs']} run(s) and {deleted['analyses']} analyses older than {before}.",
    )


def build(state: Any) -> Any:  # pragma: no cover - gradio-gated renderer
    """Render the Runs tab. ``state`` is the shared :class:`AppState`."""
    import gradio as gr

    del state
    with gr.Blocks() as tab:
        gr.Markdown(
            "### Runs history (audit DB)\n"
            "Every `openpathai analyse` / `openpathai run` / "
            "`openpathai train` invocation is logged here (Phase 8). "
            "Filenames are hashed before write — nothing in this table "
            "surfaces a filesystem path."
        )
        summary = gr.Markdown(_summary_md())
        with gr.Row():
            kind = gr.Dropdown(
                ["", "pipeline", "training"],
                value="",
                label="Kind filter",
            )
            status = gr.Dropdown(
                ["", "running", "success", "failed", "aborted"],
                value="",
                label="Status filter",
            )
            since = gr.Textbox(label="Since (ISO-8601, optional)", value="")
            until = gr.Textbox(label="Until (ISO-8601, optional)", value="")
            limit = gr.Number(value=50, precision=0, label="Limit")
        refresh = gr.Button("Refresh")
        table = gr.Dataframe(
            headers=RUNS_HEADERS,
            value=_rows_as_list(),
            interactive=False,
        )

        def _filter(
            k: str,
            s: str,
            since_val: str,
            until_val: str,
            lim: int,
        ) -> tuple[list[list[str]], str]:
            return (
                _rows_as_list(
                    kind=k or None,
                    status=s or None,
                    since=since_val or None,
                    until=until_val or None,
                    limit=int(lim),
                ),
                _summary_md(),
            )

        refresh.click(
            _filter,
            inputs=[kind, status, since, until, limit],
            outputs=[table, summary],
        )

        with gr.Accordion("Run detail", open=False):
            with gr.Row():
                detail_id = gr.Textbox(label="Run id", value="")
                detail_btn = gr.Button("Show detail")
            detail_json = gr.JSON(label="Full row + linked analyses")
            detail_btn.click(_detail, inputs=[detail_id], outputs=[detail_json])

        with gr.Accordion("Diff two runs", open=False):
            with gr.Row():
                diff_a = gr.Textbox(label="Run A", value="")
                diff_b = gr.Textbox(label="Run B", value="")
                diff_btn = gr.Button("Diff")
            diff_table = gr.Dataframe(headers=DIFF_HEADERS, interactive=False)
            diff_btn.click(_diff, inputs=[diff_a, diff_b], outputs=[diff_table])

        with gr.Accordion("Delete history (requires delete token)", open=False):
            gr.Markdown(
                "Run `openpathai audit init` first to generate a token. "
                "Deletion is permanent — enter the cutoff date, token, "
                "and tick the confirmation box."
            )
            with gr.Row():
                del_before = gr.Textbox(
                    label="Cutoff (ISO-8601 UTC — everything earlier is deleted)",
                    value="",
                )
                del_token = gr.Textbox(label="Delete token", type="password")
            del_confirm = gr.Checkbox(label="Yes, delete permanently", value=False)
            del_btn = gr.Button("Delete")
            del_status = gr.Markdown("")
            del_btn.click(
                _delete_history,
                inputs=[del_before, del_token, del_confirm],
                outputs=[table, del_status],
            )
    return tab


__all__ = ["DIFF_HEADERS", "RUNS_HEADERS", "build"]
