from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Callable

RELOADER_CHILD_ENV = "SUPPORT_AGENT_RELOADER_CHILD"
_WATCH_SUFFIXES: frozenset[str] = frozenset({".py", ".toml", ".yaml", ".yml", ".json"})
_WATCH_FILENAMES: frozenset[str] = frozenset({".env", ".env.local", ".env.dev"})
_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".idea",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "logs",
        "node_modules",
        "venv",
    }
)


def build_default_watch_roots(repo_root: Path) -> list[Path]:
    roots: list[Path] = []
    for rel in (
        "app",
        "channel_adapters",
        "core",
        "llm",
        "openclaw_adapter",
        "runtime",
        "scripts",
        "storage",
        "workflows",
    ):
        candidate = repo_root / rel
        if candidate.exists():
            roots.append(candidate)

    for rel in ("config.py", "pyproject.toml", ".env", ".env.local", ".env.dev"):
        candidate = repo_root / rel
        if candidate.exists():
            roots.append(candidate)
    return roots


def build_file_snapshot(watch_roots: Iterable[Path]) -> dict[str, int]:
    snapshot: dict[str, int] = {}
    for path in _iter_watch_files(watch_roots):
        try:
            snapshot[str(path)] = path.stat().st_mtime_ns
        except FileNotFoundError:
            continue
    return snapshot


def detect_changed_paths(
    previous: dict[str, int], current: dict[str, int], *, max_items: int = 5
) -> list[str]:
    changed = [
        path
        for path in sorted(set(previous) | set(current))
        if previous.get(path) != current.get(path)
    ]
    return changed[: max(1, max_items)]


def run_with_reloader(
    *,
    argv: list[str],
    watch_roots: Iterable[Path],
    interval_seconds: float = 1.0,
    service_name: str,
    logger: Callable[[str], None] | None = None,
) -> int:
    log = logger or _print_line
    interval = max(0.2, float(interval_seconds))
    snapshot = build_file_snapshot(watch_roots)
    log(
        f"[reload:{service_name}] watching {len(snapshot)} files; "
        f"interval={interval:.1f}s"
    )
    child = _spawn_child(argv)
    try:
        while True:
            exit_code = child.poll()
            if exit_code is not None:
                log(f"[reload:{service_name}] child exited code={exit_code}")
                return exit_code

            time.sleep(interval)
            current = build_file_snapshot(watch_roots)
            changed_paths = detect_changed_paths(snapshot, current)
            if not changed_paths:
                continue

            changed_summary = ", ".join(Path(path).name for path in changed_paths)
            log(f"[reload:{service_name}] change detected ({changed_summary}); reloading")
            _stop_child(child)
            child = _spawn_child(argv)
            snapshot = current
    except KeyboardInterrupt:
        log(f"[reload:{service_name}] stopped by keyboard interrupt")
        _stop_child(child)
        return 0


def _iter_watch_files(watch_roots: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in watch_roots:
        root = Path(root)
        if root.is_file():
            if _should_watch_file(root):
                resolved = root.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield resolved
            continue

        if not root.is_dir():
            continue

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS]
            base = Path(dirpath)
            for filename in filenames:
                candidate = base / filename
                if not _should_watch_file(candidate):
                    continue
                resolved = candidate.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                yield resolved


def _should_watch_file(path: Path) -> bool:
    return path.suffix.lower() in _WATCH_SUFFIXES or path.name in _WATCH_FILENAMES


def _spawn_child(argv: list[str]) -> subprocess.Popen[bytes]:
    child_env = dict(os.environ)
    child_env[RELOADER_CHILD_ENV] = "1"
    return subprocess.Popen(argv, env=child_env)


def _stop_child(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2.0)


def _print_line(text: str) -> None:
    print(text, flush=True)


__all__ = [
    "RELOADER_CHILD_ENV",
    "build_default_watch_roots",
    "build_file_snapshot",
    "detect_changed_paths",
    "run_with_reloader",
]
