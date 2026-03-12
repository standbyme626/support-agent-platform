from __future__ import annotations

import json
from pathlib import Path

from llm.eval.retrieval_eval import run_eval


def test_retrieval_eval_generates_metrics_and_gap_report(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    metrics_path = tmp_path / "retrieval_eval_metrics.json"
    report_path = tmp_path / "retrieval_gap_report.md"
    metrics = run_eval(
        seed_root=project_root / "seed_data",
        eval_set_path=project_root / "llm" / "eval" / "retrieval_eval_set.json",
        report_path=report_path,
        output_path=metrics_path,
    )

    assert metrics["sample_count"] > 0
    assert "hybrid_top3_hit_rate" in metrics
    assert "grounding_coverage" in metrics
    assert "similar_cases_availability" in metrics
    assert report_path.exists()
    assert metrics_path.exists()
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["sample_count"] == metrics["sample_count"]
