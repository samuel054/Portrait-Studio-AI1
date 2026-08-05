# Chapter 9 — System Architecture

## Purpose

Portrait Studio AI is an identity-first portrait orchestration platform. Its architecture must preserve identity, support multiple AI providers, validate every generated portrait, and keep the user experience independent of any single model vendor.

## Core Architectural Principles

1. **Identity first** — every pipeline decision must prioritize recognizability over style intensity.
2. **Provider independence** — no core workflow may depend on a single image model or API provider.
3. **Stage isolation** — analysis, enhancement, generation, validation, and delivery must be separable and replaceable.
4. **Quality gates** — generated images are never shown until required checks pass.
5. **Retryability** — each portrait job is resumable and every stage is independently retryable.
6. **Privacy by design** — user images, embeddings, and generated outputs must have explicit retention rules.
7. **Observability** — each stage records status, latency, model choice, failure reason, and quality results.

## High-Level Flow

```text
Client
  ↓
API Gateway
  ↓
Portrait Job Service
  ↓
Portrait Intelligence Engine
  ↓
Photo Analysis
  ↓
Conditional Enhancement
  ↓
IdentityLock Profile
  ↓
StyleDNA Resolution
  ↓
Model Router
  ↓
Preview Generation
  ↓
AI Critic + Quality Gates
  ↓
User Preview Selection
  ↓
Final Render
  ↓
Upscale / Print Preparation
  ↓
Delivery
```

## Main Components

### 1. Client Experience Layer

Supports the ChatGPT prototype first and a dedicated web/mobile client later.

Responsibilities:

- Photo upload
- One-question-at-a-time guided selections
- Visual style cards
- Preview comparison
- Final artwork delivery
- Progress and quality status

The client never constructs model-specific prompts. It sends structured selections only.

Example request:

```json
{
  "subject_scope": "all_people",
  "composition": "full_body",
  "background_mode": "surprise_me",
  "style_id": "premium_chibi_v1",
  "identity_priority": "maximum",
  "output_purpose": "canvas_print"
}
```

### 2. API Gateway

Responsibilities:

- Authentication
- Request validation
- Upload authorization
- Rate limiting
- Job creation
- Status polling or streaming
- Delivery URL issuance

The gateway must not contain model-selection logic.

### 3. Portrait Job Service

Every portrait request becomes a durable job.

Example state model:

```text
CREATED
UPLOADED
ANALYZING
ENHANCING
IDENTITY_PROFILE_READY
WAITING_FOR_USER_SELECTIONS
PLANNING
GENERATING_PREVIEWS
VALIDATING_PREVIEWS
WAITING_FOR_PREVIEW_SELECTION
RENDERING_FINAL
FINAL_VALIDATION
DELIVERED
FAILED
CANCELLED
```

Each state transition must be recorded with timestamp, attempt number, and failure reason when applicable.

### 4. Portrait Intelligence Engine

The Portrait Intelligence Engine acts as the creative director.

Responsibilities:

- Interpret the uploaded photo
- Decide which questions are necessary
- Build an internal portrait plan
- Estimate style compatibility
- Select preview count
- Define preservation priorities
- Request routing from the Model Router

Internal output example:

```json
{
  "subjects": 2,
  "identity_priority": "critical",
  "enhancement_required": true,
  "pose_preservation": "strict",
  "clothing_preservation": "strict",
  "recommended_styles": [
    "soft_lifestyle_illustration_v1",
    "premium_chibi_v1",
    "storybook_gouache_v1"
  ],
  "preview_count": 4
}
```

### 5. Photo Analysis Service

Responsibilities:

- Detect number of faces
- Estimate face size and visibility
- Detect blur, noise, exposure, and resolution
- Detect pose and framing
- Detect occlusions
- Detect clothing, hairstyle, glasses, and accessories
- Produce an image-quality report

This service does not alter the source image.

### 6. Enhancement Service

Runs only when quality thresholds require it.

Responsibilities:

- Denoise
- Correct exposure and white balance
- Restore moderate blur
- Upscale face regions
- Improve local facial clarity

Rules:

- Enhancement must not alter perceived identity.
- The original source is always retained separately during the active job.
- Both original and enhanced images may be supplied to later validators.

### 7. IdentityLock Service

Responsibilities:

- Build a structured identity profile
- Mark critical attributes
- Create face-reference data for compatible models
- Define hard constraints and soft preferences
- Compare generated faces against the source

Example profile:

```json
{
  "critical_features": [
    "hair_silhouette",
    "glasses",
    "smile_shape",
    "face_shape"
  ],
  "preserve": {
    "expression": true,
    "clothing": true,
    "pose": true,
    "accessories": true
  }
}
```

Identity validation must combine multiple signals where possible. A single similarity number is not sufficient.

### 8. StyleDNA Service

Responsibilities:

- Resolve a selected style version
- Apply transformation limits
- Define line, color, texture, proportion, and background rules
- Specify which identity features may be simplified and which may not
- Provide model-specific rendering instructions through adapters

Style definitions are versioned and immutable once used in a delivered portrait recipe.

### 9. Model Router

The Model Router selects the best available provider and model for each task.

Routing inputs:

