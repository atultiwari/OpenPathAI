"""YOLOv8 adapter (real, lazy-imports ultralytics).

**AGPL-3.0 notice:** ``ultralytics`` (which this adapter imports at
runtime) is AGPL-3.0. OpenPathAI itself is MIT. Using this adapter
in a proprietary pipeline requires a commercial Ultralytics
licence; the ``NOTICE`` file lists this explicitly. We never
vendor ultralytics code — iron rule #12 from ``CLAUDE.md``.

The adapter shape:

* ``.build()`` lazy-imports ``ultralytics``. If the package isn't
  installed, it raises ``ImportError`` — which the detection
  registry turns into a fallback via :func:`resolve_detector`.
* ``.detect()`` runs the loaded model on a numpy / PIL image and
  maps the result to :class:`DetectionResult`.

When no checkpoint is provided, the adapter defaults to
``yolov8n.pt`` (the nano variant) which Ultralytics downloads to
``~/.cache/torch/hub`` on first use. Users on air-gapped machines
should preset ``OPENPATHAI_HOME/models/yolov8n.pt`` and pass
``weight_path=...`` to the constructor.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from openpathai.detection.schema import BoundingBox, DetectionResult

__all__ = ["YOLOv8Adapter"]


def _default_weight_path() -> Path:
    root = Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))
    return root / "models" / "yolov8n.pt"


class YOLOv8Adapter:
    """YOLOv8 nano via lazy-imported ultralytics."""

    id: str = "yolov8"
    display_name: str = "YOLOv8n (Ultralytics, AGPL-3.0)"
    gated: bool = True  # AGPL contamination risk — treat as gated
    weight_source: str | None = "ultralytics://yolov8n.pt"
    input_size: tuple[int, int] = (640, 640)
    tier_compatibility: frozenset[str] = frozenset({"T1", "T2", "T3"})
    vram_gb: float = 2.0
    license: str = "AGPL-3.0 (upstream ultralytics)"
    citation: str = (
        "Jocher et al., 'Ultralytics YOLOv8' (2023). https://github.com/ultralytics/ultralytics"
    )

    def __init__(self, weight_path: str | Path | None = None) -> None:
        self._weight_path = Path(weight_path) if weight_path else _default_weight_path()
        self._model: Any = None

    def build(self, pretrained: bool = True) -> Any:
        # Lazy-import — never at module load time.
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise ImportError(
                "YOLOv8 adapter requires the [yolo] extra "
                "(ultralytics; AGPL-3.0 — see NOTICE). "
                "Install via `uv sync --extra yolo` or accept the "
                "fallback to SyntheticDetector via resolve_detector()."
            ) from exc

        # pragma: no cover - requires real ultralytics wheels + network.
        checkpoint = str(self._weight_path) if self._weight_path.exists() else "yolov8n.pt"
        self._model = YOLO(checkpoint) if pretrained else YOLO("yolov8n.yaml")
        return self._model

    def detect(
        self,
        image: Any,
        *,
        conf_threshold: float = 0.25,
    ) -> DetectionResult:  # pragma: no cover - exercised with real weights only
        if self._model is None:
            self.build(pretrained=True)
        assert self._model is not None
        arr = np.asarray(image)
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        h, w = int(arr.shape[0]), int(arr.shape[1])
        results = self._model(arr, conf=conf_threshold, verbose=False)
        boxes: list[BoundingBox] = []
        if results:
            first = results[0]
            names = getattr(first, "names", {})
            if first.boxes is not None:
                for row in first.boxes:
                    xyxy = row.xyxy[0].tolist()
                    cls_id = int(row.cls[0].item())
                    confidence = float(row.conf[0].item())
                    class_name = names.get(cls_id, str(cls_id)) if names else str(cls_id)
                    x0, y0, x1, y1 = xyxy
                    boxes.append(
                        BoundingBox(
                            x=float(x0),
                            y=float(y0),
                            w=float(max(1.0, x1 - x0)),
                            h=float(max(1.0, y1 - y0)),
                            class_name=class_name or str(cls_id),
                            confidence=confidence,
                        )
                    )
        return DetectionResult(
            boxes=tuple(boxes),
            image_width=w,
            image_height=h,
            model_id=self.id,
            resolved_model_id=self.id,
        )
