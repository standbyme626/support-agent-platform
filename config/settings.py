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
class LLMConfig:
    enabled: bool
    provider: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float
    temperature: float
    max_tokens: int | None
    stream: bool


@dataclass(frozen=True)
class AppConfig:
    environment: str
    storage: StorageConfig
    gateway: GatewayConfig
    llm: LLMConfig
    secrets: dict[str, str] = field(default_factory=dict)


def load_app_config(environment: str | None = None, *, root_dir: Path | None = None) -> AppConfig:
    project_root = root_dir or Path(__file__).resolve().parents[1]
    _load_dotenv_if_exists(project_root)

    env_name = environment or os.getenv("SUPPORT_AGENT_ENV", "dev")
    if env_name is None:
        env_name = "dev"

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
    llm_data = config_data.get("llm", {})
    llm = LLMConfig(
        enabled=_env_bool("LLM_ENABLED", default=bool(llm_data.get("enabled", True))),
        provider=os.getenv("LLM_PROVIDER", str(llm_data.get("provider", "openai_compatible"))),
        base_url=os.getenv("OPENAI_BASE_URL", str(llm_data.get("base_url", "http://127.0.0.1:11434/v1"))),
        api_key=os.getenv("OPENAI_API_KEY", str(llm_data.get("api_key", "ollama-local"))),
        model=os.getenv("OPENAI_MODEL", str(llm_data.get("model", "qwen3.5:9b"))),
        timeout_seconds=_env_float(
            "LLM_TIMEOUT_SECONDS",
            default=float(llm_data.get("timeout_seconds", 45.0)),
        ),
        temperature=_env_float("LLM_TEMPERATURE", default=float(llm_data.get("temperature", 0.2))),
        max_tokens=_env_optional_int(
            "LLM_MAX_TOKENS",
            default=_optional_int(llm_data.get("max_tokens")),
        ),
        stream=_env_bool("LLM_STREAM", default=bool(llm_data.get("stream", False))),
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
        llm=llm,
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


def _load_dotenv_if_exists(project_root: Path) -> None:
    env_path = project_root / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        cleaned = value.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
            cleaned = cleaned[1:-1]
        os.environ[key] = cleaned


def _env_bool(key: str, *, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _env_float(key: str, *, default: float) -> float:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_optional_int(key: str, *, default: int | None) -> int | None:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except ValueError:
        return None
