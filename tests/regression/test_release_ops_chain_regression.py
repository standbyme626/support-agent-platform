from __future__ import annotations

from pathlib import Path


def test_release_ops_targets_and_runbook_chain_present() -> None:
    project_root = Path(__file__).resolve().parents[2]
    makefile = (project_root / "Makefile").read_text(encoding="utf-8")
    runbook = (project_root / "RUNBOOK.md").read_text(encoding="utf-8")

    assert "deploy-release:" in makefile
    assert "verify-release:" in makefile
    assert "rollback-release:" in makefile
    assert "release-cycle: deploy-release verify-release rollback-release" in makefile

    assert "python -m scripts.deploy_release --env dev" in runbook
    assert "python -m scripts.verify_release --env dev --require-active-release" in runbook
    assert "python -m scripts.rollback_release --env dev" in runbook
    assert "make release-cycle ENV=dev" in runbook
