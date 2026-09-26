# Privacy and current limits

## Processing lifecycle

Uploads are limited to 20 MB and 40 million decoded pixels by default. The API validates image headers before allocating pixels, decodes still JPG/PNG/WebP images, corrects EXIF orientation, and strips metadata before generation. This MVP accepts one visible person per photo.

The application keeps source and candidate image bytes in local SQLite databases during a session. Face embeddings are computed transiently and never written to feedback or an identity database. Source anchors are retained only to compare refinements with the original photo, preventing gradual identity drift across edits.

App sessions expire 60 minutes after creation by default. Reads reject expired entries even without the background worker. The worker removes expired rows; SQLite secure-delete is enabled for image-bearing databases. This is logical deletion, not a guarantee of erasure from device backups, filesystem snapshots, or SSD media. Feedback contains ratings, reasons, comments, and identifiers, never image payloads or embeddings.

## ComfyUI files are separate

ComfyUI stores its own input uploads and saved output images in its local input/output folders. The app's SQLite expiry does not remove those files. Keep this runtime private. Delete those inputs/outputs using your local ComfyUI file-management process when you no longer need them, and apply the same policy to backups. Model weights may remain installed because they contain no session portraits.

## Quality and release limits

- Automated checks reject face-count failures, unreadable outputs, invalid embeddings, and insufficient similarity. Human review of face, pose, hands, and clothing is still needed; the structural checker is not a complete anatomical-artifact detector.
- Only `pass` candidates are shown; `review` and `reject` outputs are excluded.
- Every refinement is checked against the original source, not just the last generated face.
- The default workflow is SDXL image-to-image with configurable strength. It has no dedicated identity-conditioning network, and heavy stylization may produce no passing candidates.
- Prompt guidance alone does not guarantee unchanged accessories, clothing, background, or proportions. Deterministic face/upper-body cropping and optional segmentation cover only the explicit operations described in setup.
- Test doubles validate orchestration and UI behavior. They do not establish image quality, recognition accuracy, throughput, or GPU memory requirements.
- This is a local, single-user, single-API-process MVP. Public multi-user deployment still requires user authentication, per-user access controls, a durable worker queue, and deployment-specific operational work.
