from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s]{6,}\d)(?!\d)")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_ORDER_RE = re.compile(r"\b(?:ORD|TCK|INC|CASE)[-_]?[A-Za-z0-9]{4,}\b", flags=re.IGNORECASE)

_FAQ_QUESTION_KEYS = ("question", "query", "instruction", "title", "prompt")
_FAQ_ANSWER_KEYS = ("answer", "response", "output", "content", "resolution")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _redact_pii(text: str) -> str:
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    redacted = _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    redacted = _ORDER_RE.sub("[REDACTED_TICKET_ID]", redacted)
    return redacted


def _safe_text(value: Any) -> str:
    return _redact_pii(str(value or "").strip())


def _safe_identifier(value: Any) -> str:
    return str(value or "").strip()


def _normalize_row_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key).strip().lower(): value for key, value in row.items()}


def _first_non_empty(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = _safe_text(value)
        if text:
            return text
    return ""


def _clip(text: str, *, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)].rstrip()}..."


def _doc_fingerprint(doc: dict[str, Any]) -> str:
    title = str(doc.get("title") or "").lower().strip()
    content = str(doc.get("content") or "").lower().strip()
    payload = f"{title}\n{content}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _dedupe_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for doc in docs:
        signature = _doc_fingerprint(doc)
        if signature in seen:
            continue
        seen.add(signature)
        output.append(doc)
    return output


def _load_json_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Some datasets (for example MakTek) ship JSONL instead of one JSON array.
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return [item for item in payload["data"] if isinstance(item, dict)]
        if isinstance(payload.get("train"), list):
            return [item for item in payload["train"] if isinstance(item, dict)]
    return []


def _load_csv_records(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(item) for item in reader]


def _base_metadata(
    *,
    source_dataset: str,
    source_url: str,
    license_name: str,
    commercial_use: bool,
    imported_at: str,
) -> dict[str, Any]:
    return {
        "source_dataset": source_dataset,
        "source_url": source_url,
        "license": license_name,
        "commercial_use": commercial_use,
        "imported_at": imported_at,
        "governance_tier": "external_public",
    }


def build_faq_docs(path: Path, *, limit: int, imported_at: str) -> list[dict[str, Any]]:
    records = _load_json_records(path)
    docs: list[dict[str, Any]] = []
    for row in records:
        normalized = _normalize_row_keys(row)
        question = _first_non_empty(normalized, _FAQ_QUESTION_KEYS)
        answer = _first_non_empty(normalized, _FAQ_ANSWER_KEYS)
        if not question or not answer:
            continue
        category = _safe_text(normalized.get("category") or normalized.get("topic") or "general")
        doc_id = f"faq_ext_{len(docs) + 1:05d}"
        docs.append(
            {
                "doc_id": doc_id,
                "source_type": "faq",
                "title": _clip(f"FAQ: {question}", limit=96),
                "content": _clip(f"Q: {question}\nA: {answer}", limit=2200),
                "tags": ["external", "faq", category.lower()],
                "updated_at": imported_at,
                "metadata": _base_metadata(
                    source_dataset="MakTek/Customer_support_faqs_dataset",
                    source_url="https://huggingface.co/datasets/MakTek/Customer_support_faqs_dataset",
                    license_name="Apache-2.0",
                    commercial_use=True,
                    imported_at=imported_at,
                ),
            }
        )
        if len(docs) >= limit:
            break
    return _dedupe_docs(docs)


def _extract_history_tags(row: dict[str, Any]) -> list[str]:
    tags: list[str] = ["external", "history_case"]
    for key in ("type", "queue", "priority", "language"):
        value = _safe_text(row.get(key) or "")
        if value:
            tags.append(value.lower())
    for key, value in row.items():
        key_text = str(key).lower()
        if "tag" not in key_text:
            continue
        value_text = _safe_text(value)
        if value_text:
            tags.append(value_text.lower())
    deduped: list[str] = []
    seen: set[str] = set()
    for item in tags:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def build_history_docs(path: Path, *, limit: int, imported_at: str) -> list[dict[str, Any]]:
    records = _load_csv_records(path)
    docs: list[dict[str, Any]] = []
    for row in records:
        normalized = _normalize_row_keys(row)
        subject = _safe_text(normalized.get("subject") or normalized.get("title") or "")
        body = _safe_text(normalized.get("body") or normalized.get("description") or "")
        answer = _safe_text(normalized.get("answer") or normalized.get("resolution") or "")
        if not subject or not (body or answer):
            continue
        title = _clip(f"历史案例: {subject}", limit=96)
        content_parts = [f"Subject: {subject}"]
        if body:
            content_parts.append(f"Ticket: {body}")
        if answer:
            content_parts.append(f"Resolution: {answer}")
        content = _clip("\n".join(content_parts), limit=2400)
        doc_id = f"case_ext_{len(docs) + 1:05d}"
        docs.append(
            {
                "doc_id": doc_id,
                "source_type": "history_case",
                "title": title,
                "content": content,
                "tags": _extract_history_tags(normalized),
                "updated_at": imported_at,
                "metadata": _base_metadata(
                    source_dataset="Tobi-Bueck/customer-support-tickets",
                    source_url="https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets",
                    license_name="CC-BY-NC-4.0",
                    commercial_use=False,
                    imported_at=imported_at,
                ),
            }
        )
        if len(docs) >= limit:
            break
    return _dedupe_docs(docs)


