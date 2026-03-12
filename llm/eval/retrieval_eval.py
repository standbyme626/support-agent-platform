from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.retriever import Retriever
from tools.search_kb import search_kb


@dataclass(frozen=True)
class RetrievalEvalSample:
    sample_id: str
    query: str
    source_type: str
    expected_doc_ids: tuple[str, ...]
    expected_source_types: tuple[str, ...]


def load_eval_set(path: Path) -> list[RetrievalEvalSample]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("retrieval eval set must be a list")
    items: list[RetrievalEvalSample] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        sample_id = str(row.get("id") or "").strip()
        query = str(row.get("query") or "").strip()
        source_type = str(row.get("source_type") or "grounded").strip().lower()
        if not sample_id or not query:
            continue
        expected_doc_ids = tuple(
            str(item).strip() for item in row.get("expected_doc_ids", []) if str(item).strip()
        )
        expected_source_types = tuple(
            str(item).strip() for item in row.get("expected_source_types", []) if str(item).strip()
        )
        items.append(
            RetrievalEvalSample(
                sample_id=sample_id,
                query=query,
                source_type=source_type,
                expected_doc_ids=expected_doc_ids,
                expected_source_types=expected_source_types,
            )
        )
    return items


def evaluate_retrieval(
    retriever: Retriever,
    samples: list[RetrievalEvalSample],
) -> dict[str, Any]:
    mode_results: dict[str, list[bool]] = {"lexical": [], "vector": [], "hybrid": []}
    grounding_coverage_hits = 0
    similar_cases_hits = 0
    gap_candidates: list[dict[str, Any]] = []

    for sample in samples:
        search_outputs: dict[str, list[dict[str, object]]] = {}
        for mode in ("lexical", "vector", "hybrid"):
            rows = search_kb(
                retriever=retriever,
                source_type=sample.source_type,
                query=sample.query,
                top_k=3,
                retrieval_mode=mode,
            )
            search_outputs[mode] = rows
            mode_results[mode].append(_is_hit(sample, rows))

        hybrid_rows = search_outputs["hybrid"]
        if _has_grounding(hybrid_rows):
            grounding_coverage_hits += 1
        if _has_similar_cases(hybrid_rows):
            similar_cases_hits += 1

        if not mode_results["hybrid"][-1]:
            gap_candidates.append(
                {
                    "id": sample.sample_id,
                    "query": sample.query,
                    "expected_doc_ids": list(sample.expected_doc_ids),
                    "expected_source_types": list(sample.expected_source_types),
                    "hybrid_top3": [
                        str(item.get("source_id") or item.get("doc_id") or "")
                        for item in hybrid_rows
                    ],
                }
            )

    total = max(1, len(samples))
    lexical_rate = _ratio(mode_results["lexical"])
    vector_rate = _ratio(mode_results["vector"])
    hybrid_rate = _ratio(mode_results["hybrid"])
    if lexical_rate <= 0:
        hybrid_lift = 100.0 if hybrid_rate > 0 else 0.0
    else:
        hybrid_lift = ((hybrid_rate - lexical_rate) / lexical_rate) * 100.0

    grounding_coverage = grounding_coverage_hits / total
    similar_cases_availability = similar_cases_hits / total
    metrics = {
        "sample_count": len(samples),
        "lexical_top3_hit_rate": round(lexical_rate, 4),
        "vector_top3_hit_rate": round(vector_rate, 4),
        "hybrid_top3_hit_rate": round(hybrid_rate, 4),
        "hybrid_top3_lift_vs_lexical_pct": round(hybrid_lift, 2),
        "grounding_coverage": round(grounding_coverage, 4),
        "similar_cases_availability": round(similar_cases_availability, 4),
        "stage_gate": {
            "hybrid_lift_ge_15pct": hybrid_lift >= 15.0,
            "grounding_coverage_ge_95pct": grounding_coverage >= 0.95,
            "similar_cases_availability_ge_90pct": similar_cases_availability >= 0.90,
        },
        "gaps": gap_candidates,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return metrics


def render_gap_report(metrics: dict[str, Any]) -> str:
    stage_gate = metrics["stage_gate"]
    lines = [
        "# Retrieval Gap Report",
        "",
        f"- generated_at: {metrics['generated_at']}",
        f"- sample_count: {metrics['sample_count']}",
        f"- lexical_top3_hit_rate: {metrics['lexical_top3_hit_rate']}",
        f"- vector_top3_hit_rate: {metrics['vector_top3_hit_rate']}",
        f"- hybrid_top3_hit_rate: {metrics['hybrid_top3_hit_rate']}",
        f"- hybrid_top3_lift_vs_lexical_pct: {metrics['hybrid_top3_lift_vs_lexical_pct']}",
        f"- grounding_coverage: {metrics['grounding_coverage']}",
        f"- similar_cases_availability: {metrics['similar_cases_availability']}",
        "",
        "## Stage Gate",
        f"- hybrid_lift_ge_15pct: {stage_gate['hybrid_lift_ge_15pct']}",
        f"- grounding_coverage_ge_95pct: {stage_gate['grounding_coverage_ge_95pct']}",
        (
            "- similar_cases_availability_ge_90pct: "
            f"{stage_gate['similar_cases_availability_ge_90pct']}"
        ),
        "",
        "## Gaps",
    ]
    gaps = metrics.get("gaps", [])
    if not isinstance(gaps, list) or not gaps:
        lines.append("- no critical miss in hybrid top3")
    else:
        for item in gaps:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- "
                + f"{item.get('id')}: query={item.get('query')} "
                + f"expected_doc_ids={item.get('expected_doc_ids')} "
                + f"expected_source_types={item.get('expected_source_types')} "
                + f"hybrid_top3={item.get('hybrid_top3')}"
            )
    lines.extend(
        [
            "",
            "## Suggestions",
            "- Add new FAQ/SOP entries for repeated gap queries.",
            "- Backfill historical cases with richer context snippets.",
            "- Keep hybrid as default for grounded and similar-cases flows.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_eval(
    *,
    seed_root: Path,
    eval_set_path: Path,
    report_path: Path,
    output_path: Path | None,
) -> dict[str, Any]:
    retriever = Retriever(seed_root)
    samples = load_eval_set(eval_set_path)
    metrics = evaluate_retrieval(retriever, samples)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_gap_report(metrics), encoding="utf-8")
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def _is_hit(sample: RetrievalEvalSample, rows: list[dict[str, object]]) -> bool:
    top3 = rows[:3]
    expected_doc_ids = set(sample.expected_doc_ids)
    expected_source_types = set(sample.expected_source_types)
    use_source_fallback = not expected_doc_ids and bool(expected_source_types)
    for row in top3:
        row_doc_id = str(row.get("source_id") or row.get("doc_id") or "")
        row_source = str(row.get("source_type") or "")
        if expected_doc_ids and row_doc_id in expected_doc_ids:
            return True
        if use_source_fallback and row_source in expected_source_types:
            return True
    return False


