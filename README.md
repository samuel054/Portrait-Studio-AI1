# Portrait Studio AI

Identity-first portrait creation. The first working slice accepts a photo, validates it, measures basic image quality, and decides whether enhancement is required before identity analysis.

## Current build

- FastAPI service
- JPG, PNG, and WEBP upload validation
- Resolution and megapixel analysis
- Blur estimation
- Lighting estimation
- Automatic `enhance` or `identity_analysis` routing decision
- Unit tests for the analyzer

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open the interactive API at `http://127.0.0.1:8000/docs`.

## Test

```bash
pytest
```

## First endpoint

```bash
curl -X POST http://127.0.0.1:8000/v1/analyze \
  -F "file=@portrait.jpg"
```

Example response:

```json
{
  "filename": "portrait.jpg",
  "content_type": "image/jpeg",
  "analysis": {
    "width": 1920,
    "height": 1080,
    "megapixels": 2.07,
    "blur_score": 186.42,
    "blur_level": "low",
    "brightness": 132.7,
    "lighting": "good",
    "needs_enhancement": false
  },
  "next_step": "identity_analysis"
}
```

## Next build target

Add face detection and an identity-preservation report without permanently storing biometric data.
