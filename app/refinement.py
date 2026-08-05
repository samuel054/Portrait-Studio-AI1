from __future__ import annotations

from dataclasses import replace

from app.planner import PortraitPlan, build_portrait_plan

_ALLOWED_OPERATIONS = {
    "background",
    "lighting",
    "color",
    "clothing",
    "cleanup",
}
_BLOCKED_TERMS = {
    "different face",
    "change face",
    "replace face",
    "change age",
    "younger",
    "older",
    "change ethnicity",
    "change gender",
    "remove glasses",
    "change hairstyle",
}


def build_refinement_plan(
    *,
    style_id: str,
    operation: str,
    instruction: str,
    crop: str = "original",
    background: str = "keep",
    output_type: str = "social",
    preserve_pose: bool = True,
    preserve_clothing: bool = True,
    strength: float = 0.25,
) -> PortraitPlan:
    """Create a narrowly scoped refinement plan that keeps identity locked.

    Refinement is intentionally conservative. Requests that explicitly change identity-defining
    traits are rejected rather than forwarded to a generator.
    """
    normalized_operation = operation.strip().lower()
    if normalized_operation not in _ALLOWED_OPERATIONS:
        choices = ", ".join(sorted(_ALLOWED_OPERATIONS))
        raise ValueError(f"Unsupported refinement operation. Choose one of: {choices}.")

    normalized_instruction = " ".join(instruction.strip().split())
    if not normalized_instruction:
        raise ValueError("A refinement instruction is required.")
    if len(normalized_instruction) > 500:
        raise ValueError("Refinement instruction must be 500 characters or fewer.")

    lowered = normalized_instruction.lower()
    blocked = sorted(term for term in _BLOCKED_TERMS if term in lowered)
    if blocked:
        raise ValueError(
            "Refinement cannot change identity-defining traits: " + ", ".join(blocked) + "."
        )
    if not 0.05 <= strength <= 0.50:
        raise ValueError("Refinement strength must be between 0.05 and 0.50.")

    base = build_portrait_plan(
        style_id=style_id,
        crop=crop,
        background=background,
        output_type=output_type,
        preserve_pose=preserve_pose,
        preserve_clothing=preserve_clothing,
    )
    refinement_rules = (
        f"Refinement operation: {normalized_operation}.",
        f"Apply only this requested change: {normalized_instruction}.",
        f"Use a conservative edit strength of {strength:.2f}.",
        "Keep the selected portrait's face, expression, hair, accessories, body proportions, and pose unchanged unless the approved operation requires otherwise.",
    )
    negative_rules = base.negative_rules + (
        "Do not regenerate or reinterpret the face during refinement.",
        "Do not change identity-defining traits while applying the requested edit.",
    )
    prompt = " ".join(base.identity_rules + base.style_rules + refinement_rules + negative_rules)
    return replace(
        base,
        style_rules=base.style_rules + refinement_rules,
        negative_rules=negative_rules,
        prompt=prompt,
    )
