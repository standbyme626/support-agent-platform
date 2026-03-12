from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from config import load_app_config
from config.settings import LLMConfig
from llm import build_summary_model_adapter


def test_load_app_config_reads_llm_values_from_dotenv(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    for key in [
        "SUPPORT_AGENT_ENV",
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "LLM_ENABLED",
        "LLM_STREAM",
    ]:
        monkeypatch.delenv(key, raising=False)

    env_dir = tmp_path / "config" / "environments"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "dev.toml").write_text(
        "\n".join(
            [
                "[gateway]",
                'name = "test-gateway"',
                'log_path = "storage/test.log"',
                "",
                "[storage]",
                'sqlite_path = "storage/test.db"',
                "",
                "[llm]",
                "enabled = true",
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:11434/v1"',
                'api_key = "default-key"',
                'model = "default-model"',
                "timeout_seconds = 30",
                "temperature = 0.2",
                "stream = false",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "SUPPORT_AGENT_ENV=dev",
                "LLM_ENABLED=true",
                "OPENAI_BASE_URL=http://100.90.236.32:11434/v1",
                "OPENAI_API_KEY=ollama-local",
                "OPENAI_MODEL=qwen3.5:9b",
                "LLM_STREAM=true",
                "LLM_RETRY=2",
            ]
        ),
        encoding="utf-8",
    )

    app_config = load_app_config(root_dir=tmp_path)
    assert app_config.llm.base_url == "http://100.90.236.32:11434/v1"
    assert app_config.llm.model == "qwen3.5:9b"
    assert app_config.llm.stream is True
    assert app_config.llm.retry_count == 2


def test_build_summary_model_adapter_can_be_disabled() -> None:
    adapter = build_summary_model_adapter(
        LLMConfig(
            enabled=False,
            provider="openai_compatible",
            base_url="http://127.0.0.1:11434/v1",
            api_key="ollama-local",
            model="qwen3.5:9b",
            timeout_seconds=30,
            retry_count=1,
            temperature=0.2,
            max_tokens=None,
            stream=False,
        )
    )
    assert adapter is None


def test_load_app_config_supports_dashscope_alias_envs(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    for key in [
        "SUPPORT_AGENT_ENV",
        "OPENAI_BASE_URL",
        "OPENAI_API_BASE",
        "OPENAI_API_KEY",
        "API_KEY_ROTATION_LIST",
        "DASHSCOPE_API_KEY_POOL",
        "OPENAI_MODEL",
        "OPENAI_MODEL_NAME",
        "MODEL_CANDIDATES",
    ]:
        monkeypatch.delenv(key, raising=False)

    env_dir = tmp_path / "config" / "environments"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "dev.toml").write_text(
        "\n".join(
            [
                "[gateway]",
                'name = "test-gateway"',
                'log_path = "storage/test.log"',
                "",
                "[storage]",
                'sqlite_path = "storage/test.db"',
                "",
                "[llm]",
                "enabled = true",
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:11434/v1"',
                'api_key = "default-key"',
                'model = "default-model"',
                "timeout_seconds = 30",
                "temperature = 0.2",
                "stream = false",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "SUPPORT_AGENT_ENV=dev",
                "OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1",
                "API_KEY_ROTATION_LIST=key-a,key-b",
                "OPENAI_MODEL_NAME=qwen3.5-27b,qwen-plus-2025-07-28",
            ]
        ),
        encoding="utf-8",
    )

    app_config = load_app_config(root_dir=tmp_path)
    assert app_config.llm.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert app_config.llm.api_key == "key-a"
    assert app_config.llm.model == "qwen3.5-27b"
