from __future__ import annotations

from pathlib import Path

REQUIRED_DIRS = [
    "channel_adapters",
    "channel_adapters/feishu_adapter",
    "channel_adapters/telegram_adapter",
    "channel_adapters/wecom_adapter",
    "config",
    "config/environments",
    "openclaw_adapter",
    "storage",
    "tests/integration",
    "tests/regression",
    "tests/unit",
    "tests/workflow",
]

REQUIRED_FILES = [
    ".env.example",
    "pyproject.toml",
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
    ".github/workflows/ci.yml",
    "config/settings.py",
    "config/secrets.py",
    "openclaw_adapter/inbound_handler.py",
    "openclaw_adapter/channel_router.py",
    "openclaw_adapter/outbound_sender.py",
    "openclaw_adapter/session_mapper.py",
    "scripts/healthcheck.py",
    "scripts/trace_debug.py",
    "scripts/replay_gateway_event.py",
    "scripts/run_acceptance.py",
    "scripts/trace_kpi.py",
    "scripts/deploy_release.py",
    "scripts/verify_release.py",
    "scripts/rollback_release.py",
    "scripts/release_state.py",
    "seed_data/acceptance_samples/default_samples.json",
]


def validate_structure(project_root: Path) -> list[str]:
    errors: list[str] = []

    for rel in REQUIRED_DIRS:
        if not (project_root / rel).is_dir():
            errors.append(f"Missing directory: {rel}")

    for rel in REQUIRED_FILES:
        if not (project_root / rel).is_file():
            errors.append(f"Missing file: {rel}")

    return errors


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    errors = validate_structure(project_root)
    if errors:
        for err in errors:
            print(err)
        return 1

    print("Structure validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
