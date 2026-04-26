"""Tests for the Phase 22.1 MedGemma fallback planner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openpathai.data.advise_llm import (
    build_metadata_prompt,
    parse_llm_plan,
    propose_plan_via_llm,
)
from openpathai.data.shape import inspect_folder


def _make_tile(p: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image  # type: ignore[import-untyped]

    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (10, 20, 30)).save(p, format="PNG")


def _kather_like(tmp_path: Path) -> Path:
    inner = tmp_path / "Kather_texture_2016_image_tiles_5000"
    for cls in ("01_TUMOR", "02_STROMA"):
        for i in range(3):
            _make_tile(inner / cls / f"{i}.png")
    return tmp_path


class _FakeBackend:
    """Stand-in for an LLM backend — captures the prompt and returns
    a canned JSON response."""

    def __init__(self, response_content: str) -> None:
        self.response_content = response_content
        self.last_messages: list = []
        self.last_temperature: float | None = None
        self.last_response_format: dict | None = None

    def chat(self, messages, *, temperature=0.2, response_format=None):  # type: ignore[no-untyped-def]
        from openpathai.nl.llm_backends.base import ChatResponse

        self.last_messages = messages
        self.last_temperature = temperature
        self.last_response_format = response_format
        return ChatResponse(
            content=self.response_content,
            backend_id="fake",
            model_id="medgemma:1.5",
        )


def test_build_metadata_prompt_excludes_image_bytes(tmp_path: Path) -> None:
    _kather_like(tmp_path)
    shape = inspect_folder(tmp_path)
    prompt = build_metadata_prompt(shape, "yolo-classifier-yolov26")
    # Structural facts are present.
    assert "TARGET MODEL: yolo-classifier-yolov26" in prompt
    assert "REQUIREMENT BUCKET: yolo_cls_split" in prompt
    assert "Kather_texture_2016_image_tiles_5000" in prompt
    assert "01_TUMOR" in prompt
    # Image bytes / pixel data are NEVER in the prompt.
    assert "data:image" not in prompt
    assert "base64" not in prompt
    # Schema hint is included.
    assert "make_split" in prompt


def test_parse_llm_plan_happy_path(tmp_path: Path) -> None:
    _kather_like(tmp_path)
    shape = inspect_folder(tmp_path)
    raw = json.dumps(
        {
            "ok": True,
            "actions": [
                {"kind": "make_dir", "path": "/tmp/out"},
                {
                    "kind": "make_split",
                    "dest_root": "/tmp/out",
                    "class_dirs": ["/tmp/a", "/tmp/b"],
                    "train_ratio": 0.7,
                    "val_ratio": 0.2,
                    "test_ratio": 0.1,
                    "seed": 7,
                },
            ],
            "notes": ["Reviewed by MedGemma."],
        }
    )
    plan = parse_llm_plan(raw, shape=shape, model_id="yolo-classifier-yolov26")
    assert plan.ok is True
    assert plan.provenance == "medgemma"
    assert {a.kind for a in plan.actions} == {"make_dir", "make_split"}
    assert plan.notes == ("Reviewed by MedGemma.",)
    # Bash render is non-empty.
    assert "make_split" in plan.bash


def test_parse_llm_plan_unparseable_returns_incompatible(tmp_path: Path) -> None:
    _kather_like(tmp_path)
    shape = inspect_folder(tmp_path)
    plan = parse_llm_plan("not json at all", shape=shape, model_id="dinov2")
    assert plan.ok is False
    assert plan.actions[0].kind == "incompatible"
    assert "not valid JSON" in plan.actions[0].reason


def test_parse_llm_plan_unknown_action_returns_incompatible(tmp_path: Path) -> None:
    _kather_like(tmp_path)
    shape = inspect_folder(tmp_path)
    raw = json.dumps(
        {
            "ok": True,
            "actions": [{"kind": "delete_universe"}],
        }
    )
    plan = parse_llm_plan(raw, shape=shape, model_id="dinov2")
    assert plan.ok is False
    assert plan.actions[0].kind == "incompatible"
    assert "delete_universe" in plan.actions[0].reason


def test_parse_llm_plan_explicit_incompatible(tmp_path: Path) -> None:
    _kather_like(tmp_path)
    shape = inspect_folder(tmp_path)
    raw = json.dumps(
        {
            "ok": False,
            "actions": [
                {
                    "kind": "incompatible",
                    "reason": "No bbox labels on disk.",
                    "hint": "Bootstrap with MedSAM2 zero-shot.",
                }
            ],
        }
    )
    plan = parse_llm_plan(raw, shape=shape, model_id="yolo-detector-yolov26")
    assert plan.ok is False
    assert plan.actions[0].kind == "incompatible"
    assert plan.actions[0].hint == "Bootstrap with MedSAM2 zero-shot."


def test_propose_plan_via_llm_uses_injected_backend(tmp_path: Path) -> None:
    _kather_like(tmp_path)
    shape = inspect_folder(tmp_path)
    canned = json.dumps(
        {
            "ok": True,
            "actions": [{"kind": "make_dir", "path": "/tmp/yolo_out"}],
            "notes": ["mock"],
        }
    )
    fake = _FakeBackend(canned)
    plan = propose_plan_via_llm(shape, "yolo-classifier-yolov26", backend=fake)
    assert plan.provenance == "medgemma"
    assert plan.ok is True
    assert plan.actions[0].kind == "make_dir"
    # Backend received a metadata-only prompt with the right model id.
    assert any(
        "yolo-classifier-yolov26" in m.content for m in fake.last_messages if m.role == "user"
    )
    # JSON response format requested.
    assert fake.last_response_format == {"type": "json_object"}


def test_propose_plan_via_llm_handles_backend_chat_failure(tmp_path: Path) -> None:
    _kather_like(tmp_path)
    shape = inspect_folder(tmp_path)

    class _Boom:
        def chat(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("connection refused")

    plan = propose_plan_via_llm(shape, "dinov2", backend=_Boom())
    assert plan.ok is False
    assert plan.provenance == "medgemma"
    assert "connection refused" in plan.actions[0].reason
