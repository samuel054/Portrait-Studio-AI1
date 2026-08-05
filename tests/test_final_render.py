from __future__ import annotations

import base64
import io

from PIL import Image

from app.final_render import render_selected_candidate


def _image_base64(size: tuple[int, int] = (1200, 800)) -> str:
    image = Image.new("RGB", size, "white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def test_final_render_resizes_without_changing_aspect_ratio() -> None:
    result = render_selected_candidate(
        candidate_id="A",
        source_filename="candidate.png",
        image_base64=_image_base64(),
        output_format="jpeg",
        max_dimension=600,
        quality=90,
    )

    assert result.filename == "candidate-final.jpg"
    assert result.content_type == "image/jpeg"
    assert result.width == 600
    assert result.height == 400
    assert base64.b64decode(result.image_base64).startswith(b"\xff\xd8")


def test_final_render_does_not_upscale_by_default() -> None:
    result = render_selected_candidate(
        candidate_id="B",
        source_filename="small.png",
        image_base64=_image_base64((320, 240)),
        max_dimension=1024,
    )

    assert result.width == 320
    assert result.height == 240


def test_final_render_rejects_invalid_format() -> None:
    try:
        render_selected_candidate(
            candidate_id="A",
            source_filename="candidate.png",
            image_base64=_image_base64(),
            output_format="tiff",
        )
    except ValueError as exc:
        assert "png, jpeg, or webp" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
