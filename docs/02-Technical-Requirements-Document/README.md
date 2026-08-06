# Technical Requirements Document (TRD)

**Version:** 1.0  
**Status:** Approved baseline  
**Owner:** Engineering Team

## 1. Purpose

Define the architecture, system boundaries, technical constraints, interfaces, security controls, quality gates, testing expectations, and deployment requirements for Portrait Studio AI.

## 2. Technology Baseline

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | Next.js 15, React 19, TypeScript | Upload, analysis, style selection, progress, candidate selection, refinement, export |
| API | FastAPI, Pydantic | Validation, orchestration, contracts, errors |
| Image processing | OpenCV, Pillow, NumPy | Analysis, conservative enhancement, render/export |
| Generation runtime | ComfyUI | Local workflow execution and checkpoint interchange |
| Identity comparison | InsightFace / ArcFace | Same-session face embedding and likeness score |
| MVP persistence | SQLite and process memory | Feedback and temporary local workflow state |
| CI | GitHub Actions | Backend lint/tests and frontend build |

## 3. High-Level Architecture

```text
Browser / Next.js
        |
        v
FastAPI Application
  |-- Upload Validation
  |-- Image Analyzer
  |-- Conservative Enhancer
  |-- Identity Readiness
  |-- Style and Prompt Planner
  |-- Generator Adapter Registry
  |-- ComfyUI Client
  |-- Candidate Evaluator
  |-- Likeness Adapter
  |-- Candidate Sessions
  |-- Refinement and Rendering
  |-- Feedback Store
        |
        v
Local GPU Runtime / ComfyUI
  |-- Versioned workflow template
  |-- Approved open-source checkpoint
  |-- Optional identity-conditioning nodes
```

## 4. Architectural Rules

1. Model-specific behavior must remain behind adapter interfaces.
2. The application must not depend permanently on one checkpoint.
3. The frontend must communicate with FastAPI, never directly with ComfyUI.
4. Identity-sensitive decisions must include machine-readable reasons.
5. Generation state must be explicit: queued, running, completed, or failed.
6. Portrait pixels and embeddings must not appear in logs.
7. Source images and embeddings must expire according to a documented lifecycle.
8. AI workflow templates must be controlled and versioned by the application.

## 5. Core Components

### 5.1 Upload Validator

- Accept configured image MIME types only.
- Enforce byte-size and decoded-pixel limits.
- Reject empty, corrupt, and decompression-bomb payloads.
- Normalize orientation from EXIF metadata.

### 5.2 Image Analyzer

- Return width, height, megapixels, blur classification, lighting classification, and enhancement recommendation.
- Complete within the configured CPU latency target.

### 5.3 Identity Readiness

- Detect face count and bounding boxes.
- Identify the largest or most prominent face.
- Return readiness and risk classifications.
- Reject or request a better photo when a reliable face cannot be extracted.

### 5.4 Conservative Enhancer

- Improve lighting, noise, sharpness, and minimum dimensions.
- Avoid generative face restoration in the default pipeline.
- Compare face count before and after processing.
- Return before-and-after quality reports.

### 5.5 Style and Portrait Planner

- Validate style, crop, background, and output compatibility.
- Build identity rules, style rules, composition rules, and negative rules.
- Produce a deterministic portrait plan consumable by any generator adapter.

### 5.6 Generator Adapter

Required contract:

```python
generate(request: GenerationRequest) -> GenerationResult
```

The adapter must expose:

- Identifier and capabilities
- Local/open-source flags
- Candidate-count limits
- Seed support
- Reference-image support
- Submission and failure behavior

### 5.7 ComfyUI Integration

- Upload the working reference image to a controlled subfolder.
- Load a versioned workflow JSON.
- Replace prompt, negative prompt, seed, reference image, and candidate count.
- Submit to `/prompt`.
- Poll `/history/{prompt_id}`.
- Retrieve outputs through `/view`.
- Apply network timeouts and clear errors.

### 5.8 Candidate Evaluation

- Validate image payloads.
- Compare face count and facial scale.
- Measure blur, lighting, dimensions, and structural quality.
- Compare face embeddings with the source image.
- Apply hard reject rules before composite ranking.
- Expose only safe candidates.

### 5.9 Candidate Session

- Assign stable A-D candidate IDs.
- Store recommendation and reasons.
- Require explicit user selection before final render.
- MVP may use a thread-safe in-memory store; production must use durable shared storage.

### 5.10 Refinement and Render

