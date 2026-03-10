from __future__ import annotations

from pathlib import Path


def test_containerization_and_ci_guardrails_present() -> None:
    project_root = Path(__file__).resolve().parents[2]

    dockerfile = project_root / "Dockerfile"
    compose_file = project_root / "docker-compose.yml"
    dockerignore = project_root / ".dockerignore"
    ci_file = project_root / ".github" / "workflows" / "ci.yml"

    assert dockerfile.exists()
    assert compose_file.exists()
    assert dockerignore.exists()
    assert ci_file.exists()

    dockerfile_text = dockerfile.read_text(encoding="utf-8")
    compose_text = compose_file.read_text(encoding="utf-8")
    ci_text = ci_file.read_text(encoding="utf-8")

    assert "FROM python:3.11-slim" in dockerfile_text
    assert "pip install -e \".[dev]\"" in dockerfile_text

    assert "smoke:" in compose_text
    assert "\"pytest\"" in compose_text
    assert "\"tests/integration/test_openclaw_gateway.py\"" in compose_text

    assert "quality:" in ci_text
    assert "smoke-container:" in ci_text
    assert "acceptance:" in ci_text
    assert "make ci" in ci_text
    assert "docker compose run --rm smoke" in ci_text
    assert "make acceptance-gate" in ci_text
