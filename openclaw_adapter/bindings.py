from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from channel_adapters.feishu_adapter import FeishuAdapter
from channel_adapters.telegram_adapter import TelegramAdapter
from channel_adapters.wecom_adapter import WeComAdapter
from config import AppConfig, load_app_config
from core.trace_logger import JsonTraceLogger

from .channel_router import ChannelRouter
from .session_mapper import SessionMapper


@dataclass(frozen=True)
class GatewayBindings:
    channel_router: ChannelRouter
    session_mapper: SessionMapper
    trace_logger: JsonTraceLogger


def build_default_bindings(config: AppConfig | None = None) -> GatewayBindings:
    app_config = config or load_app_config()
    session_mapper = SessionMapper(Path(app_config.storage.sqlite_path))
    channel_router = ChannelRouter(
        {
            "feishu": FeishuAdapter(),
            "telegram": TelegramAdapter(),
            "wecom": WeComAdapter(),
        }
    )
    trace_logger = JsonTraceLogger(Path(app_config.gateway.log_path))
    return GatewayBindings(
        channel_router=channel_router,
        session_mapper=session_mapper,
        trace_logger=trace_logger,
    )
