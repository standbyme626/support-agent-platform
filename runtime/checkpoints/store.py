from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import uuid4

from runtime.state import RuntimeState, clone_runtime_state


@dataclass(frozen=True)
class CheckpointRecord:
    checkpoint_id: str
    next_node: str
    state: RuntimeState
    created_at: str


class CheckpointStoreProtocol(Protocol):
    def save(self, state: RuntimeState, *, next_node: str) -> str: ...

    def load(self, checkpoint_id: str) -> RuntimeState: ...

    def load_record(self, checkpoint_id: str) -> CheckpointRecord: ...

    def delete(self, checkpoint_id: str) -> None: ...


class FileCheckpointStore:
    """Minimal file-backed checkpoint store for runtime pause/resume."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write_payload({})

    def save(self, state: RuntimeState, *, next_node: str) -> str:
        checkpoint_id = f"cp-{uuid4().hex}"
        payload = self._read_payload()
        payload[checkpoint_id] = {
            "next_node": next_node,
            "created_at": datetime.now(UTC).isoformat(),
            "state": clone_runtime_state(state),
        }
        self._write_payload(payload)
        return checkpoint_id

    def load(self, checkpoint_id: str) -> RuntimeState:
        return clone_runtime_state(self.load_record(checkpoint_id).state)

    def load_record(self, checkpoint_id: str) -> CheckpointRecord:
        payload = self._read_payload()
        record = payload.get(checkpoint_id)
        if record is None:
            raise KeyError(f"checkpoint {checkpoint_id} not found")
        state = record.get("state")
        if not isinstance(state, dict):
            raise RuntimeError(f"checkpoint {checkpoint_id} has invalid state payload")
        runtime_state = cast(RuntimeState, state)
        return CheckpointRecord(
            checkpoint_id=checkpoint_id,
            next_node=str(record.get("next_node") or ""),
            state=clone_runtime_state(runtime_state),
            created_at=str(record.get("created_at") or ""),
        )

    def delete(self, checkpoint_id: str) -> None:
        payload = self._read_payload()
        if checkpoint_id not in payload:
            raise KeyError(f"checkpoint {checkpoint_id} not found")
        payload.pop(checkpoint_id)
        self._write_payload(payload)

    def _read_payload(self) -> dict[str, Any]:
        raw = self._path.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise RuntimeError("checkpoint store payload must be a JSON object")
        return data

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
