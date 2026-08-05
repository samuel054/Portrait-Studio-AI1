from __future__ import annotations

import base64
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from app.analyzer import analyze_image
from app.enhancer import enhance_image
from app.identity import analyze_identity
from app.styles import get_style, list_styles

app = FastAPI(title="Portrait Studio AI", version="0.4.0")

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024
ImageUpload = Annotated[UploadFile, File()]


async def _read_upload(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WEBP image.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="The image exceeds the 20 MB limit.")
    return data


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/styles")
def styles(category: str | None = Query(default=None)) -> dict[str, object]:
    items = list_styles(category)
    return {"count": len(items), "styles": items}


@app.get("/v1/styles/{style_id}")
def style_detail(style_id: str) -> dict[str, object]:
    style = get_style(style_id)
    if style is None:
        raise HTTPException(status_code=404, detail="Style not found.")
    return style.to_dict()


@app.post("/v1/analyze")
async def analyze(file: ImageUpload) -> dict[str, object]:
    data = await _read_upload(file)

    try:
        image_report = analyze_image(data)
        identity_report = analyze_identity(data)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if image_report.needs_enhancement:
        next_step = "enhance"
    elif identity_report.identity_readiness in {"not_ready", "needs_better_photo"}:
        next_step = "request_better_photo"
    else:
        next_step = "style_selection"

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "analysis": image_report.to_dict(),
        "identity": identity_report.to_dict(),
        "next_step": next_step,
    }


@app.post("/v1/enhance")
async def enhance(file: ImageUpload) -> dict[str, object]:
    data = await _read_upload(file)

    try:
        enhanced_bytes, report = enhance_image(data)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "filename": file.filename,
        "output_content_type": "image/png",
        "enhancement": report.to_dict(),
        "enhanced_image_base64": base64.b64encode(enhanced_bytes).decode("ascii"),
        "next_step": (
            "style_selection"
            if report.identity_after.identity_readiness not in {"not_ready", "needs_better_photo"}
            else "request_better_photo"
        ),
    }
