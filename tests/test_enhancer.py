import cv2
import numpy as np

from app.enhancer import enhance_image


def encode(image: np.ndarray) -> bytes:
    ok, data = cv2.imencode(".png", image)
    assert ok
    return data.tobytes()


def test_low_resolution_image_is_upscaled_without_changing_face_count() -> None:
    image = np.full((240, 320, 3), 110, dtype=np.uint8)
    enhanced, report = enhance_image(encode(image))

    decoded = cv2.imdecode(np.frombuffer(enhanced, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    assert report.applied is True
    assert "non_generative_upscale" in report.operations
    assert report.output_width > 320
    assert report.output_height > 240
    assert report.face_count_preserved is True
    assert report.before.megapixels < report.after.megapixels


def test_dark_image_receives_lighting_correction() -> None:
    image = np.full((800, 800, 3), 25, dtype=np.uint8)
    _, report = enhance_image(encode(image))

    assert "lighting_correction" in report.operations
    assert report.after.brightness > report.before.brightness


def test_invalid_image_is_rejected() -> None:
    try:
        enhance_image(b"not-an-image")
    except ValueError as exc:
        assert "readable image" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
