from __future__ import annotations

from dataclasses import asdict, dataclass

from app.analyzer import analyze_image
from app.identity import analyze_identity


@dataclass(frozen=True)
class CandidateEvaluation:
    index: int
    score: float
    rank: int
    status: str
    face_count_preserved: bool
    face_scale_similarity: float
    quality_score: float
    identity_readiness: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


@dataclass(frozen=True)
class CandidateRanking:
    evaluations: tuple[CandidateEvaluation, ...]
    recommended_index: int | None
    method: str

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluations": [item.to_dict() for item in self.evaluations],
            "recommended_index": self.recommended_index,
            "method": self.method,
        }


def _quality_score(image_bytes: bytes) -> float:
    report = analyze_image(image_bytes)
    blur_points = {"low": 100.0, "medium": 65.0, "high": 25.0}[report.blur_level]
    lighting_points = {"good": 100.0, "dark": 55.0, "bright": 55.0}[report.lighting]
    resolution_points = min(100.0, max(20.0, report.megapixels * 35.0))
    return round((blur_points * 0.45) + (lighting_points * 0.30) + (resolution_points * 0.25), 2)


def rank_candidates(original_bytes: bytes, candidate_bytes: list[bytes]) -> CandidateRanking:
    """Rank candidates with conservative, explainable checks.

    This is not a biometric identity matcher. It rejects obvious structural regressions and
    prioritizes candidates with preserved face count, similar face scale, and usable quality.
    """
    if not candidate_bytes:
        raise ValueError("At least one candidate image is required.")
    if len(candidate_bytes) > 4:
        raise ValueError("A maximum of four candidate images can be ranked at once.")

    original_identity = analyze_identity(original_bytes)
    if original_identity.face_count == 0:
        raise ValueError("The original image must contain a clearly detectable face.")

    preliminary: list[dict[str, object]] = []
    original_ratio = max(original_identity.largest_face_ratio, 0.0001)

    for index, image_bytes in enumerate(candidate_bytes):
        identity = analyze_identity(image_bytes)
        quality = _quality_score(image_bytes)
        face_count_preserved = identity.face_count == original_identity.face_count
        ratio_delta = abs(identity.largest_face_ratio - original_ratio) / original_ratio
        face_scale_similarity = round(max(0.0, 100.0 - min(100.0, ratio_delta * 100.0)), 2)

        reasons: list[str] = []
        score = quality * 0.30 + face_scale_similarity * 0.30
        if face_count_preserved:
            score += 30.0
            reasons.append("Face count matches the source image.")
        else:
            reasons.append("Face count differs from the source image.")
        if identity.identity_readiness == "ready":
            score += 10.0
            reasons.append("Detected face is generation-ready.")
        else:
            reasons.append(f"Identity readiness is {identity.identity_readiness}.")
        if face_scale_similarity >= 75:
            reasons.append("Face scale is close to the source composition.")
        if quality >= 70:
            reasons.append("Image clarity and lighting are suitable for preview.")

        status = "pass"
        if not face_count_preserved or identity.face_count == 0:
            status = "reject"
            score = min(score, 49.0)
        elif score < 65:
            status = "review"

        preliminary.append(
            {
                "index": index,
                "score": round(min(100.0, max(0.0, score)), 2),
                "status": status,
                "face_count_preserved": face_count_preserved,
                "face_scale_similarity": face_scale_similarity,
                "quality_score": quality,
                "identity_readiness": identity.identity_readiness,
                "reasons": tuple(reasons),
            }
        )

    ordered = sorted(preliminary, key=lambda item: (-float(item["score"]), int(item["index"])))
    ranks = {int(item["index"]): rank for rank, item in enumerate(ordered, start=1)}
    evaluations = tuple(
        CandidateEvaluation(rank=ranks[int(item["index"])], **item) for item in preliminary
    )
    passing = [item for item in ordered if item["status"] != "reject"]
    recommended_index = int(passing[0]["index"]) if passing else None

    return CandidateRanking(
        evaluations=evaluations,
        recommended_index=recommended_index,
        method="explainable_structural_quality_v1_non_biometric",
    )
