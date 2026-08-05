from __future__ import annotations

import cv2
import numpy as np

from app.identity_score import rank_identity_first_candidates


class SequenceAdapter:
    id = "sequence_test"

    def __init__(self, vectors: list[list[float]]) -> None:
        self._vectors = iter(vectors)

    def embed(self, _image_bytes: bytes) -> np.ndarray:
        return np.asarray(next(self._vectors), dtype=np.float32)


def _portrait() -> bytes:
    image = np.full((256, 256, 3), 220, dtype=np.uint8)
    cv2.circle(image, (128, 110), 55, (160, 160, 160), -1)
    cv2.circle(image, (108, 100), 5, (20, 20, 20), -1)
    cv2.circle(image, (148, 100), 5, (20, 20, 20), -1)
    cv2.ellipse(image, (128, 125), (20, 10), 0, 0, 180, (30, 30, 30), 2)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def test_identity_score_rejects_attractive_different_face(monkeypatch) -> None:
    image = _portrait()
    monkeypatch.setattr(
        "app.evaluator.analyze_identity",
        lambda _bytes: type(
            "Identity",
            (),
            {"face_count": 1, "largest_face_ratio": 0.2, "identity_readiness": "ready"},
        )(),
    )
    monkeypatch.setattr(
        "app.evaluator._quality_score",
        lambda _bytes: 95.0,
    )
    adapter = SequenceAdapter(
        [
            [1.0, 0.0],
            [-1.0, 0.0],
        ]
    )

    ranking = rank_identity_first_candidates(image, [image], adapter, likeness_threshold=0.35)

    result = ranking.evaluations[0]
    assert result.status == "reject"
    assert result.final_score <= 49.0
    assert ranking.recommended_index is None


def test_identity_score_prefers_the_best_likeness(monkeypatch) -> None:
    image = _portrait()
    monkeypatch.setattr(
        "app.evaluator.analyze_identity",
        lambda _bytes: type(
            "Identity",
            (),
            {"face_count": 1, "largest_face_ratio": 0.2, "identity_readiness": "ready"},
        )(),
    )
    monkeypatch.setattr("app.evaluator._quality_score", lambda _bytes: 85.0)
    adapter = SequenceAdapter(
        [
            [1.0, 0.0],
            [0.8, 0.2],
            [1.0, 0.0],
            [0.2, 0.8],
        ]
    )

    ranking = rank_identity_first_candidates(image, [image, image], adapter, likeness_threshold=0.1)

    assert ranking.recommended_index == 0
    assert ranking.evaluations[0].final_score > ranking.evaluations[1].final_score
    assert ranking.evaluations[0].rank == 1
