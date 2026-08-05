from __future__ import annotations

import base64
import io
from dataclasses import asdict, dataclass

from PIL import Image, ImageOps, UnidentifiedImageError


_ALLOWED_FORMATS = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}
_CONTENT_TYPES = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}


@dataclass(frozen=True)
class FinalRenderResult:
    candidate_id: str
    filename: str
    content_type: str
    width: int
    height: int
    format: str
    quality: int
    image_base64: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def render_selected_candidate(
    *,
    candidate_id: str,
    source_filename: str,
    image_base64: str,
    output_format: str = "png",
    max_dimension: int | None = None,
    quality: int = 95,
    allow_upscale: bool = False,
) -> FinalRenderResult:
    normalized_format = output_format.strip().lower()
    if normalized_format == "jpg":
        normalized_format = "jpeg"
    if normalized_format not in _ALLOWED_FORMATS:
        raise ValueError("output_format must be png, jpeg, or webp.")
    if not 1 <= quality <= 100:
        raise ValueError("quality must be between 1 and 100.")
    if max_dimension is not None and not 256 <= max_dimension <= 8192:
        raise ValueError("max_dimension must be between 256 and 8192 pixels.")

    try:
        source_bytes = base64.b64decode(image_base64, validate=True)
    except ValueError as exc:
        raise ValueError("Selected candidate contains invalid image data.") from exc

    try:
        with Image.open(io.BytesIO(source_bytes)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Selected candidate is not a readable image.") from exc

    if max_dimension is not None:
        current_max = max(image.size)
        should_resize = current_max > max_dimension or (allow_upscale and current_max < max_dimension)
        if should_resize:
            scale = max_dimension / current_max
            target = (
                max(1, round(image.width * scale)),
                max(1, round(image.height * scale)),
            )
            image = image.resize(target, Image.Resampling.LANCZOS)

    output = io.BytesIO()
    save_options: dict[str, object] = {"format": _ALLOWED_FORMATS[normalized_format]}
    if normalized_format in {"jpeg", "webp"}:
        save_options["quality"] = quality
    if normalized_format == "jpeg":
        save_options["optimize"] = True
    image.save(output, **save_options)

    stem = source_filename.rsplit(".", 1)[0] or "portrait"
    extension = "jpg" if normalized_format == "jpeg" else normalized_format
    return FinalRenderResult(
        candidate_id=candidate_id,
        filename=f"{stem}-final.{extension}",
        content_type=_CONTENT_TYPES[normalized_format],
        width=image.width,
        height=image.height,
        format=normalized_format,
        quality=quality,
        image_base64=base64.b64encode(output.getvalue()).decode("ascii"),
    )
