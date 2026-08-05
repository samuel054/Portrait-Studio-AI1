from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.analyzer import ImageAnalysis, analyze_image
from app.identity import IdentityReport, analyze_identity


@dataclass(frozen=True)
class EnhancementReport:
    applied: bool
    operations: tuple[str, ...]
    before: ImageAnalysis
    after: ImageAnalysis
    identity_before: IdentityReport
    identity_after: IdentityReport
    face_count_preserved: bool
    output_width: int
    output_height: int

    def to_dict(self) -> dict[str, object]:
        return {
            "applied": self.applied,
            "operations": list(self.operations),
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "identity_before": self.identity_before.to_dict(),
            "identity_after": self.identity_after.to_dict(),
            "face_count_preserved": self.face_count_preserved,
            "output_width": self.output_width,
            "output_height": self.output_height,
        }


def _decode_image(image_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded file is not a readable image.")
    return image


def _encode_png(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not ok:
        raise RuntimeError("The enhanced image could not be encoded.")
    return encoded.tobytes()


def _correct_lighting(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8))
    corrected = clahe.apply(lightness)
    return cv2.cvtColor(cv2.merge((corrected, a_channel, b_channel)), cv2.COLOR_LAB2BGR)


def _denoise(image: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(image, None, 3, 3, 7, 21)


def _sharpen(image: np.ndarray) -> np.ndarray:
    blurred = cv2.GaussianBlur(image, (0, 0), 1.0)
    return cv2.addWeighted(image, 1.25, blurred, -0.25, 0)


def _upscale_if_needed(image: np.ndarray, megapixels: float) -> tuple[np.ndarray, bool]:
    if megapixels >= 1.0:
        return image, False

    height, width = image.shape[:2]
    scale = min(2.0, (1_000_000 / max(width * height, 1)) ** 0.5)
    if scale <= 1.05:
        return image, False

    resized = cv2.resize(
        image,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_LANCZOS4,
    )
    return resized, True


def enhance_image(image_bytes: bytes) -> tuple[bytes, EnhancementReport]:
    """Apply conservative, identity-safe corrections without generative face reconstruction."""
    before = analyze_image(image_bytes)
    identity_before = analyze_identity(image_bytes)
    image = _decode_image(image_bytes)
    operations: list[str] = []

    if before.lighting != "good":
        image = _correct_lighting(image)
        operations.append("lighting_correction")

    if before.blur_level in {"high", "medium"}:
        image = _denoise(image)
        image = _sharpen(image)
        operations.extend(("gentle_denoise", "conservative_sharpen"))

    image, upscaled = _upscale_if_needed(image, before.megapixels)
    if upscaled:
        operations.append("non_generative_upscale")

    enhanced_bytes = _encode_png(image)
    after = analyze_image(enhanced_bytes)
    identity_after = analyze_identity(enhanced_bytes)
    height, width = image.shape[:2]

    report = EnhancementReport(
        applied=bool(operations),
        operations=tuple(operations),
        before=before,
        after=after,
        identity_before=identity_before,
        identity_after=identity_after,
        face_count_preserved=identity_before.face_count == identity_after.face_count,
        output_width=width,
        output_height=height,
    )
    return enhanced_bytes, report
