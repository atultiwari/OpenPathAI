"""SyntheticDetector — pure-numpy blob detector (the fallback anchor)."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.detection import BoundingBox, DetectionResult, SyntheticDetector


def _blob_image(*, size: int = 128, centres: list[tuple[int, int]] | None = None) -> np.ndarray:
    """White square image with a few black circles drawn on it."""
    if centres is None:
        centres = [(32, 32), (96, 96)]
    img = np.full((size, size, 3), 240, dtype=np.uint8)
    yy, xx = np.mgrid[:size, :size]
    for cy, cx in centres:
        radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
        img[radius < 12] = np.array([20, 20, 20], dtype=np.uint8)
    return img


def test_detect_finds_blobs() -> None:
    detector = SyntheticDetector(class_name="nucleus")
    image = _blob_image()
    result = detector.detect(image, conf_threshold=0.1)
    assert isinstance(result, DetectionResult)
    assert len(result.boxes) >= 1
    # All boxes are valid (BoundingBox validates at construction).
    for box in result.boxes:
        assert isinstance(box, BoundingBox)
        assert box.class_name == "nucleus"


def test_detect_respects_confidence_threshold() -> None:
    detector = SyntheticDetector()
    image = _blob_image()
    loose = detector.detect(image, conf_threshold=0.0)
    tight = detector.detect(image, conf_threshold=0.99)
    assert len(loose.boxes) >= len(tight.boxes)


def test_detect_on_empty_image_returns_no_boxes() -> None:
    detector = SyntheticDetector()
    result = detector.detect(np.full((64, 64, 3), 200, dtype=np.uint8))
    assert len(result.boxes) == 0
    assert result.image_width == 64
    assert result.image_height == 64


def test_detection_result_model_ids_match_detector() -> None:
    detector = SyntheticDetector()
    result = detector.detect(_blob_image())
    assert result.model_id == detector.id
    assert result.resolved_model_id == detector.id


def test_bounding_box_xyxy_roundtrip() -> None:
    b = BoundingBox(x=1.0, y=2.0, w=3.0, h=4.0, class_name="x", confidence=0.5)
    assert b.xyxy == (1.0, 2.0, 4.0, 6.0)


def test_detection_result_filter_by_confidence() -> None:
    detector = SyntheticDetector()
    result = detector.detect(_blob_image(), conf_threshold=0.0)
    filtered = result.filter_by_confidence(0.99)
    assert all(b.confidence >= 0.99 for b in filtered.boxes)


def test_bounding_box_rejects_invalid_values() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        BoundingBox(x=-1.0, y=0, w=1, h=1, class_name="x", confidence=0.5)
    with pytest.raises(pydantic.ValidationError):
        BoundingBox(x=0, y=0, w=0, h=1, class_name="x", confidence=0.5)
    with pytest.raises(pydantic.ValidationError):
        BoundingBox(x=0, y=0, w=1, h=1, class_name="", confidence=0.5)
    with pytest.raises(pydantic.ValidationError):
        BoundingBox(x=0, y=0, w=1, h=1, class_name="x", confidence=1.5)