- Refinement must use the selected portrait as reference.
- Block identity-changing instructions.
- Limit edit strength to a conservative configurable range.
- Render PNG, JPEG, and WebP with aspect-ratio-preserving resize.
- Do not upscale unless explicitly requested.

## 6. API Requirements

Minimum endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/v1/analyze` | Quality and identity-readiness analysis |
| POST | `/v1/enhance` | Conservative enhancement |
| GET | `/v1/styles` | Style catalog |
| GET | `/v1/styles/{style_id}` | Style detail |
| POST | `/v1/plans` | Portrait plan creation |
| GET | `/v1/generators` | Adapter registry |
| POST | `/v1/generate` | Generation submission |
| POST | `/v1/portrait-jobs` | Upload-to-generation orchestration |
| GET | `/v1/generations/{prompt_id}` | Generation polling |
| POST | `/v1/candidate-sessions` | Retrieval, evaluation, and safe candidate creation |
| GET | `/v1/candidate-sessions/{session_id}` | Session retrieval |
| POST | `/v1/candidate-sessions/{session_id}/selection` | Candidate selection |
| POST | `/v1/candidate-sessions/{session_id}/refine` | Safe refinement |
| POST | `/v1/candidate-sessions/{session_id}/render` | Final export |
| POST | `/v1/candidate-sessions/{session_id}/feedback` | Feedback creation |
| GET | `/v1/candidate-sessions/{session_id}/feedback` | Feedback retrieval |

## 7. Identity-First Scoring

Baseline composite score:

```text
final_score = 0.70 * likeness_score + 0.30 * structural_quality_score
```

Hard rejection overrides the composite score when:

- No face is detected.
- Face count changes unexpectedly.
- Similarity is below the configured threshold.
- The image is corrupt.
- Severe anatomical or facial artifacts are present.
- The output appears to depict a different person.

## 8. Security and Privacy

- Production traffic must use HTTPS.
- ComfyUI must not be publicly exposed.
- User-controlled workflow JSON must not be executed.
- Logs must exclude Base64 images, embeddings, and unnecessary EXIF data.
- Face embeddings are for same-session comparison only.
- Refinement instructions must be validated against prohibited identity changes.
- A retention and deletion policy is mandatory before public beta.
- Secrets must be supplied through environment or secret-management systems.

## 9. Performance Targets

| Operation | Initial Target |
|---|---|
| Analysis | P95 under 2 seconds on reference CPU |
| Enhancement | Under 3 seconds on reference CPU for standard portrait |
| Generation | Under 60 seconds on reference GPU when queue is empty |
| Evaluation | Under 5 seconds for four candidates |
| Candidate ranking | Under 2 seconds after metrics exist |
| Export | Under 2 seconds for standard sizes |

## 10. Reliability and Observability

- External calls require explicit connect/read timeouts.
- Every workflow should carry a workflow or prompt identifier.
- Logs should include stage, duration, outcome, and normalized error code.
- Metrics should include API latency, generation latency, failure rate, queue depth, GPU utilization, and identity rejection rate.
- Production generation must move to a durable job queue before horizontal scaling.

## 11. Deployment Requirements

### Local MVP

```text
Docker Compose
  - Next.js web
  - FastAPI API
  - ComfyUI GPU runtime
  - SQLite volume
  - Optional Caddy/Nginx reverse proxy
```

### Production-Hardening Path

- PostgreSQL for durable application data
- Redis or durable queue for jobs and shared state
- Encrypted object storage with short-lived URLs
- Separate CPU and GPU worker pools
- Authentication, rate limits, quotas, and abuse controls
- Centralized metrics, logs, alerts, backups, and recovery procedures

## 12. Testing Requirements

- Unit tests for analyzer, enhancer, planner, adapters, likeness, ranking, rendering, refinement, and feedback.
- API tests for validation, status codes, and workflow transitions.
- Frontend strict type-check and production build.
- Mocked ComfyUI integration tests in CI.
- Real-GPU smoke tests before model workflow releases.
- Golden-dataset regression tests before production releases.
- Human recognition evaluation before changing identity thresholds.

## 13. Technical Acceptance Criteria

- All relevant Must requirements are implemented.
- CI passes from a clean checkout for Python 3.11/3.12 and supported Node version.
- The complete local stack can run without a paid API.
- Identity-failed candidates cannot be returned as safe candidates.
- Model and workflow versions are visible in operational metadata.
- Privacy boundaries are documented and tested.
- End-to-end generation is verified with at least one approved local model workflow.
