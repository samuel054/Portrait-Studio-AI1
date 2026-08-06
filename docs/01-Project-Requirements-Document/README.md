# Project Requirements Document (PRD)

**Version:** 1.0  
**Status:** Approved baseline  
**Owner:** Product Team

## 1. Executive Summary

Portrait Studio AI is an identity-first portrait generation platform. The MVP enables a user to upload one photograph of one person, receive quality and identity-readiness guidance, choose a visual style, generate multiple candidates, view only candidates that pass identity-safety checks, select a preferred result, optionally refine it, and export the final portrait.

## 2. Business Objective

Build a trusted portrait product that users prefer because generated results remain recognizably faithful to the uploaded person.

Secondary objectives:

- Create reusable AI infrastructure.
- Use open-source and free-to-run components for the initial product.
- Minimize vendor lock-in and operating cost.
- Establish measurable identity quality standards.
- Prepare the foundation for future API and professional offerings.

## 3. Product Goals

### Primary

- Preserve recognizable facial identity.
- Prevent different-looking people from reaching the user.
- Provide visually appealing artistic results.
- Explain when an input or result is unsuitable.
- Keep the user in control of the final choice.

### Secondary

- Support multiple curated styles.
- Allow safe iterative refinement.
- Maintain a modular, model-agnostic architecture.
- Collect privacy-safe feedback for quality improvement.

## 4. Target Users

- Professionals and students seeking polished portraits.
- Creators seeking stylized social-media images.
- Individuals and families creating gifts or keepsakes.
- Photographers and small studios seeking repeatable AI portrait workflows.

## 5. MVP User Journey

```text
Upload photo
  -> Analyze quality and face readiness
  -> Enhance conservatively when required
  -> Choose style
  -> Generate 2-4 candidates
  -> Evaluate likeness and structure
  -> Hide rejected candidates
  -> Select A/B/C/D
  -> Refine safely if needed
  -> Export PNG/JPEG/WebP
```

## 6. MVP Scope

### Included

- JPG, PNG, and WebP upload
- File validation and preview
- Blur, lighting, dimensions, and megapixel analysis
- Face detection and identity-readiness guidance
- Conservative non-generative enhancement
- Curated style catalog
- Prompt and portrait-plan construction
- Local ComfyUI generation
- Two to four candidates
- Automated likeness, structural, and quality evaluation
- Identity-first filtering and ranking
- User candidate selection
- Safe refinement
- PNG, JPEG, and WebP export
- Structured feedback
- Responsive web interface

### Excluded

- Multi-person portrait generation
- Native mobile applications
- Video generation
- Payments and subscriptions
- Public style marketplace
- Enterprise administration
- Persistent biometric identity profiles

## 7. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Accept JPG, PNG, and WebP files up to the configured limit. | Must |
| FR-002 | Reject empty, unsupported, corrupt, and oversized uploads. | Must |
| FR-003 | Analyze dimensions, blur, lighting, and enhancement need. | Must |
| FR-004 | Detect face count and prominent face region. | Must |
| FR-005 | Classify identity readiness and provide actionable guidance. | Must |
| FR-006 | Apply conservative enhancement without generative face reconstruction. | Must |
| FR-007 | Verify face-count preservation after enhancement. | Must |
| FR-008 | Present a curated style gallery with compatible options. | Must |
| FR-009 | Build deterministic identity, style, and negative prompt rules. | Must |
| FR-010 | Submit reference image and portrait plan through a pluggable generator. | Must |
| FR-011 | Generate two to four candidates for the standard workflow. | Must |
| FR-012 | Expose queued, running, completed, and failed job states. | Must |
| FR-013 | Evaluate likeness, structure, and technical quality. | Must |
| FR-014 | Hide candidates that fail identity or structural gates. | Must |
| FR-015 | Allow explicit A/B/C/D selection. | Must |
| FR-016 | Permit only identity-safe refinement controls. | Should |
| FR-017 | Export PNG, JPEG, and WebP while preserving aspect ratio. | Must |
| FR-018 | Store ratings, acceptance, structured reasons, and optional comments. | Should |
| FR-019 | Exclude portrait pixels and embeddings from feedback records. | Must |
| FR-020 | Provide responsive upload-to-download frontend screens. | Must |

## 8. Non-Functional Requirements

- Privacy-first processing and documented retention.
- Clear timeout and retry behavior for AI-runtime calls.
- Structured logs without portrait data or embeddings.
- Accessible web experience targeting WCAG 2.2 AA.
- Backend unit/API tests and frontend production-build checks in CI.
- Model adapters and workflows must be replaceable and versioned.
- MVP must run without mandatory paid APIs.

## 9. Success Metrics

| Metric | Initial Target |
|---|---|
| Human identity recognition rate | At least 90% on curated beta evaluation |
| Automated identity pass rate | At least 60% of generated candidates before display |
| Generation infrastructure completion rate | At least 95% |
| End-to-end task completion in usability tests | At least 80% |
| Analysis P95 latency excluding upload transfer | Under 2 seconds on reference CPU |
| First candidate-set acceptance | At least 50% during beta |

## 10. Business Rules

1. Identity safety overrides aesthetic score.
2. A visually attractive candidate that fails likeness must be rejected.
3. The user must select the final candidate.
4. Refinement must not permit face, age, ethnicity, or gender replacement.
5. Low-confidence inputs must trigger guidance rather than uncontrolled generation.
6. Model or checkpoint adoption requires license review and benchmark approval.

## 11. Key Risks

- Identity drift during generation
- Weak results from small, blurry, or occluded faces
- GPU availability and queue delays
- Model/checkpoint licensing changes
- User expectations exceeding current model capability
- Privacy or retention failures

## 12. Release Stages

### Alpha

Engineering validation with consented internal images.

### Private Beta

Invited users, structured feedback, calibrated likeness thresholds.

### Public Beta

Broader use with monitoring, rate limits, retention controls, and support processes.

### Version 1.0

Stable workflow, production persistence, authentication, observability, and documented quality targets.

## 13. MVP Acceptance Criteria

- Supported images can be uploaded from desktop and mobile.
- The system returns quality and identity-readiness guidance.
- Enhancement runs only when needed and preserves face count.
- A user can choose a style and start a local generation job.
- Every candidate is evaluated before display.
- Identity-failed candidates are not shown.
- A user can select a candidate and export it.
- Safe refinement does not intentionally regenerate the face.
- Backend CI and frontend CI pass from a clean checkout.
- The end-to-end system can run without a paid model API.

## 14. Requirements Traceability

Each approved business requirement must map to:

- One or more functional requirements
- A technical component
- An API or user-interface behavior
- Automated or human test cases
- A release status
