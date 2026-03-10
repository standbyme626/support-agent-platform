from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

from scripts.run_acceptance import run_acceptance


def test_acceptance_runner_outputs_summary_and_trace_kpi(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPPORT_AGENT_ENV", "dev")
    monkeypatch.setenv("SUPPORT_AGENT_SQLITE_PATH", str(tmp_path / "acceptance.db"))

    sample_path = (
        Path(__file__).resolve().parents[2]
        / "seed_data"
        / "acceptance_samples"
        / "default_samples.json"
    )
    output_dir = tmp_path / "acceptance_outputs"
    summary = run_acceptance(
        environment="dev",
        sample_path=sample_path,
        output_dir=output_dir,
        sample_id="faq_direct_reply",
    )

    assert summary["total"] == 1
    assert summary["failed"] == 0

    summary_json = Path(str(summary["summary_json_path"]))
    trace_kpi_json = Path(str(summary["trace_kpi_path"]))
    summary_md = Path(str(summary["summary_md_path"]))

    assert summary_json.exists()
    assert trace_kpi_json.exists()
    assert summary_md.exists()

    parsed = json.loads(summary_json.read_text(encoding="utf-8"))
    assert parsed["results"][0]["replay_command"]
