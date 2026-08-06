# UI/UX Specification

**Version:** 1.0  
**Status:** Draft  
**Owner:** Product Design

## Design principles

- Identity first
- Minimal learning curve
- Explain AI decisions
- Human control
- Mobile first
- Accessible by default

## Information architecture

```text
Landing
├── Upload
├── Analysis
├── Style Gallery
├── Generation Progress
├── Candidate Selection
├── Refinement
└── Export
```

## Primary user flow

```text
Upload → Analyze → Enhance if needed → Select style → Generate → Rank → Select A/B/C/D → Refine optionally → Export
```

## MVP screens

| ID | Screen | Purpose |
|---|---|---|
| UX-001 | Landing | Explain the product promise and start upload |
| UX-002 | Upload | Drag/drop, file picker, preview and validation |
| UX-003 | Analysis | Show face count, quality, readiness and recommendation |
| UX-004 | Style Gallery | Browse and select supported visual styles |
| UX-005 | Progress | Show real backend stages and failure states |
| UX-006 | Candidate Selection | Present safe candidates A-D and recommended result |
| UX-007 | Refinement | Offer identity-safe edit controls |
| UX-008 | Export | Choose format, size and download |

## Core components

- Upload zone
- Image preview
- Analysis summary
- Style card
- Progress timeline
- Candidate card
- Recommended badge
- Refinement controls
- Export panel
- Error alert
- Toast notification

## Candidate selection requirements

- Only candidates that pass identity gates may be shown.
- Candidate IDs must remain stable within a session.
- The recommended result must be clearly labeled.
- The user must explicitly select a candidate before rendering.
- Identity and quality explanations should be available without overwhelming the main screen.

## Refinement controls

Allowed:

- Background
- Lighting
- Color treatment
- Clothing detail preservation
- Artifact cleanup

Blocked:

- Face replacement
- Identity change
- Age transformation
- Ethnicity transformation
- Gender-presentation transformation
- Hairstyle replacement

## Responsive behavior

- Mobile: single-column workflow and full-width cards
- Tablet: two-column candidate grid
- Desktop: two- or four-column candidate grid with persistent workflow summary

## Accessibility

- Target WCAG 2.2 AA
- Keyboard navigation
- Visible focus states
- Screen-reader labels
- Sufficient color contrast
- Alt text for meaningful images
- Error messages linked to the relevant input

## Loading and error states

Stages:

- Uploading
- Analyzing
- Enhancing
- Generating
- Evaluating
- Ranking
- Rendering

Errors:

- Invalid file
- File too large
- No face detected
- Multiple faces not supported
- Network failure
- Generation failure
- No safe candidates
- Export failure

## Acceptance criteria

- All MVP screens are implemented.
- The complete workflow is usable on mobile and desktop.
- Progress reflects actual backend state.
- Identity-first safeguards are visible and understandable.
- A user can complete the workflow without external guidance.