- Task type
- Style ID
- Subject count
- Identity priority
- Source quality
- Current provider availability
- Benchmark score
- Latency target
- Cost ceiling

Routing output:

```json
{
  "enhancer": "provider_a/model_x",
  "preview_generator": "provider_b/model_y",
  "final_generator": "provider_c/model_z",
  "validator": "provider_d/model_q",
  "upscaler": "provider_e/model_u"
}
```

Fallback routes must be defined for every production task.

### 10. Provider Adapters

Every external model is accessed through a provider adapter.

Each adapter must expose a common internal contract:

- `analyze()`
- `enhance()`
- `generate_preview()`
- `generate_final()`
- `validate()`
- `upscale()`

Provider-specific prompts, parameters, authentication, response parsing, and error handling remain inside the adapter.

### 11. AI Critic and Quality Gate

The AI Critic reviews each generated candidate.

Required gates:

- Identity
- Critical-feature preservation
- Subject count
- Pose consistency
- Clothing and accessory consistency
- Style accuracy
- Anatomy and artifact quality
- Background compliance
- Resolution
- Output suitability

Critical failures cause automatic rejection regardless of the average score.

Example:

```json
{
  "identity": "pass",
  "glasses": "pass",
  "hair": "pass",
  "pose": "pass",
  "style": "pass",
  "artifacts": "fail",
  "decision": "reject"
}
```

### 12. Retry Controller

Responsibilities:

- Retry failed generations
- Modify generation strategy based on failure reason
- Switch model when repeated failures occur
- Stop after a configured attempt budget
- Escalate to a graceful user message or optional manual review

A retry must not simply repeat the same request unchanged.

### 13. Preview Service

Responsibilities:

- Store validated preview candidates
- Present 2–4 curated options
- Record the selected concept
- Preserve the selected concept's generation recipe for final rendering

Only previews that pass minimum identity and quality gates are shown.

### 14. Final Render and Finisher

Responsibilities:

- Re-render the selected concept at target quality
- Apply final identity validation
- Upscale where required
- Convert color profile and dimensions for intended output
- Produce web, print, transparent, or product-specific derivatives

### 15. Portrait Recipe

Every delivered portrait stores a reproducible recipe containing configuration and version references, not hidden provider assumptions.

Example:

```json
{
  "style_id": "premium_chibi_v1",
  "identity_profile_version": "1.0",
  "generator_adapter": "provider_b",
  "generator_model": "model_y",
  "quality_policy": "canvas_v1",
  "selected_seed_or_reference": "internal-reference",
  "output": {
    "purpose": "canvas_print",
    "aspect_ratio": "4:5"
  }
}
```

Sensitive biometric data must not be retained in a recipe unless the user has explicitly consented and retention is legally justified.

## Data Stores

### Relational Database

Stores:

- Users
- Portrait jobs
- Workflow states
- Structured selections
- Style versions
- Model registry
- Routing decisions
- Quality-gate outcomes
- Portrait recipes

### Object Storage

Stores temporarily or permanently according to policy:

- Source uploads
- Enhanced working images
- Preview images
- Final images
- Print derivatives

### Cache

Used for:

- Job status
- Model availability
- Style metadata
- Temporary signed delivery links

### Queue

Used for long-running tasks:

- Enhancement
- Preview generation
- Validation
- Final render
- Upscaling

## Privacy and Retention Boundaries

Default policy should minimize retention:

- Source photos: short-lived unless the user saves the project
- Intermediate generations: automatically deleted after a defined period
- Face embeddings or identity representations: memory-only or short-lived by default
- Final artwork: retained only according to user account and deletion settings
- Logs: must not contain raw images or sensitive biometric vectors

Users must be able to delete source photos, outputs, saved preferences, and project history.

## Failure Handling

The system must distinguish:

- Invalid upload
- Unusable face quality
- Provider outage
- Generation failure
- Identity validation failure
- Quality validation failure
- User cancellation
- Delivery failure

User-facing language must remain simple. Internal logs should preserve technical detail.

Example user message:

> We could not preserve the faces reliably enough with this photo. Please upload a clearer image or choose a less stylized portrait option.

## Observability

Every job should expose internal metrics:

- Time per stage
- Provider and model used
- Retry count
- Failure reason
- Identity gate result
- Style gate result
- User preview selection
- Total cost
- Final delivery status

Metrics must avoid unnecessary personal data.

## MVP Boundary

The first production MVP should include:

- One client interface
- Single and two-person portraits
- 5–8 certified styles
- One enhancement path
- At least two image-generation providers
- One identity-validation path
- Automatic retries
- Two validated previews
- One final high-resolution output
- Temporary file retention and user deletion

The MVP should not initially include payments, physical-product ordering, public galleries, social features, or unlimited style uploads.

## Acceptance Criteria

Chapter 9 is considered implemented when:

- A portrait job can progress through durable states.
- Providers can be swapped through adapters.
- Routing is configuration-driven.
- Failed identity validation triggers a meaningful retry.
- Only validated previews reach the user.
- The selected preview can be reproduced as a final render.
- User photos and identity data follow explicit retention rules.
- The full job can be observed and debugged without inspecting raw user photos.
