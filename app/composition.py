from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path
import os

from PIL import Image, ImageFilter

from app.identity import analyze_identity
from app.settings import get_settings


def prepare_crop(image_bytes: bytes, crop: str) -> bytes:
    if crop in {"original", "full_body"}:
        return image_bytes
    report = analyze_identity(image_bytes)
    if report.face_count != 1:
        raise ValueError("Choose a photo with one clearly visible face.")
    face = report.faces[0]
    with Image.open(io.BytesIO(image_bytes)) as image:
        half_width = face.width * (1.1 if crop == "face" else 1.8)
        bottom = face.y + face.height * (1.65 if crop == "face" else 4.0)
        center = face.x + face.width / 2
        box = (max(0, int(center - half_width)), max(0, int(face.y - face.height * 0.5)),
               min(image.width, int(center + half_width)), min(image.height, int(bottom)))
        output = io.BytesIO()
        image.crop(box).save(output, "PNG")
        return output.getvalue()


def background_model_path() -> Path:
    return get_settings().background_model_dir / "u2netp.onnx"


@lru_cache(maxsize=1)
def background_session():
    if not background_model_path().is_file():
        raise RuntimeError("Install the local background model to remove or blur backgrounds.")
    os.environ["U2NET_HOME"] = str(background_model_path().parent.resolve())
    try:
        from rembg import new_session
    except ImportError as exc:
        raise RuntimeError("Install the optional background dependencies first.") from exc
    return new_session("u2netp", providers=["CPUExecutionProvider"])


def finish_background(image_bytes: bytes, mode: str) -> bytes:
    if mode not in {"transparent", "blur"}:
        return image_bytes
    session = background_session()
    from rembg import remove

    with Image.open(io.BytesIO(image_bytes)) as image:
        foreground = remove(image.convert("RGBA"), session=session)
        if mode == "blur":
            result = image.convert("RGBA").filter(ImageFilter.GaussianBlur(18))
            result.alpha_composite(foreground)
        else:
            result = foreground
        output = io.BytesIO()
        result.save(output, "PNG")
        return output.getvalue()
