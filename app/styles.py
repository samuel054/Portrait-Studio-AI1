from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class StyleDefinition:
    id: str
    name: str
    category: str
    description: str
    identity_priority: str
    pose_preservation: bool
    clothing_preservation: bool
    background_modes: tuple[str, ...]
    output_types: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["background_modes"] = list(self.background_modes)
        data["output_types"] = list(self.output_types)
        return data


STYLE_CATALOG: tuple[StyleDefinition, ...] = (
    StyleDefinition(
        id="soft_lifestyle_illustration",
        name="Soft Lifestyle Illustration",
        category="illustration",
        description="Warm editorial character illustration with soft colors and gentle shading.",
        identity_priority="very_high",
        pose_preservation=True,
        clothing_preservation=True,
        background_modes=("keep", "blur", "replace", "transparent", "surprise"),
        output_types=("social", "canvas", "frame", "gift"),
    ),
    StyleDefinition(
        id="premium_chibi",
        name="Premium Chibi",
        category="chibi",
        description="Cute proportions with detailed facial cues and polished shading.",
        identity_priority="high",
        pose_preservation=True,
        clothing_preservation=True,
        background_modes=("replace", "transparent", "surprise"),
        output_types=("canvas", "frame", "gift", "sticker"),
    ),
    StyleDefinition(
        id="friendly_caricature",
        name="Friendly Caricature",
        category="caricature",
        description="Recognizable, playful exaggeration of distinctive facial features.",
        identity_priority="very_high",
        pose_preservation=True,
        clothing_preservation=True,
        background_modes=("keep", "replace", "transparent", "surprise"),
        output_types=("social", "canvas", "frame", "gift"),
    ),
    StyleDefinition(
        id="soft_watercolor",
        name="Soft Watercolor",
        category="painting",
        description="Light watercolor washes with preserved facial structure and clothing colors.",
        identity_priority="very_high",
        pose_preservation=True,
        clothing_preservation=True,
        background_modes=("keep", "blur", "replace", "surprise"),
        output_types=("canvas", "frame", "gift"),
    ),
    StyleDefinition(
        id="storybook_character",
        name="Storybook Character",
        category="illustration",
        description="Cozy hand-painted character art with a gentle narrative atmosphere.",
        identity_priority="high",
        pose_preservation=True,
        clothing_preservation=True,
        background_modes=("replace", "surprise"),
        output_types=("canvas", "frame", "gift"),
    ),
)


def list_styles(category: str | None = None) -> list[dict[str, object]]:
    styles = STYLE_CATALOG
    if category:
        normalized = category.strip().lower()
        styles = tuple(style for style in styles if style.category == normalized)
    return [style.to_dict() for style in styles]


def get_style(style_id: str) -> StyleDefinition | None:
    normalized = style_id.strip().lower()
    return next((style for style in STYLE_CATALOG if style.id == normalized), None)
