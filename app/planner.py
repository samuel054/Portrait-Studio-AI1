from __future__ import annotations

from dataclasses import asdict, dataclass

from app.styles import StyleDefinition, get_style


ALLOWED_CROPS = {"face", "half_body", "full_body", "original"}
ALLOWED_BACKGROUNDS = {"keep", "blur", "replace", "transparent", "surprise"}
ALLOWED_OUTPUTS = {"social", "canvas", "frame", "gift", "sticker"}


@dataclass(frozen=True)
class PortraitPlan:
    style_id: str
    style_name: str
    crop: str
    background: str
    output_type: str
    preserve_pose: bool
    preserve_clothing: bool
    identity_rules: tuple[str, ...]
    style_rules: tuple[str, ...]
    negative_rules: tuple[str, ...]
    prompt: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["identity_rules"] = list(self.identity_rules)
        data["style_rules"] = list(self.style_rules)
        data["negative_rules"] = list(self.negative_rules)
        return data


def _validate_choice(value: str, allowed: set[str], field_name: str) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"Unsupported {field_name}. Choose one of: {choices}.")
    return normalized


def _style_rules(style: StyleDefinition) -> tuple[str, ...]:
    common = (
        f"Render as {style.name}.",
        style.description,
        "Keep the subject immediately recognizable as the same person.",
    )
    if style.category == "caricature":
        return common + ("Exaggerate only distinctive features gently; do not replace the face.",)
    if style.category == "chibi":
        return common + ("Use cute proportions while retaining the original facial cues.",)
    if style.category == "painting":
        return common + ("Preserve facial structure beneath the painted texture.",)
    return common + ("Use simplified illustrated details without inventing a new identity.",)


def build_portrait_plan(
    style_id: str,
    crop: str = "original",
    background: str = "keep",
    output_type: str = "social",
    preserve_pose: bool = True,
    preserve_clothing: bool = True,
) -> PortraitPlan:
    style = get_style(style_id)
    if style is None:
        raise ValueError("Unknown style ID.")

    crop = _validate_choice(crop, ALLOWED_CROPS, "crop")
    background = _validate_choice(background, ALLOWED_BACKGROUNDS, "background mode")
    output_type = _validate_choice(output_type, ALLOWED_OUTPUTS, "output type")

    if background not in style.background_modes:
        raise ValueError(f"{style.name} does not support the '{background}' background mode.")
    if output_type not in style.output_types:
        raise ValueError(f"{style.name} does not support the '{output_type}' output type.")

    identity_rules = (
        "Preserve the person's recognizable facial identity and natural skin tone.",
        "Preserve hairstyle, hairline, expression, glasses, beard, and visible accessories.",
        "Keep facial proportions and feature spacing consistent with the source photo.",
    )
    composition_rules = [f"Use the requested crop: {crop}.", f"Background mode: {background}."]
    if preserve_pose and style.pose_preservation:
        composition_rules.append("Preserve the original pose and hand positions.")
    if preserve_clothing and style.clothing_preservation:
        composition_rules.append("Preserve the original clothing design, colors, and accessories.")

    style_rules = _style_rules(style) + tuple(composition_rules)
    negative_rules = (
        "Do not invent a different face or change age, ethnicity, or gender presentation.",
        "Do not remove defining accessories or change the hairstyle.",
        "Do not add extra fingers, limbs, facial features, text, logos, or watermarks.",
        "Do not over-smooth or reconstruct the face into a generic beauty portrait.",
    )
    prompt = " ".join(identity_rules + style_rules + negative_rules)

    return PortraitPlan(
        style_id=style.id,
        style_name=style.name,
        crop=crop,
        background=background,
        output_type=output_type,
        preserve_pose=preserve_pose,
        preserve_clothing=preserve_clothing,
        identity_rules=identity_rules,
        style_rules=style_rules,
        negative_rules=negative_rules,
        prompt=prompt,
    )
