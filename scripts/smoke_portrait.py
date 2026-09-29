"""Real upload-to-export smoke test; requires running API, ComfyUI, and local models."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import time

import httpx
from PIL import Image
from io import BytesIO


def checked(response):
    if response.is_error:
        raise RuntimeError(
            f"HTTP {response.status_code}: {response.json().get('detail', 'request failed')}"
        )
    return response.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photo", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path("artifacts/smoke"))
    parser.add_argument("--style-id", default="soft_lifestyle_illustration")
    parser.add_argument("--timeout", type=float, default=1200)
    parser.add_argument("--no-refine", action="store_true")
    args = parser.parse_args()
    if not args.photo.is_file():
        raise SystemExit("Portrait file not found.")
    args.output.mkdir(parents=True, exist_ok=True)
    headers = (
        {"x-api-key": os.environ["PORTRAIT_API_KEY"]} if os.environ.get("PORTRAIT_API_KEY") else {}
    )
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=180) as client:
        runtime = checked(client.get("/v1/runtime"))
        if not runtime["ready"]:
            raise SystemExit("Models are not ready: " + json.dumps(runtime["checks"]))
        with args.photo.open("rb") as source:
            job = checked(
                client.post(
                    "/v1/portrait-jobs",
                    files={
                        "file": (
                            args.photo.name,
                            source,
                            mimetypes.guess_type(args.photo.name)[0] or "image/jpeg",
                        )
                    },
                    data={"style_id": args.style_id, "candidate_count": 2},
                )
            )["job"]

        def wait_for_candidates(job):
            deadline = time.monotonic() + args.timeout
            last_stage = None
            while time.monotonic() < deadline:
                job = checked(client.get(f"/v1/portrait-jobs/{job['id']}"))["job"]
                if job["stage"] != last_stage:
                    print(job["stage"], flush=True)
                    last_stage = job["stage"]
                if job["status"] == "failed":
                    raise RuntimeError(job.get("error", {}).get("message", "Generation failed"))
                if job.get("candidate_session_id"):
                    return checked(
                        client.get(f"/v1/candidate-sessions/{job['candidate_session_id']}")
                    )["session"]
                time.sleep(2)
            raise RuntimeError("Timed out waiting for candidates.")

        def export(session, prefix):
            if not session["candidates"]:
                raise RuntimeError("No portrait passed the likeness checks.")
            choice = next(
                (item for item in session["candidates"] if item["recommended"]),
                session["candidates"][0],
            )
            checked(
                client.post(
                    f"/v1/candidate-sessions/{session['id']}/selection",
                    json={"candidate_id": choice["id"]},
                )
            )
            for fmt in ["png", "jpeg", "webp"]:
                result = checked(
                    client.post(
                        f"/v1/candidate-sessions/{session['id']}/render",
                        json={"output_format": fmt},
                    )
                )["render"]
                image_bytes = base64.b64decode(result["image_base64"], validate=True)
                with Image.open(BytesIO(image_bytes)) as image:
                    if image.format.lower() != fmt:
                        raise RuntimeError(f"Expected {fmt}, received {image.format}.")
                    image.verify()
                (args.output / f"{prefix}.{fmt}").write_bytes(image_bytes)
            return session

        session = export(wait_for_candidates(job), "portrait")
        if not args.no_refine:
            refined = checked(
                client.post(
                    f"/v1/candidate-sessions/{session['id']}/refine",
                    json={
                        "style_id": args.style_id,
                        "operation": "lighting",
                        "instruction": "Gently soften lighting without changing the face.",
                        "candidate_count": 2,
                    },
                )
            )["job"]
            export(wait_for_candidates(refined), "refined")
            final = checked(client.get(f"/v1/portrait-jobs/{refined['id']}"))["job"]
            if final["status"] != "completed":
                raise RuntimeError("Refined workflow did not finish after export.")
        final = checked(client.get(f"/v1/portrait-jobs/{job['id']}"))["job"]
        if final["status"] != "completed":
            raise RuntimeError("Workflow did not finish after export.")
        print(f"Real workflow completed. Inspect the portraits in {args.output}.")


if __name__ == "__main__":
    main()
