"""User-level configuration helpers shared across the library.

Phase 21.5 chunk C introduced :mod:`openpathai.config.hf` to centralise
Hugging Face token resolution (settings file > env). Future helpers for
other long-lived credentials (API keys, signing keys) belong here too.
"""

from __future__ import annotations

from openpathai.config import hf

__all__ = ["hf"]
