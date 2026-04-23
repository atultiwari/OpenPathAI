"""Unit tests for :class:`openpathai.gui.state.AppState`."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.gui.state import AppState

FrozenInstanceError = AttributeError  # dataclasses' frozen setattr raises this


def test_app_state_has_sensible_defaults() -> None:
    state = AppState()
    assert state.device == "auto"
    assert state.selected_explainer == "gradcam"
    assert state.host == "127.0.0.1"
    assert state.port == 7860
    assert state.share is False


def test_app_state_updated_returns_new_instance() -> None:
    state = AppState()
    new_state = state.updated(device="cpu", selected_model="resnet18")
    assert new_state is not state
    assert new_state.device == "cpu"
    assert new_state.selected_model == "resnet18"
    # Original is untouched.
    assert state.device == "auto"
    assert state.selected_model is None


def test_app_state_is_frozen() -> None:
    state = AppState()
    with pytest.raises(FrozenInstanceError):
        state.device = "cpu"  # type: ignore[misc]


def test_with_cache_root_coerces_string() -> None:
    state = AppState().with_cache_root("/tmp/openpathai-cache")
    assert state.cache_root == Path("/tmp/openpathai-cache")