def _has_grounding(rows: list[dict[str, object]]) -> bool:
    if not rows:
        return False
    for row in rows:
        if not row.get("source_id"):
            return False
        if not row.get("reason"):
            return False
        if not row.get("snippet"):
            return False
    return True


def _has_similar_cases(rows: list[dict[str, object]]) -> bool:
    return any(str(row.get("source_type")) == "history_case" for row in rows)


def _ratio(values: list[bool]) -> float:
    if not values:
        return 0.0
    hit_count = sum(1 for item in values if item)
    return hit_count / len(values)


def _default_seed_root() -> Path:
    return Path(__file__).resolve().parents[2] / "seed_data"


def _default_eval_set_path() -> Path:
    return Path(__file__).resolve().parent / "retrieval_eval_set.json"


def _default_report_path() -> Path:
    return Path(__file__).resolve().parents[2] / "storage" / "reports" / "retrieval_gap_report.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate lexical/vector/hybrid retrieval quality."
    )
    parser.add_argument("--seed-root", default=str(_default_seed_root()))
    parser.add_argument("--eval-set", default=str(_default_eval_set_path()))
    parser.add_argument("--report-path", default=str(_default_report_path()))
    parser.add_argument("--output", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output).resolve() if str(args.output).strip() else None
    metrics = run_eval(
        seed_root=Path(args.seed_root).resolve(),
        eval_set_path=Path(args.eval_set).resolve(),
        report_path=Path(args.report_path).resolve(),
        output_path=output_path,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
