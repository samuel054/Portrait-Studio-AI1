from __future__ import annotations

import pytest

from app.refinement import build_refinement_plan


def test_refinement_plan_adds_scoped_instruction_and_identity_lock() -> None:
    plan = build_refinement_plan(
        style_id="soft_lifestyle_illustration",
        operation="background",
        instruction="Replace the background with a warm garden at sunset.",
        strength=0.20,
    )

    assert "warm garden at sunset" in plan.prompt
    assert "Do not regenerate or reinterpret the face" in plan.negative_rules
    assert "0.20" in plan.prompt


def test_refinement_rejects_identity_change_requests() -> None:
    with pytest.raises(ValueError, match="identity-defining"):
        build_refinement_plan(
            style_id="soft_lifestyle_illustration",
            operation="cleanup",
            instruction="Make the person younger and change hairstyle.",
        )


def test_refinement_rejects_excessive_strength() -> None:
    with pytest.raises(ValueError, match="strength"):
        build_refinement_plan(
            style_id="soft_lifestyle_illustration",
            operation="lighting",
            instruction="Add softer window light.",
            strength=0.8,
        )
