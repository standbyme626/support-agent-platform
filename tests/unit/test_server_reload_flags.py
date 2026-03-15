from __future__ import annotations

import sys

from pytest import MonkeyPatch

from scripts.ops_api_server import parse_args as parse_ops_api_args
from scripts.wecom_bridge_server import parse_args as parse_wecom_bridge_args


def test_ops_api_parse_args_accepts_reload_flags(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ops_api_server.py",
            "--env",
            "dev",
            "--host",
            "127.0.0.1",
            "--port",
            "18082",
            "--reload",
            "--reload-interval",
            "0.5",
        ],
    )
    args = parse_ops_api_args()

    assert args.env == "dev"
    assert args.reload is True
    assert args.reload_interval == 0.5


def test_wecom_bridge_parse_args_accepts_reload_flags(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "wecom_bridge_server.py",
            "--env",
            "dev",
            "--host",
            "127.0.0.1",
            "--port",
            "18081",
            "--path",
            "/wecom/process",
            "--reload",
            "--reload-interval",
            "0.8",
        ],
    )
    args = parse_wecom_bridge_args()

    assert args.env == "dev"
    assert args.path == "/wecom/process"
    assert args.reload is True
    assert args.reload_interval == 0.8
