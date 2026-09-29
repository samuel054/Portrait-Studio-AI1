"""Bounded image decoding and EXIF-free, consistently oriented uploads."""
from __future__ import annotations

import io
import warnings

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from app.settings import get_settings

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


def normalize_upload(data: bytes) -> bytes:
    settings = get_settings()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise HTTPException(415, "Upload a JPG, PNG, or WEBP image.")
                if source.width * source.height > settings.max_image_pixels:
                    raise HTTPException(413, "The image pixel dimensions exceed the safe limit.")
                if getattr(source, "n_frames", 1) != 1:
                    raise HTTPException(415, "Choose a still photo, rather than an animated image.")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGB")
                # A fresh image excludes EXIF, GPS, comments, and other source metadata.
                clean = Image.new("RGB", image.size)
                clean.paste(image)
                output = io.BytesIO()
                clean.save(output, format="PNG")
                return output.getvalue()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(413, "The image pixel dimensions exceed the safe limit.") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(400, "The uploaded image is corrupt or unreadable.") from exc


async def read_upload(file: UploadFile) -> bytes:
    settings = get_settings()
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Upload a JPG, PNG, or WEBP image.")
    data = await file.read(settings.max_upload_bytes + 1)
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"The image exceeds the {settings.max_upload_mb} MB limit.")
    return await run_in_threadpool(normalize_upload, data)
