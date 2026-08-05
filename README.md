# Portrait Studio AI

Identity-first portrait creation. The current working slice analyzes a photo, detects faces, measures identity readiness, and can apply conservative non-generative enhancement before style generation.

## Current build

- FastAPI service
- JPG, PNG, and WEBP upload validation
- Resolution, megapixel, blur, and lighting analysis
- OpenCV frontal-face detection
- Multiple-face bounding boxes and relative face-size measurement
- Identity-readiness and identity-risk classification
- Identity-safe enhancement using lighting correction, gentle denoising, conservative sharpening, and non-generative upscaling
- Before-and-after quality and face-count reports
- Automatic routing to `enhance`, `request_better_photo`, or `style_selection`
- Unit tests for analysis, identity detection, and enhancement

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

## Enhance a portrait

```bash
curl -X POST http://127.0.0.1:8000/v1/enhance \
  -F "file=@portrait.jpg" \
  -o enhancement-response.json
```

The enhancement response contains:

- the enhanced PNG encoded as Base64,
- operations applied,
- before-and-after quality measurements,
- before-and-after identity-readiness reports,
- a face-count preservation check,
- and the recommended next step.

The enhancer deliberately avoids generative face restoration. It improves presentation without inventing facial details or replacing the person's identity.

## Privacy boundary

Uploaded bytes are processed in memory. This build does not create a reusable face identity or permanently store biometric data.

## Next build target

Add the first curated style-selection contract and a prompt recipe builder for identity-preserving illustration generation.
