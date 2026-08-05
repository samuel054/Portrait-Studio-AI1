from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class ImageAnalysis:
    width: int
    height: int
    megapixels: float
    blur_score: float
    blur_level: str
    brightness: float
    lighting: str
    needs_enhancement: bool

    def to_dict(self) -> dict[str, int | float | str | bool]:
        return asdict(self)


def analyze_image(image_bytes: bytes) -> ImageAnalysis:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded file is not a readable image.")

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())

    if blur_score < 60:
        blur_level = "high"
    elif blur_score < 140:
        blur_level = "medium"
    else:
        blur_level = "low"

    if brightness < 70:
        lighting = "dark"
    elif brightness > 210:
        lighting = "overexposed"
    else:
        lighting = "good"

    megapixels = round((width * height) / 1_000_000, 2)
    needs_enhancement = blur_level != "low" or lighting != "good" or megapixels < 1.0

    return ImageAnalysis(
        width=width,
        height=height,
        megapixels=megapixels,
        blur_score=round(blur_score, 2),
        blur_level=blur_level,
        brightness=round(brightness, 2),
        lighting=lighting,
        needs_enhancement=needs_enhancement,
    )
