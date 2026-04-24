"""``openpathai audit`` — inspect and prune the audit DB (Phase 8).

Subcommands:

* ``audit init``    — generate + stash the delete token.
* ``audit status``  — DB path / row counts / size / token backend.
* ``audit list``    — tabular listing of ``runs`` with filters.
* ``audit show``    — full JSON detail for one run + its analyses.
* ``audit delete``  — keyring-gated prune by cutoff date.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

audit_app = typer.Typer(
    name="audit",
    help="Inspect and prune the audit DB (Phase 8).",
    no_args_is_help=True,
    add_completion=False,
)


@audit_app.command("init")
def init_audit(
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite an existing token. Dangerous — old token is unrecoverable.",
        ),
    ] = False,
) -> None:
    """Generate and store a new delete token.

    Prints the token **exactly once** — the store only supports
    verification afterwards. Save it immediately (password manager,
    paper, etc.).
    """
    from openpathai.safety.audit import KeyringTokenStore

    store = KeyringTokenStore()
    existing = store.status()
    if existing["set"] == "true" and not force:
        typer.secho(
            "A delete token is already set. Pass --force to overwrite "
            "(the old token will be unrecoverable).",
            fg="yellow",
            err=True,
        )
        raise typer.Exit(1)
    if existing["set"] == "true":
        store.clear()
    token, backend = store.init()
    typer.secho("Delete token created.", fg="green")
    typer.echo(f"Backend: {backend}")
    typer.echo("")
    typer.secho(
        "SAVE THIS TOKEN NOW — it will not be shown again:",
        fg="yellow",
        bold=True,
    )
    typer.echo(token)


@audit_app.command("status")
def audit_status() -> None:
    """Print DB path, row counts, size on disk, and token-store backend."""
    from openpathai.safety.audit import AuditDB, KeyringTokenStore

    db = AuditDB.open_default()
    stats = db.stats()
    store = KeyringTokenStore()
    token_status = store.status()
    size_mib = stats["size_bytes"] / (1024 * 1024)
    typer.echo(f"path:            {stats['path']}")
    typer.echo(f"schema_version:  {stats['schema_version']}")
    typer.echo(f"size:            {size_mib:.3f} MiB")
    typer.echo(f"runs total:      {stats['runs']}")
    for kind, count in sorted(stats["runs_per_kind"].items()):
        typer.echo(f"  {kind:10s}   {count}")
    typer.echo(f"analyses total:  {stats['analyses']}")
    typer.echo(f"token backend:   {token_status['store']}")
    typer.echo(f"token set:       {token_status['set']}")


@audit_app.command("list")
def list_runs(
    kind: Annotated[
        str | None,
        typer.Option(help="Filter by kind (pipeline / training)."),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option(help="ISO-8601 UTC lower bound on timestamp_start."),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option(help="ISO-8601 UTC upper bound on timestamp_start."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option(help="Filter by status (running/success/failed/aborted)."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(help="Maximum rows to print.", min=1, max=10_000),
    ] = 50,
) -> None:
    """Tabular listing of the ``runs`` table, most recent first."""
    from openpathai.safety.audit import AuditDB

    db = AuditDB.open_default()
    rows = db.list_runs(
        kind=kind,  # type: ignore[arg-type]
        since=since,
        until=until,
        status=status,  # type: ignore[arg-type]
        limit=limit,
    )
    if not rows:
        typer.echo("(no runs matched)")
        raise typer.Exit(0)
    for entry in rows:
        typer.echo(
            f"{entry.run_id:<22s}  {entry.kind:<9s}  {entry.mode:<12s}  "
            f"{entry.status:<8s}  {entry.timestamp_start}"
        )


@audit_app.command("show")
def show_run(
    run_id: Annotated[str, typer.Argument(help="Run id to show.")],
) -> None:
    """Print full JSON detail for a run + its linked analyses."""
    from openpathai.safety.audit import AuditDB

    db = AuditDB.open_default()
    entry = db.get_run(run_id)
    if entry is None:
        typer.secho(f"No run with id {run_id!r}.", fg="red", err=True)
        raise typer.Exit(2)
    payload = {
        "run": entry.model_dump(mode="json"),
        "analyses": [
            a.model_dump(mode="json") for a in db.list_analyses(run_id=run_id, limit=1000)
        ],
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@audit_app.command("delete")
def delete_history(
    before: Annotated[
        str,
        typer.Option(
            "--before",
            help="Delete every run with timestamp_start strictly earlier than this ISO-8601 date.",
        ),
    ],
    token: Annotated[
        str | None,
        typer.Option(help="Delete token. Omit to read from prompt."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Actually delete (default is dry-run)."),
    ] = False,
) -> None:
    """Prune runs older than ``--before``. Requires the delete token."""
    from openpathai.safety.audit import AuditDB, KeyringTokenStore

    store = KeyringTokenStore()
    status = store.status()
    if status["set"] != "true":
        typer.secho(
            "No delete token is configured. Run `openpathai audit init` first.",
            fg="red",
            err=True,
        )
        raise typer.Exit(2)

    candidate = token
    if candidate is None:
        candidate = typer.prompt("Delete token", hide_input=True)

    if not store.verify(candidate):
        typer.secho("Delete refused: token mismatch.", fg="red", err=True)
        raise typer.Exit(3)

    db = AuditDB.open_default()
    if not yes:
        # Dry-run — count without deleting.
        all_runs = db.list_runs(limit=1_000_000)
        candidates = [r for r in all_runs if r.timestamp_start < before]
        typer.echo(f"Would delete {len(candidates)} run(s) older than {before}.")
        typer.echo("Pass --yes to actually delete.")
        return

    deleted = db.delete_before(before)
    typer.secho(
        f"Deleted {deleted['runs']} run(s) and {deleted['analyses']} analyses older than {before}.",
        fg="green",
    )


__all__ = ["audit_app"]
