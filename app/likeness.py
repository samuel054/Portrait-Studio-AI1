from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol
from threading import RLock

import cv2
import numpy as np

from app.settings import get_settings


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

    def __init__(self, model_name: str | None = None) -> None:
        settings = get_settings()
        model_name = model_name or settings.insightface_model_name
        model_dir = settings.insightface_root / "models" / model_name
        if not model_dir.is_dir() or not list(model_dir.glob("*.onnx")):
            raise RuntimeError(
                "The local likeness model is not installed. Follow the model setup guide first."
            )
        try:
            from insightface.app import FaceAnalysis
        except ImportError as exc:
            raise RuntimeError(
                "InsightFace is not installed. Install the optional 'identity' dependencies."
            ) from exc

        self._app = FaceAnalysis(
            name=model_name, root=str(settings.insightface_root),
            allowed_modules=["detection", "recognition"], providers=["CPUExecutionProvider"],
        )
        self._app.prepare(ctx_id=-1, det_size=(640, 640))

    def embed(self, image_bytes: bytes) -> np.ndarray:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Unable to decode image for likeness evaluation.")

        faces = self._app.get(image)
        if len(faces) != 1:
            raise ValueError("Exactly one clearly visible face is needed for likeness checking.")
        face = faces[0]
        embedding = np.asarray(face.normed_embedding, dtype=np.float32)
        if embedding.ndim != 1 or embedding.size == 0:
            raise RuntimeError("InsightFace returned an invalid embedding.")
        return _normalize(embedding)


class OpenCVSFaceAdapter:
    """Local YuNet detection and SFace likeness; model files installed explicitly."""

    id = "opencv_sface"

    def __init__(self) -> None:
        root = get_settings().identity_model_dir
        detector = root / "face_detection_yunet_2023mar.onnx"
        recognizer = root / "face_recognition_sface_2021dec.onnx"
        if not detector.is_file() or not recognizer.is_file():
            raise RuntimeError("Install the local likeness models: python scripts/setup_identity_models.py")
        try:
            self._detector = cv2.FaceDetectorYN.create(str(detector), "", (320, 320), 0.85, 0.3, 5000)
            self._recognizer = cv2.FaceRecognizerSF.create(str(recognizer), "")
        except cv2.error as exc:
            raise RuntimeError("The local likeness model files could not be loaded. Run model setup again.") from exc
        self._lock = RLock()

    def embed(self, image_bytes: bytes) -> np.ndarray:
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Unable to decode image for likeness evaluation.")
        scale = min(1.0, 1024 / max(image.shape[:2]))
        if scale < 1:
            image = cv2.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)))
        with self._lock:
            self._detector.setInputSize((image.shape[1], image.shape[0]))
            _, faces = self._detector.detect(image)
            if faces is None or len(faces) != 1:
                raise ValueError("Exactly one clearly visible face is needed for likeness checking.")
            aligned = self._recognizer.alignCrop(image, faces[0])
            vector = self._recognizer.feature(aligned).flatten()
        return _normalize(vector)


def create_likeness_adapter() -> FaceEmbeddingAdapter:
    if get_settings().identity_adapter == "insightface":
        return InsightFaceAdapter()
    return OpenCVSFaceAdapter()


def _normalize(vector: np.ndarray) -> np.ndarray:
    if vector.ndim != 1 or not vector.size or not np.isfinite(vector).all():
        raise ValueError("Face embedding must contain a finite, nonempty vector.")
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
