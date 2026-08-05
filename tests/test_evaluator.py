from __future__ import annotations

from dataclasses import dataclass

import app.evaluator as evaluator


@dataclass(frozen=True)
class FakeAnalysis:
    blur_level: str = "low"
    lighting: str = "good"
    megapixels: float = 2.0


@dataclass(frozen=True)
class FakeIdentity:
    face_count: int
    largest_face_ratio: float
    identity_readiness: str = "ready"


def test_rank_candidates_recommends_best_structural_match(monkeypatch) -> None:
    identities = iter(
        [
            FakeIdentity(face_count=1, largest_face_ratio=0.25),
            FakeIdentity(face_count=1, largest_face_ratio=0.24),
            FakeIdentity(face_count=1, largest_face_ratio=0.10),
        ]
    )
    monkeypatch.setattr(evaluator, "analyze_identity", lambda _data: next(identities))
    monkeypatch.setattr(evaluator, "analyze_image", lambda _data: FakeAnalysis())

    ranking = evaluator.rank_candidates(b"original", [b"close", b"far"])

    assert ranking.recommended_index == 0
    assert ranking.evaluations[0].rank == 1
    assert ranking.evaluations[0].status == "pass"
    assert ranking.method.endswith("non_biometric")


def test_rank_candidates_rejects_changed_face_count(monkeypatch) -> None:
    identities = iter(
        [
            FakeIdentity(face_count=1, largest_face_ratio=0.25),
            FakeIdentity(face_count=2, largest_face_ratio=0.25),
        ]
    )
    monkeypatch.setattr(evaluator, "analyze_identity", lambda _data: next(identities))
    monkeypatch.setattr(evaluator, "analyze_image", lambda _data: FakeAnalysis())

    ranking = evaluator.rank_candidates(b"original", [b"candidate"])

    assert ranking.recommended_index is None
    assert ranking.evaluations[0].status == "reject"
    assert ranking.evaluations[0].score <= 49


def test_rank_candidates_requires_candidates() -> None:
    try:
        evaluator.rank_candidates(b"original", [])
    except ValueError as exc:
        assert "At least one" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
