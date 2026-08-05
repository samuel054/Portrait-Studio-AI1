import cv2
import numpy as np

from app.analyzer import analyze_image


def encode(image: np.ndarray) -> bytes:
    ok, data = cv2.imencode(".png", image)
    assert ok
    return data.tobytes()


def test_analyze_image_returns_dimensions_and_quality_flags() -> None:
    image = np.full((200, 300, 3), 128, dtype=np.uint8)
    report = analyze_image(encode(image))

    assert report.width == 300
    assert report.height == 200
    assert report.megapixels == 0.06
    assert report.lighting == "good"
    assert report.needs_enhancement is True


def test_invalid_image_is_rejected() -> None:
    try:
        analyze_image(b"not-an-image")
    except ValueError as exc:
        assert "readable image" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
