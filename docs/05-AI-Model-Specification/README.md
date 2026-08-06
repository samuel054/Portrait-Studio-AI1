# AI Model Specification

**Version:** 1.0  
**Status:** Draft  
**Owner:** AI Engineering

## Purpose

Define the AI pipeline, supported model roles, identity-preservation controls, evaluation framework and model adoption requirements.

## Principles

- Identity first
- Open-source first for MVP
- Model-agnostic adapters
- Human-in-the-loop selection
- Explainable evaluation
- Privacy by design

## AI pipeline

```text
Input photo
  → quality analysis
  → identity readiness
  → conservative enhancement
  → portrait planning / PromptDNA
  → model selection
  → generation
  → identity evaluation
  → candidate ranking
  → user selection
  → safe refinement
  → final export
```

## Model roles

| Task | Baseline |
|---|---|
| Face detection | OpenCV baseline; replaceable detector |
| Image analysis | OpenCV, Pillow and NumPy |
| Conservative enhancement | OpenCV and Pillow |
| Face embeddings | InsightFace / ArcFace |
| Generation runtime | ComfyUI |
| Image generation | Approved SDXL- or FLUX-compatible local checkpoint |
| Identity conditioning | Benchmark IP-Adapter, InstantID, PuLID or comparable open implementations |
| Candidate ranking | Portrait Studio identity-first scoring engine |

## Model adoption requirements

A model or checkpoint must not be enabled in the product until:

- Its license is documented and compatible with intended use.
- It runs through the generator adapter contract.
- GPU memory, latency and failure behavior are measured.
- It is evaluated against the approved golden dataset.
- Identity-preservation results meet the current release gate.
- Safety and prohibited-edit behavior are verified.

## PromptDNA

PromptDNA is the deterministic portrait-plan layer. It contains:

- Identity rules
- Style rules
- Crop and composition rules
- Pose and clothing preservation rules
- Background and lighting rules
- Negative identity rules
- Artifact-prevention rules

The plan must explicitly prohibit a different face, generic beauty reconstruction, removal of defining accessories and unintended changes to age, ethnicity or gender presentation.

## Identity-first score

Baseline weighting:

```text
final_score = 0.70 × likeness + 0.30 × structural_and_quality_score
```

The numeric score does not override hard rejection rules.

## Hard rejection rules

- No face detected
- Face-count mismatch
- Likeness below configured threshold
- Severe facial distortion
- Invalid anatomy or major artifact
- Corrupt image data
- Likely identity replacement

## Candidate decisions

- `pass`: safe to present
- `review`: may be shown only under an approved review policy
- `reject`: never shown in the normal user flow

## Benchmark dimensions

- Identity recognition by people familiar with the subject
- Automated embedding similarity
- False-accept rate
- False-reject rate
- Style compliance
- Structural and anatomical quality
- Generation latency
- GPU memory consumption
- Runtime failure rate
- User selection and acceptance rate

## Benchmark dataset requirements

The consented dataset should include varied:

- Ages and skin tones
- Hair textures and facial hair
- Glasses and accessories
- Lighting and camera quality
- Indoor and outdoor photos
- Selfies and professional portraits
- Poses and crop sizes

It must also contain negative cases such as blur, darkness, tiny faces, occlusion, profiles, no face and multiple faces.

## Privacy requirements

- Embeddings are transient and session-scoped.
- Embeddings must not be used for cross-person identification.
- Raw images and embeddings must not appear in logs.
- User images must not enter training or benchmark datasets without explicit consent.

## Performance targets

| Stage | Initial target |
|---|---|
| Analysis | Under 2 seconds on reference CPU hardware |
| Enhancement | Under 3 seconds for normal MVP inputs |
| Evaluation and ranking | Under 7 seconds total |
| Generation | Under 60 seconds on approved reference GPU where feasible |
| Complete workflow | Under 90 seconds under normal load |

## Acceptance criteria

- Generator and embedding implementations are replaceable.
- PromptDNA is deterministic and versioned.
- Every candidate is evaluated before presentation.
- Hard identity gates are enforced.
- Model and checkpoint licenses are recorded.
- Benchmark results are documented before release.
