"""``openpathai manifest`` — sign + verify run-manifest JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from openpathai.safety.sigstore import (
    ManifestSignature,
    SigstoreError,
    sign_manifest,
    verify_manifest,
)

__all__ = ["manifest_app"]

manifest_app = typer.Typer(
    name="manifest",
    help="Sign + verify OpenPathAI run-manifest JSON files (Phase 17).",
)


def _load_manifest_json(path: Path) -> dict[str, object]:
    if not path.exists():
        typer.secho(f"manifest not found: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.secho(
            f"manifest is not valid JSON: {exc!s}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from exc


def _signature_path(manifest_path: Path) -> Path:
    """Sibling file convention: ``manifest.json`` →
    ``manifest.signature.json``."""
    return manifest_path.with_name(manifest_path.stem + ".signature.json")


@manifest_app.command("sign")
def sign_cmd(
    manifest_path: Annotated[
        Path,
        typer.Argument(help="Path to a run manifest JSON file."),
    ],
) -> None:
    """Sign ``manifest_path``; write the sibling ``.signature.json``."""
    manifest = _load_manifest_json(manifest_path)
    try:
        signature = sign_manifest(manifest)
    except SigstoreError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    out = _signature_path(manifest_path)
    out.write_text(signature.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(
        json.dumps(
            {
                "signature_path": str(out),
                "manifest_hash": signature.manifest_hash,
                "signed_at": signature.signed_at,
            },
            indent=2,
            sort_keys=True,
        )
    )


@manifest_app.command("verify")
def verify_cmd(
    manifest_path: Annotated[
        Path,
        typer.Argument(help="Path to a run manifest JSON file."),
    ],
    signature_path: Annotated[
        Path | None,
        typer.Option(
            "--signature",
            help=("Override the signature-file path (default: sibling <manifest>.signature.json)."),
        ),
    ] = None,
) -> None:
    """Verify ``manifest_path`` against its sibling signature."""
    manifest = _load_manifest_json(manifest_path)
    sig_path = signature_path or _signature_path(manifest_path)
    if not sig_path.exists():
        typer.secho(
            f"signature not found at {sig_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        signature = ManifestSignature.model_validate_json(sig_path.read_text(encoding="utf-8"))
    except Exception as exc:
        typer.secho(
            f"signature file is malformed: {exc!s}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from exc

    try:
        ok = verify_manifest(manifest, signature)
    except SigstoreError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    payload = {
        "manifest_hash": signature.manifest_hash,
        "signature_ok": ok,
        "signer_pubkey": signature.public_key_b64,
        "signed_at": signature.signed_at,
        "algorithm": signature.algorithm,
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        raise typer.Exit(code=2)
