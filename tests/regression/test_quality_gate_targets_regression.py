from __future__ import annotations

from pathlib import Path


def test_makefile_quality_gate_targets_regression() -> None:
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(encoding="utf-8")

    assert "test-unit:" in makefile
    assert "test-workflow:" in makefile
    assert "test-regression:" in makefile
    assert "test-integration:" in makefile
    assert "smoke-replay:" in makefile
    assert "acceptance:" in makefile
    assert "trace-kpi:" in makefile
    expected = (
        "check: validate-structure lint typecheck test-unit "
        "test-workflow test-regression test-integration smoke-replay"
    )
    assert expected in makefile
