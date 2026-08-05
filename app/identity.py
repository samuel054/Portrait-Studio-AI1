from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache

import cv2
import numpy as np


@dataclass(frozen=True)
class FaceRegion:
    x: int
    y: int
    width: int
    height: int
    area_ratio: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True)
class IdentityReport:
    face_count: int
    faces: tuple[FaceRegion, ...]
    largest_face_ratio: float
    identity_readiness: str
    identity_risk: str
    guidance: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "face_count": self.face_count,
            "faces": [face.to_dict() for face in self.faces],
            "largest_face_ratio": self.largest_face_ratio,
            "identity_readiness": self.identity_readiness,
            "identity_risk": self.identity_risk,
            "guidance": list(self.guidance),
        }


@lru_cache(maxsize=1)
def _face_detector() -> cv2.CascadeClassifier:
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        raise RuntimeError("OpenCV face detector could not be loaded.")
    return detector


def _decode_image(image_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded file is not a readable image.")
    return image


def _classify_readiness(face_count: int, largest_face_ratio: float) -> tuple[str, str, tuple[str, ...]]:
    guidance: list[str] = []

    if face_count == 0:
        return (
            "not_ready",
            "high",
            (
                "No clear frontal face was detected.",
                "Use a photo with the face visible, well lit, and facing the camera.",
            ),
        )

    if largest_face_ratio < 0.02:
        guidance.append("The largest face is too small for reliable identity preservation.")
        guidance.append("Upload a closer crop or a higher-resolution photo.")
        return "needs_better_photo", "high", tuple(guidance)

    if face_count > 4:
        guidance.append("Many faces were detected; identity matching will be more difficult.")
        guidance.append("For best results, use a smaller group or provide separate reference photos.")
        return "review_required", "medium", tuple(guidance)

    if largest_face_ratio < 0.06:
        guidance.append("Identity can be analyzed, but a closer face crop may improve likeness.")
        return "usable", "medium", tuple(guidance)

    return "ready", "low", ("Face visibility is suitable for identity analysis.",)


def analyze_identity(image_bytes: bytes) -> IdentityReport:
    image = _decode_image(image_bytes)
    height, width = image.shape[:2]
    image_area = max(width * height, 1)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    detected = _face_detector().detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(40, 40),
    )

    faces = tuple(
        sorted(
            (
                FaceRegion(
                    x=int(x),
                    y=int(y),
                    width=int(face_width),
                    height=int(face_height),
                    area_ratio=round((face_width * face_height) / image_area, 4),
                )
                for x, y, face_width, face_height in detected
            ),
            key=lambda face: face.area_ratio,
            reverse=True,
        )
    )

    largest_face_ratio = faces[0].area_ratio if faces else 0.0
    readiness, risk, guidance = _classify_readiness(len(faces), largest_face_ratio)

    return IdentityReport(
        face_count=len(faces),
        faces=faces,
        largest_face_ratio=largest_face_ratio,
        identity_readiness=readiness,
        identity_risk=risk,
        guidance=guidance,
    )
