from fastapi import FastAPI, File, HTTPException, UploadFile

from app.analyzer import analyze_image

app = FastAPI(title="Portrait Studio AI", version="0.1.0")

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/analyze")
async def analyze(file: UploadFile = File(...)) -> dict[str, object]:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, or WEBP image.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="The image exceeds the 20 MB limit.")

    try:
        report = analyze_image(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "analysis": report.to_dict(),
        "next_step": "enhance" if report.needs_enhancement else "identity_analysis",
    }
