from __future__ import annotations

import numpy as np

from app.likeness import compare_likeness


class FakeAdapter:
    id = "fake"

    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = iter(vectors)

    def embed(self, _image_bytes: bytes) -> np.ndarray:
        return np.asarray(next(self.vectors), dtype=np.float32)


def test_likeness_passes_close_embeddings() -> None:
    result = compare_likeness(
        b"original",
        b"candidate",
        FakeAdapter([[1.0, 0.0], [0.98, 0.20]]),
        threshold=0.35,
    )

    assert result.decision == "pass"
    assert result.cosine_similarity > 0.9
    assert result.likeness_score > 95


def test_likeness_rejects_opposite_embeddings() -> None:
    result = compare_likeness(
        b"original",
        b"candidate",
        FakeAdapter([[1.0, 0.0], [-1.0, 0.0]]),
        threshold=0.35,
    )

    assert result.decision == "reject"
    assert result.likeness_score == 0.0


def test_likeness_marks_borderline_result_for_review() -> None:
    result = compare_likeness(
        b"original",
        b"candidate",
        FakeAdapter([[1.0, 0.0], [0.40, 0.9165]]),
        threshold=0.35,
    )

    assert result.decision == "review"


def test_likeness_rejects_incompatible_embeddings() -> None:
    try:
        compare_likeness(
            b"original",
            b"candidate",
            FakeAdapter([[1.0, 0.0], [1.0, 0.0, 0.0]]),
        )
    except ValueError as exc:
        assert "incompatible" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
