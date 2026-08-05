from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

import cv2
import numpy as np


class FaceEmbeddingAdapter(Protocol):
    id: str

    def embed(self, image_bytes: bytes) -> np.ndarray:
        """Return one normalized embedding for the most prominent detected face."""


@dataclass(frozen=True)
class LikenessResult:
    adapter_id: str
    cosine_similarity: float
    likeness_score: float
    decision: str
    threshold: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class InsightFaceAdapter:
    """Optional local InsightFace adapter.

    Install the optional identity dependencies before using this adapter. Model files are loaded
    by InsightFace locally; no image is sent to a remote service.
    """

    id = "insightface_arcface"

    def __init__(self, model_name: str = "buffalo_l") -> None:
        try:
            from insightface.app import FaceAnalysis
        except ImportError as exc:
            raise RuntimeError(
                "InsightFace is not installed. Install the optional 'identity' dependencies."
            ) from exc

        self._app = FaceAnalysis(name=model_name, providers=["CPUExecutionProvider"])
        self._app.prepare(ctx_id=-1, det_size=(640, 640))

    def embed(self, image_bytes: bytes) -> np.ndarray:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Unable to decode image for likeness evaluation.")

        faces = self._app.get(image)
        if not faces:
            raise ValueError("No clearly detectable face was found.")
        face = max(faces, key=lambda item: float(item.bbox[2] - item.bbox[0]) * float(item.bbox[3] - item.bbox[1]))
        embedding = np.asarray(face.normed_embedding, dtype=np.float32)
        if embedding.ndim != 1 or embedding.size == 0:
            raise RuntimeError("InsightFace returned an invalid embedding.")
        return _normalize(embedding)


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        raise ValueError("Face embedding has zero magnitude.")
    return vector.astype(np.float32) / norm


def compare_likeness(
    original_bytes: bytes,
    candidate_bytes: bytes,
    adapter: FaceEmbeddingAdapter,
    threshold: float = 0.35,
) -> LikenessResult:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1.")

    original = _normalize(np.asarray(adapter.embed(original_bytes), dtype=np.float32))
    candidate = _normalize(np.asarray(adapter.embed(candidate_bytes), dtype=np.float32))
    if original.shape != candidate.shape:
        raise ValueError("Face embeddings have incompatible dimensions.")

    cosine = float(np.clip(np.dot(original, candidate), -1.0, 1.0))
    likeness_score = round(max(0.0, min(100.0, (cosine + 1.0) * 50.0)), 2)
    decision = "pass" if cosine >= threshold else "reject"
    if decision == "pass" and cosine < threshold + 0.10:
        decision = "review"

    return LikenessResult(
        adapter_id=adapter.id,
        cosine_similarity=round(cosine, 4),
        likeness_score=likeness_score,
        decision=decision,
        threshold=threshold,
    )
