# Portrait Studio AI

A local portrait studio: upload one photo, choose framing/background/style, generate 2–4 options, review likeness-checked candidates, refine, and download PNG, JPEG, or WebP.

## Start here

Follow [Local setup](docs/LOCAL_SETUP.md). No paid image API is required.

- **Web:** Next.js 15 / React 19, responsive desktop and mobile UI.
- **API:** FastAPI, Pillow, OpenCV, SQLite session storage.
- **Likeness:** local OpenCV YuNet + SFace models, installed with a checksum-verified setup script. InsightFace remains an optional adapter.
- **Generation:** local ComfyUI, with a configurable SDXL image-to-image workflow.
- **Background removal/blur:** optional local rembg / U2Net model.

The application reports whether its engine and likeness models are ready. Photo analysis works before model setup. It does not fabricate portraits when the image engine is unavailable.

## Working flow

1. Validate the photo, correct EXIF orientation, strip metadata, and check face visibility.
2. Choose a compatible style, framing, background, intended use, and 2–4 candidates.
3. Apply conservative enhancement and run the configured local workflow.
4. Compare candidates with the original photo. Only candidates passing both quality and likeness checks are shown.
5. Confirm A–D explicitly. Changing the choice requires confirmation again.
6. Optionally request a finishing touch; refined options go through the same checks against the original source.
7. Choose PNG/JPEG/WebP and a size, then download. Feedback is optional.

The current session can be restored after a browser refresh. The browser stores identifiers and options, not portrait pixels. Source/candidate data in the application's local SQLite databases expires after 60 minutes by default. Read [Privacy and limits](docs/PRIVACY_AND_LIMITS.md) for the separate ComfyUI disk retention policy.

## Validation

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
ruff check app tests
cd frontend
npm ci
npm run lint
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

Backend integration tests exercise the full HTTP workflow with a simulated image engine and face model. Browser tests cover desktop/mobile selection, refinement, export, validation, and refresh recovery. These tests do **not** establish real generated-image likeness.

Before calling a model configuration ready for release, run the [real model smoke test](docs/LOCAL_SETUP.md#real-model-check) and evaluate it on consented portraits. The SDXL starter is an image-to-image baseline, not a trained identity guarantee. Quality thresholds are provisional; no recognition-rate benchmark is claimed.
