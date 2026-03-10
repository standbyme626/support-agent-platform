from __future__ import annotations

import os
from pathlib import Path


def read_secret(env_key: str, *, file_env: str | None = None) -> str | None:
    """Read a secret from ENV, then file path ENV, then /run/secrets."""
    direct_value = os.getenv(env_key)
    if direct_value:
        return direct_value

    secret_file = os.getenv(file_env or f"{env_key}_FILE")
    if secret_file:
        secret_path = Path(secret_file)
        if secret_path.exists():
            return secret_path.read_text(encoding="utf-8").strip()

    default_secret_path = Path("/run/secrets") / env_key.lower()
    if default_secret_path.exists():
        return default_secret_path.read_text(encoding="utf-8").strip()

    return None


def require_secret(env_key: str, *, file_env: str | None = None) -> str:
    """Read a required secret value or fail with a clear message."""
    secret_value = read_secret(env_key, file_env=file_env)
    if not secret_value:
        raise RuntimeError(f"Missing required secret '{env_key}'. Set {env_key} or {env_key}_FILE.")
    return secret_value
