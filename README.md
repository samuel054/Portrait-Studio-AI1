# Portrait Studio AI

Identity-first portrait creation. The current working slice accepts a photo, validates it, measures image quality, detects frontal faces, and produces an identity-readiness report before style generation.

## Current build

- FastAPI service
- JPG, PNG, and WEBP upload validation
- Resolution and megapixel analysis
- Blur and lighting estimation
- OpenCV frontal-face detection
- Multiple-face bounding boxes and relative face-size measurement
- Identity readiness and identity-risk classification
- Helpful guidance when a photo is unsuitable
- Automatic routing to `enhance`, `request_better_photo`, or `style_selection`
- Unit tests for image and identity analysis

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

## Analyze a portrait

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
  "identity": {
    "face_count": 1,
    "faces": [
      {
        "x": 630,
        "y": 180,
        "width": 420,
        "height": 420,
        "area_ratio": 0.0851
      }
    ],
    "largest_face_ratio": 0.0851,
    "identity_readiness": "ready",
    "identity_risk": "low",
    "guidance": [
      "Face visibility is suitable for identity analysis."
    ]
  },
  "next_step": "style_selection"
}
```

## Privacy boundary

This build analyzes the uploaded bytes in memory and returns a report. It does not create a reusable face identity or permanently store biometric data.

## Next build target

Add automatic, identity-safe photo enhancement with before-and-after quality measurements.
