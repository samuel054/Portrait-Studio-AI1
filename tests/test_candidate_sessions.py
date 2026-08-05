from __future__ import annotations

import base64

import pytest

from app.candidate_sessions import CandidateSessionStore
from app.comfyui import ComfyUIImage, ComfyUIJobResult
from app.identity_score import IdentityFirstEvaluation, IdentityFirstRanking


def _image(name: str) -> ComfyUIImage:
    return ComfyUIImage(
        filename=name,
        subfolder="",
        image_type="output",
        content_type="image/png",
        image_base64=base64.b64encode(name.encode("utf-8")).decode("ascii"),
    )


def _ranking() -> IdentityFirstRanking:
    return IdentityFirstRanking(
        evaluations=(
            IdentityFirstEvaluation(
                index=0,
                rank=2,
                final_score=84.0,
                status="pass",
                structural_score=80.0,
                likeness_score=86.0,
                cosine_similarity=0.72,
                reasons=("Candidate passed identity checks.",),
            ),
            IdentityFirstEvaluation(
                index=1,
                rank=1,
                final_score=94.0,
                status="pass",
                structural_score=91.0,
                likeness_score=95.0,
                cosine_similarity=0.90,
                reasons=("Best identity match.",),
            ),
            IdentityFirstEvaluation(
                index=2,
                rank=3,
                final_score=42.0,
                status="reject",
                structural_score=75.0,
                likeness_score=28.0,
                cosine_similarity=-0.10,
                reasons=("Different-looking face.",),
            ),
        ),
        recommended_index=1,
        method="identity_first_v1_70_likeness_30_structural",
        likeness_threshold=0.35,
    )


def test_session_only_exposes_safe_candidates_in_rank_order() -> None:
    store = CandidateSessionStore()
    job = ComfyUIJobResult(
        prompt_id="prompt-1",
        status="completed",
        images=(_image("zero.png"), _image("one.png"), _image("two.png")),
    )

    session = store.create(job, _ranking())

    assert [item.id for item in session.candidates] == ["A", "B"]
    assert [item.source_index for item in session.candidates] == [1, 0]
    assert session.candidates[0].recommended is True
    assert all(item.source_index != 2 for item in session.candidates)


def test_user_can_select_an_available_candidate() -> None:
    store = CandidateSessionStore()
    session = store.create(
        ComfyUIJobResult(
            prompt_id="prompt-1",
            status="completed",
            images=(_image("zero.png"), _image("one.png"), _image("two.png")),
        ),
        _ranking(),
    )

    selected = store.select(session.id, "b")

    assert selected.status == "selected"
    assert selected.selected_candidate_id == "B"


def test_session_refuses_when_every_candidate_is_rejected() -> None:
    store = CandidateSessionStore()
    ranking = IdentityFirstRanking(
        evaluations=(
            IdentityFirstEvaluation(
                index=0,
                rank=1,
                final_score=30.0,
                status="reject",
                structural_score=50.0,
                likeness_score=20.0,
                cosine_similarity=-0.2,
                reasons=("Identity mismatch.",),
            ),
        ),
        recommended_index=None,
        method="identity_first_v1_70_likeness_30_structural",
        likeness_threshold=0.35,
    )

    with pytest.raises(ValueError, match="All generated candidates failed"):
        store.create(
            ComfyUIJobResult(
                prompt_id="prompt-1",
                status="completed",
                images=(_image("unsafe.png"),),
            ),
            ranking,
        )
