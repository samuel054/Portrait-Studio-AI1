from __future__ import annotations

from dataclasses import asdict, dataclass

from app.evaluator import CandidateEvaluation, rank_candidates
from app.likeness import FaceEmbeddingAdapter, LikenessResult, compare_likeness


@dataclass(frozen=True)
class IdentityFirstEvaluation:
    index: int
    rank: int
    final_score: float
    status: str
    structural_score: float
    likeness_score: float
    cosine_similarity: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


@dataclass(frozen=True)
class IdentityFirstRanking:
    evaluations: tuple[IdentityFirstEvaluation, ...]
    recommended_index: int | None
    method: str
    likeness_threshold: float

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluations": [item.to_dict() for item in self.evaluations],
            "recommended_index": self.recommended_index,
            "method": self.method,
            "likeness_threshold": self.likeness_threshold,
        }


def _combine(
    structural: CandidateEvaluation,
    likeness: LikenessResult,
) -> tuple[float, str, tuple[str, ...]]:
    reasons = list(structural.reasons)
    reasons.append(
        f"Face likeness score is {likeness.likeness_score:.2f}/100 "
        f"using {likeness.adapter_id}."
    )

    # Identity is the dominant signal. A visually attractive but different person must not pass.
    final_score = round((likeness.likeness_score * 0.70) + (structural.score * 0.30), 2)

    if structural.status == "reject":
        reasons.append("Rejected because structural face checks failed.")
        return min(final_score, 49.0), "reject", tuple(reasons)
    if likeness.decision == "reject":
        reasons.append("Rejected because the generated face does not sufficiently match the source.")
        return min(final_score, 49.0), "reject", tuple(reasons)
    if likeness.decision == "review" or structural.status == "review" or final_score < 75.0:
        reasons.append("Manual review is recommended before presenting this candidate.")
        return final_score, "review", tuple(reasons)

    reasons.append("Candidate passed identity, structure, and quality checks.")
    return final_score, "pass", tuple(reasons)


def rank_identity_first_candidates(
    original_bytes: bytes,
    candidate_bytes: list[bytes],
    adapter: FaceEmbeddingAdapter,
    likeness_threshold: float = 0.35,
) -> IdentityFirstRanking:
    """Rank generated portraits with likeness as the primary quality gate."""
    structural_ranking = rank_candidates(original_bytes, candidate_bytes)
    combined: list[dict[str, object]] = []

    for structural, image_bytes in zip(
        structural_ranking.evaluations,
        candidate_bytes,
        strict=True,
    ):
        likeness = compare_likeness(
            original_bytes,
            image_bytes,
            adapter=adapter,
            threshold=likeness_threshold,
        )
        final_score, status, reasons = _combine(structural, likeness)
        combined.append(
            {
                "index": structural.index,
                "final_score": final_score,
                "status": status,
                "structural_score": structural.score,
                "likeness_score": likeness.likeness_score,
                "cosine_similarity": likeness.cosine_similarity,
                "reasons": reasons,
            }
        )

    ordered = sorted(
        combined,
        key=lambda item: (-float(item["final_score"]), int(item["index"])),
    )
    ranks = {int(item["index"]): rank for rank, item in enumerate(ordered, start=1)}
    evaluations = tuple(
        IdentityFirstEvaluation(rank=ranks[int(item["index"])], **item)
        for item in combined
    )
    eligible = [item for item in ordered if item["status"] != "reject"]
    recommended_index = int(eligible[0]["index"]) if eligible else None

    return IdentityFirstRanking(
        evaluations=evaluations,
        recommended_index=recommended_index,
        method="identity_first_v1_70_likeness_30_structural",
        likeness_threshold=likeness_threshold,
    )
