"""Install pinned OpenCV Zoo models with SHA-256 verification. No portrait is uploaded."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import urllib.request

REVISION = "47534e27c9851bb1128ccc0102f1145e27f23f98"
MODELS = (
    (
        "face_detection_yunet",
        "face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    (
        "face_recognition_sface",
        "face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
)


def install(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for folder, filename, expected in MODELS:
        target = destination / filename
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            print(f"Verified {filename}")
        else:
            print(f"Downloading {filename}", flush=True)
            url = f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{REVISION}/models/{folder}/{filename}"
            temporary = target.with_suffix(".download")
            try:
                with (
                    urllib.request.urlopen(url, timeout=60) as source,
                    temporary.open("wb") as output,
                ):
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
                    raise RuntimeError(f"Model checksum mismatch: {filename}")
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        license_url = f"https://raw.githubusercontent.com/opencv/opencv_zoo/{REVISION}/models/{folder}/LICENSE"
        with urllib.request.urlopen(license_url, timeout=30) as source:
            (destination / f"{folder}-LICENSE.txt").write_bytes(source.read())
    print(f"Likeness models ready in {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("models/identity"))
    args = parser.parse_args()
    install(args.directory)
