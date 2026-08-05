from __future__ import annotations

import cv2
import numpy as np

from app import identity


class FakeDetector:
    def __init__(self, faces: list[tuple[int, int, int, int]]) -> None:
        self.faces = np.array(faces, dtype=np.int32)

    def detectMultiScale(self, *_args: object, **_kwargs: object) -> np.ndarray:
        return self.faces


def make_image_bytes(width: int = 400, height: int = 400) -> bytes:
    image = np.full((height, width, 3), 180, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def test_no_face_is_high_risk(monkeypatch) -> None:
    monkeypatch.setattr(identity, "_face_detector", lambda: FakeDetector([]))

    report = identity.analyze_identity(make_image_bytes())

    assert report.face_count == 0
    assert report.identity_readiness == "not_ready"
    assert report.identity_risk == "high"


def test_large_face_is_ready(monkeypatch) -> None:
    monkeypatch.setattr(identity, "_face_detector", lambda: FakeDetector([(80, 60, 200, 200)]))

    report = identity.analyze_identity(make_image_bytes())

    assert report.face_count == 1
    assert report.identity_readiness == "ready"
    assert report.identity_risk == "low"
    assert report.largest_face_ratio == 0.25


def test_faces_are_sorted_largest_first(monkeypatch) -> None:
    monkeypatch.setattr(
        identity,
        "_face_detector",
        lambda: FakeDetector([(10, 10, 60, 60), (100, 100, 160, 160)]),
    )

    report = identity.analyze_identity(make_image_bytes())

    assert report.face_count == 2
    assert report.faces[0].width == 160
    assert report.faces[1].width == 60
