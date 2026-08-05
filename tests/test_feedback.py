from __future__ import annotations

from pathlib import Path

import pytest

from app.feedback import FeedbackStore


def test_feedback_is_persisted_without_image_data(tmp_path: Path) -> None:
    store = FeedbackStore(str(tmp_path / "feedback.sqlite3"))

    created = store.create(
        session_id="session-1",
        candidate_id="b",
        rating=5,
        accepted=True,
        reasons=["best_likeness", "best_style"],
        comment="This one looks like the original person.",
    )
    results = store.list_for_session("session-1")

    assert created.candidate_id == "B"
    assert created.accepted is True
    assert len(results) == 1
    assert results[0] == created
    assert "image" not in results[0].to_dict()


def test_feedback_rejects_unknown_reason(tmp_path: Path) -> None:
    store = FeedbackStore(str(tmp_path / "feedback.sqlite3"))

    with pytest.raises(ValueError, match="Unknown feedback reason"):
        store.create(
            session_id="session-1",
            candidate_id="A",
            rating=3,
            accepted=False,
            reasons=["made_up_reason"],
        )


def test_feedback_validates_candidate_and_rating(tmp_path: Path) -> None:
    store = FeedbackStore(str(tmp_path / "feedback.sqlite3"))

    with pytest.raises(ValueError, match="candidate_id"):
        store.create("session-1", "Z", 4, False)
    with pytest.raises(ValueError, match="rating"):
        store.create("session-1", "A", 0, False)
