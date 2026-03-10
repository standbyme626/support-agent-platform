from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .secrets import read_secret


@dataclass(frozen=True)
class StorageConfig:
    sqlite_path: Path


@dataclass(frozen=True)
class GatewayConfig:
    name: str
    log_path: Path


@dataclass(frozen=True)
class AppConfig:
    environment: str
    storage: StorageConfig
    gateway: GatewayConfig
    secrets: dict[str, str] = field(default_factory=dict)


def load_app_config(environment: str | None = None, *, root_dir: Path | None = None) -> AppConfig:
    env_name = environment or os.getenv("SUPPORT_AGENT_ENV", "dev")
    if env_name is None:
        env_name = "dev"
    project_root = root_dir or Path(__file__).resolve().parents[1]

    config_file = project_root / "config" / "environments" / f"{env_name}.toml"
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    config_data = tomllib.loads(config_file.read_text(encoding="utf-8"))

    storage = StorageConfig(
        sqlite_path=_resolve_path(
            config_data["storage"]["sqlite_path"],
            root_dir=project_root,
            env_override="SUPPORT_AGENT_SQLITE_PATH",
        )
    )
    gateway = GatewayConfig(
        name=config_data["gateway"]["name"],
        log_path=_resolve_path(config_data["gateway"]["log_path"], root_dir=project_root),
    )

    secret_values: dict[str, str] = {}
    for key, secret_config in config_data.get("secrets", {}).items():
        env_key = secret_config.get("env", key)
        file_env = secret_config.get("file_env")
        value = read_secret(env_key, file_env=file_env)
        if value is not None:
            secret_values[key] = value

    return AppConfig(
        environment=env_name,
        storage=storage,
        gateway=gateway,
        secrets=secret_values,
    )


def _resolve_path(value: str, *, root_dir: Path, env_override: str | None = None) -> Path:
    if env_override:
        overridden = os.getenv(env_override)
        if overridden:
            return Path(overridden).expanduser().resolve()

    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (root_dir / candidate).resolve()