def _incident_id(row: dict[str, Any]) -> str:
    for key in (
        "number",
        "incident_id",
        "incident number",
        "incident_number",
        "case_id",
        "issue_id",
        "id",
    ):
        value = _safe_identifier(row.get(key) or "")
        if value:
            return value
    return ""


def build_uci_process_docs(path: Path, *, limit: int, imported_at: str) -> list[dict[str, Any]]:
    records = [_normalize_row_keys(row) for row in _load_csv_records(path)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        incident = _incident_id(row)
        if not incident:
            continue
        grouped[incident].append(row)

    docs: list[dict[str, Any]] = []
    for incident, rows in grouped.items():
        if len(docs) >= limit:
            break
        first = rows[0]
        state = _safe_text(first.get("incident_state") or "unknown")
        priority = _safe_text(first.get("priority") or "unknown")
        assignment_group = _safe_text(first.get("assignment_group") or "unknown")
        made_sla = _safe_text(first.get("made_sla") or "unknown")
        reopen_count = _safe_text(first.get("reopen_count") or "0")
        reassignment_count = _safe_text(first.get("reassignment_count") or "0")
        content = (
            f"Incident {incident}: state={state}, priority={priority}, assignment_group={assignment_group}, "
            f"made_sla={made_sla}, reopen_count={reopen_count}, reassignment_count={reassignment_count}."
        )
        docs.append(
            {
                "doc_id": f"process_uci_{len(docs) + 1:05d}",
                "source_type": "history_case",
                "title": _clip(f"流程事件(UCI): Incident {incident}", limit=96),
                "content": _clip(content, limit=2200),
                "tags": ["external", "process", "sla", "uci"],
                "updated_at": imported_at,
                "metadata": _base_metadata(
                    source_dataset="UCI Incident Management Process Enriched Event Log",
                    source_url="https://archive.ics.uci.edu/dataset/498/incident+management+process+enriched+event+log",
                    license_name="CC BY 4.0",
                    commercial_use=True,
                    imported_at=imported_at,
                ),
            }
        )
    return _dedupe_docs(docs)


def build_mendeley_process_docs(
    issues_path: Path,
    history_path: Path | None,
    *,
    limit: int,
    imported_at: str,
) -> list[dict[str, Any]]:
    issues = [_normalize_row_keys(row) for row in _load_csv_records(issues_path)]
    history_by_issue: dict[str, int] = defaultdict(int)
    if history_path and history_path.exists():
        for row in _load_csv_records(history_path):
            normalized = _normalize_row_keys(row)
            issue_id = _incident_id(normalized)
            if issue_id:
                history_by_issue[issue_id] += 1

    docs: list[dict[str, Any]] = []
    for row in issues:
        if len(docs) >= limit:
            break
        issue_id = _incident_id(row)
        if not issue_id:
            continue
        title = _safe_text(row.get("subject") or row.get("title") or "")
        description = _safe_text(row.get("description") or row.get("body") or "")
        status = _safe_text(row.get("status") or "unknown")
        assignee = _safe_text(row.get("assignee") or row.get("assigned_to") or "unknown")
        if not (title or description):
            continue
        content = (
            f"Issue {issue_id}: status={status}, assignee={assignee}, "
            f"change_events={history_by_issue.get(issue_id, 0)}.\n"
            f"Summary: {_clip(description or title, limit=1800)}"
        )
        docs.append(
            {
                "doc_id": f"process_mendeley_{len(docs) + 1:05d}",
                "source_type": "history_case",
                "title": _clip(f"流程事件(Mendeley): {title or issue_id}", limit=96),
                "content": _clip(content, limit=2200),
                "tags": ["external", "process", "sla", "mendeley"],
                "updated_at": imported_at,
                "metadata": _base_metadata(
                    source_dataset="Help Desk Tickets (Mendeley, 2025)",
                    source_url="https://data.mendeley.com/",
                    license_name="CC BY 4.0",
                    commercial_use=True,
                    imported_at=imported_at,
                ),
            }
        )
    return _dedupe_docs(docs)


def build_project_sop_docs(*, repo_root: Path, imported_at: str) -> list[dict[str, Any]]:
    readme_path = repo_root / "README.md"
    architecture_path = repo_root / "ARCHITECTURE.md"
    plan_path = repo_root / "docs" / "project-review-refactor-plan.md"
    references = [
        path.as_posix()
        for path in (readme_path, architecture_path, plan_path)
        if path.exists()
    ]
    reference_text = ", ".join(references) if references else "project docs"

    docs = [
        {
            "doc_id": "sop_proj_0001",
            "source_type": "sop",
            "title": "SOP: 重启 Ops API 并验证健康",
            "content": (
                "1) mkdir -p logs\n"
                "2) pkill -f \"python -m scripts.ops_api_server\" || true\n"
                "3) nohup python -m scripts.ops_api_server --env dev --host 127.0.0.1 --port 18082 "
                "> logs/ops_api_server.log 2>&1 &\n"
                "4) curl http://127.0.0.1:18082/healthz"
            ),
            "tags": ["sop", "ops", "healthcheck"],
            "updated_at": imported_at,
            "metadata": {
                "source_dataset": "support-agent-platform internal docs",
                "source_url": reference_text,
                "license": "Internal project docs",
                "commercial_use": True,
                "imported_at": imported_at,
                "governance_tier": "project_internal",
            },
        },
        {
            "doc_id": "sop_proj_0002",
            "source_type": "sop",
            "title": "SOP: 启动 Web Console 并验证页面",
            "content": (
                "1) cd web_console\n"
                "2) npm install\n"
                "3) npm run dev -- --host 0.0.0.0 --port 3001\n"
                "4) 打开 /tickets、/kb/faq 并确认页面可访问"
            ),
            "tags": ["sop", "web_console", "runbook"],
            "updated_at": imported_at,
            "metadata": {
                "source_dataset": "support-agent-platform internal docs",
                "source_url": reference_text,
                "license": "Internal project docs",
                "commercial_use": True,
                "imported_at": imported_at,
                "governance_tier": "project_internal",
            },
        },
        {
            "doc_id": "sop_proj_0003",
            "source_type": "sop",
            "title": "SOP: 工单知识库回归校验",
            "content": (
                "1) cd web_console && npm run lint\n"
                "2) cd web_console && npm run typecheck\n"
                "3) cd web_console && npm run test -- tickets\n"
                "4) 检查 /kb/faq 是否展示来源与许可证字段"
            ),
            "tags": ["sop", "qa", "kb"],
            "updated_at": imported_at,
            "metadata": {
                "source_dataset": "support-agent-platform internal docs",
                "source_url": reference_text,
                "license": "Internal project docs",
                "commercial_use": True,
                "imported_at": imported_at,
                "governance_tier": "project_internal",
            },
        },
    ]
    return docs


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _bootstrap_docs(imported_at: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    faq_docs = [
        {
            "doc_id": "faq_bootstrap_0001",
            "source_type": "faq",
            "title": "FAQ: 如何重置账户密码",
            "content": "Q: 如何重置账户密码？\nA: 进入账户中心，完成验证码校验后可重置密码。",
            "tags": ["external", "faq", "account"],
            "updated_at": imported_at,
            "metadata": _base_metadata(
                source_dataset="MakTek/Customer_support_faqs_dataset",
                source_url="https://huggingface.co/datasets/MakTek/Customer_support_faqs_dataset",
                license_name="Apache-2.0",
                commercial_use=True,
                imported_at=imported_at,
            ),
        },
        {
            "doc_id": "faq_bootstrap_0002",
            "source_type": "faq",
            "title": "FAQ: 如何查询退款进度",
            "content": "Q: 如何查询退款进度？\nA: 在订单详情页输入工单号即可查询退款状态。",
            "tags": ["external", "faq", "billing"],
            "updated_at": imported_at,
            "metadata": _base_metadata(
                source_dataset="MakTek/Customer_support_faqs_dataset",
                source_url="https://huggingface.co/datasets/MakTek/Customer_support_faqs_dataset",
                license_name="Apache-2.0",
                commercial_use=True,
                imported_at=imported_at,
            ),
        },
    ]
    history_docs = [
        {
            "doc_id": "case_bootstrap_0001",
            "source_type": "history_case",
            "title": "历史案例: VPN access not working",
            "content": "Subject: VPN access not working\nTicket: User cannot connect from remote office.\nResolution: Re-sync MFA and renew VPN profile.",
            "tags": ["external", "history_case", "incident", "high"],
            "updated_at": imported_at,
            "metadata": _base_metadata(
                source_dataset="Tobi-Bueck/customer-support-tickets",
                source_url="https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets",
                license_name="CC-BY-NC-4.0",
                commercial_use=False,
                imported_at=imported_at,
            ),
        },
        {
            "doc_id": "process_bootstrap_0001",
            "source_type": "history_case",
            "title": "流程事件(UCI): Incident INC-10001",
            "content": "Incident INC-10001: state=resolved, priority=2, assignment_group=network, made_sla=true, reopen_count=0, reassignment_count=1.",
            "tags": ["external", "process", "sla", "uci"],
            "updated_at": imported_at,
            "metadata": _base_metadata(
                source_dataset="UCI Incident Management Process Enriched Event Log",
                source_url="https://archive.ics.uci.edu/dataset/498/incident+management+process+enriched+event+log",
                license_name="CC BY 4.0",
                commercial_use=True,
                imported_at=imported_at,
            ),
        },
    ]
    sop_docs = []
    return faq_docs, history_docs, sop_docs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import external KB datasets into seed_data JSON files.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--seed-root", type=Path, default=None)
    parser.add_argument("--faq-json", type=Path, default=None)
    parser.add_argument("--history-csv", type=Path, default=None)
    parser.add_argument("--uci-events-csv", type=Path, default=None)
    parser.add_argument("--mendeley-issues-csv", type=Path, default=None)
    parser.add_argument("--mendeley-history-csv", type=Path, default=None)
    parser.add_argument("--max-faq", type=int, default=500)
    parser.add_argument("--max-history", type=int, default=1000)
    parser.add_argument("--max-process", type=int, default=600)
    parser.add_argument("--include-project-sop", action="store_true")
    parser.add_argument("--use-bootstrap-samples", action="store_true")
    parser.add_argument("--write-manifest", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    seed_root = (args.seed_root or repo_root / "seed_data").resolve()
    imported_at = _now_iso()

    faq_docs: list[dict[str, Any]] = []
    history_docs: list[dict[str, Any]] = []
    sop_docs: list[dict[str, Any]] = []

    if args.faq_json and args.faq_json.exists():
        faq_docs.extend(build_faq_docs(args.faq_json, limit=max(1, args.max_faq), imported_at=imported_at))

    if args.history_csv and args.history_csv.exists():
        history_docs.extend(
            build_history_docs(
                args.history_csv,
                limit=max(1, args.max_history),
                imported_at=imported_at,
            )
        )

    if args.uci_events_csv and args.uci_events_csv.exists():
        history_docs.extend(
            build_uci_process_docs(
                args.uci_events_csv,
                limit=max(1, args.max_process),
                imported_at=imported_at,
            )
        )

    if args.mendeley_issues_csv and args.mendeley_issues_csv.exists():
        history_docs.extend(
            build_mendeley_process_docs(
                args.mendeley_issues_csv,
                args.mendeley_history_csv,
                limit=max(1, args.max_process),
                imported_at=imported_at,
            )
        )

    if args.include_project_sop:
        sop_docs.extend(build_project_sop_docs(repo_root=repo_root, imported_at=imported_at))

    if args.use_bootstrap_samples:
        faq_bootstrap, history_bootstrap, sop_bootstrap = _bootstrap_docs(imported_at)
        faq_docs.extend(faq_bootstrap)
        history_docs.extend(history_bootstrap)
        sop_docs.extend(sop_bootstrap)

    faq_docs = _dedupe_docs(faq_docs)
    history_docs = _dedupe_docs(history_docs)
    sop_docs = _dedupe_docs(sop_docs)

    faq_output = seed_root / "faq" / "faq_external_documents.json"
    history_output = seed_root / "historical_cases" / "history_external_documents.json"
    sop_output = seed_root / "sop" / "sop_project_documents.json"

    _write_json(faq_output, faq_docs)
    _write_json(history_output, history_docs)
    _write_json(sop_output, sop_docs)

    manifest: dict[str, Any] = {
        "imported_at": imported_at,
        "faq_count": len(faq_docs),
        "history_count": len(history_docs),
        "sop_count": len(sop_docs),
        "outputs": {
            "faq": faq_output.as_posix(),
            "history_case": history_output.as_posix(),
            "sop": sop_output.as_posix(),
        },
        "governance": {
            "faq": {"license": "Apache-2.0", "commercial_use": True},
            "history_case": {"license": "CC-BY-NC-4.0", "commercial_use": False},
            "process_logs": {"license": "CC BY 4.0", "commercial_use": True},
        },
    }

    if args.write_manifest:
        _write_json(seed_root / "external_sources_manifest.json", manifest)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
