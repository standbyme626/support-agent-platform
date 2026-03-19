from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.wecom_bridge_server import process_wecom_message
from storage.models import InboundEnvelope
from workflows.support_intake_workflow import SupportIntakeWorkflow


def _load_system_corpus() -> dict:
    corpus_path = (
        Path(__file__).resolve().parents[2]
        / "seed_data"
        / "acceptance_samples"
        / "system_corpus.json"
    )
    with open(corpus_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def system_corpus() -> dict:
    return _load_system_corpus()


class TestSystemCorpusRegression:
    """十系统真实语料回归测试 - 验证 system 推断准确性"""

    def test_corpus_structure(self, system_corpus: dict) -> None:
        assert "systems" in system_corpus
        systems = system_corpus["systems"]
        assert len(systems) == 10
        expected_systems = {
            "ticket",
            "procurement",
            "finance",
            "approval",
            "hr",
            "asset",
            "kb",
            "crm",
            "project",
            "supply_chain",
        }
        assert set(systems.keys()) == expected_systems

    def test_corpus_samples_count(self, system_corpus: dict) -> None:
        total = 0
        for system_key, system_data in system_corpus["systems"].items():
            samples = system_data["samples"]
            assert len(samples) >= 10, f"{system_key} should have at least 10 samples"
            total += len(samples)
        assert total >= 100, f"Total samples should be at least 100, got {total}"

    def test_ticket_system_samples(self, system_corpus: dict) -> None:
        samples = system_corpus["systems"]["ticket"]["samples"]
        expected_system = "ticket"
        for sample in samples:
            assert sample["expected_system"] == expected_system
            assert "text" in sample
            assert "id" in sample
            assert sample["text"].strip(), f"Sample {sample['id']} has empty text"

    def test_procurement_system_samples(self, system_corpus: dict) -> None:
        samples = system_corpus["systems"]["procurement"]["samples"]
        expected_system = "procurement"
        procurement_keywords = ("采购", "请购", "购买", "PO", "procurement", "purchase")
        for sample in samples:
            assert sample["expected_system"] == expected_system
            text_lower = sample["text"].lower()
            has_keyword = any(k.lower() in text_lower for k in procurement_keywords)
            assert has_keyword, (
                f"Sample {sample['id']} missing procurement keywords: {sample['text']}"
            )

    def test_finance_system_samples(self, system_corpus: dict) -> None:
        samples = system_corpus["systems"]["finance"]["samples"]
        expected_system = "finance"
        for sample in samples:
            assert sample["expected_system"] == expected_system
            assert "text" in sample and sample["text"].strip()

    def test_approval_system_samples(self, system_corpus: dict) -> None:
        samples = system_corpus["systems"]["approval"]["samples"]
        expected_system = "approval"
        approval_keywords = ("审批", "OA", "审核", "申请", "approval", "approve")
        for sample in samples:
            assert sample["expected_system"] == expected_system
            text_lower = sample["text"].lower()
            has_keyword = any(k.lower() in text_lower for k in approval_keywords)
            assert has_keyword, f"Sample {sample['id']} missing approval keywords: {sample['text']}"

    def test_hr_system_samples(self, system_corpus: dict) -> None:
        samples = system_corpus["systems"]["hr"]["samples"]
        expected_system = "hr"
        for sample in samples:
            assert sample["expected_system"] == expected_system
            assert "text" in sample and sample["text"].strip()

    def test_asset_system_samples(self, system_corpus: dict) -> None:
        samples = system_corpus["systems"]["asset"]["samples"]
        expected_system = "asset"
        for sample in samples:
            assert sample["expected_system"] == expected_system
            assert "text" in sample and sample["text"].strip()

    def test_kb_system_samples(self, system_corpus: dict) -> None:
        samples = system_corpus["systems"]["kb"]["samples"]
        expected_system = "kb"
        for sample in samples:
            assert sample["expected_system"] == expected_system
            assert "text" in sample and sample["text"].strip()

    def test_crm_system_samples(self, system_corpus: dict) -> None:
        samples = system_corpus["systems"]["crm"]["samples"]
        expected_system = "crm"
        for sample in samples:
            assert sample["expected_system"] == expected_system
            assert "text" in sample and sample["text"].strip()

    def test_project_system_samples(self, system_corpus: dict) -> None:
        samples = system_corpus["systems"]["project"]["samples"]
        expected_system = "project"
        for sample in samples:
            assert sample["expected_system"] == expected_system
            assert "text" in sample and sample["text"].strip()

    def test_supply_chain_system_samples(self, system_corpus: dict) -> None:
        samples = system_corpus["systems"]["supply_chain"]["samples"]
        expected_system = "supply_chain"
        for sample in samples:
            assert sample["expected_system"] == expected_system
            assert "text" in sample and sample["text"].strip()

    def test_group_chat_ids_defined(self, system_corpus: dict) -> None:
        for system_key, system_data in system_corpus["systems"].items():
            assert "group_chat_id" in system_data, f"{system_key} missing group_chat_id"
            chat_id = system_data["group_chat_id"]
            assert chat_id.startswith("wrAEX9Rg"), (
                f"{system_key} has invalid group_chat_id: {chat_id}"
            )

    def test_all_samples_have_required_fields(self, system_corpus: dict) -> None:
        required_fields = {"id", "text", "expected_system", "expected_ticket_action"}
        for system_key, system_data in system_corpus["systems"].items():
            for sample in system_data["samples"]:
                missing = required_fields - set(sample.keys())
                assert not missing, (
                    f"{system_key}/{sample.get('id', 'unknown')}: missing fields {missing}"
                )


class TestSystemCorpusEndToEnd:
    """十系统端到端验证 - 使用 WeCom 桥接测试 system 分发"""

    def test_ticket_dispatch(
        self,
        tmp_path: Path,
        system_corpus: dict,
    ) -> None:
        from core.handoff_manager import HandoffManager
        from core.intent_router import IntentRouter
        from core.recommended_actions_engine import RecommendedActionsEngine
        from core.retriever import Retriever
        from core.sla_engine import SlaEngine
        from core.summary_engine import SummaryEngine
        from core.ticket_api import TicketAPI
        from core.tool_router import ToolRouter
        from core.workflow_engine import WorkflowEngine
        from storage.models import InboundEnvelope
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow
        from workflows.support_intake_workflow import SupportIntakeWorkflow

        repo = TicketRepository(tmp_path / "tickets.db")
        repo.apply_migrations()
        ticket_api = TicketAPI(repo)

        tool_router = ToolRouter(
            ticket_api=ticket_api,
            retriever=Retriever(Path(__file__).resolve().parents[2] / "seed_data"),
        )
        policy_path = (
            Path(__file__).resolve().parents[2]
            / "seed_data"
            / "sla_rules"
            / "default_sla_rules.json"
        )
        engine = WorkflowEngine(
            ticket_api=ticket_api,
            intent_router=IntentRouter(),
            tool_router=tool_router,
            summary_engine=SummaryEngine(),
            handoff_manager=HandoffManager.from_file(policy_path),
            sla_engine=SlaEngine.from_file(policy_path),
            recommendation_engine=RecommendedActionsEngine(),
        )
        workflow = SupportIntakeWorkflow(
            engine, case_collab_workflow=CaseCollabWorkflow(ticket_api)
        )

        sample = system_corpus["systems"]["ticket"]["samples"][0]
        envelope = InboundEnvelope(
            channel="wecom",
            session_id=f"test-{sample['id']}",
            message_text=sample["text"],
            metadata={"sender_id": "test_user"},
        )
        result = workflow.run(envelope)

        assert result.system == "ticket", f"Expected system=ticket, got {result.system}"

    def test_procurement_dispatch(
        self,
        tmp_path: Path,
        system_corpus: dict,
    ) -> None:
        from core.handoff_manager import HandoffManager
        from core.intent_router import IntentRouter
        from core.recommended_actions_engine import RecommendedActionsEngine
        from core.retriever import Retriever
        from core.sla_engine import SlaEngine
        from core.summary_engine import SummaryEngine
        from core.ticket_api import TicketAPI
        from core.tool_router import ToolRouter
        from core.workflow_engine import WorkflowEngine
        from storage.models import InboundEnvelope
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow
        from workflows.support_intake_workflow import SupportIntakeWorkflow

        repo = TicketRepository(tmp_path / "tickets.db")
        repo.apply_migrations()
        ticket_api = TicketAPI(repo)

        tool_router = ToolRouter(
            ticket_api=ticket_api,
            retriever=Retriever(Path(__file__).resolve().parents[2] / "seed_data"),
        )
        policy_path = (
            Path(__file__).resolve().parents[2]
            / "seed_data"
            / "sla_rules"
            / "default_sla_rules.json"
        )
        engine = WorkflowEngine(
            ticket_api=ticket_api,
            intent_router=IntentRouter(),
            tool_router=tool_router,
            summary_engine=SummaryEngine(),
            handoff_manager=HandoffManager.from_file(policy_path),
            sla_engine=SlaEngine.from_file(policy_path),
            recommendation_engine=RecommendedActionsEngine(),
        )
        workflow = SupportIntakeWorkflow(
            engine, case_collab_workflow=CaseCollabWorkflow(ticket_api)
        )

        sample = system_corpus["systems"]["procurement"]["samples"][0]
        envelope = InboundEnvelope(
            channel="wecom",
            session_id=f"test-{sample['id']}",
            message_text=sample["text"],
            metadata={"sender_id": "test_user"},
        )
        result = workflow.run(envelope)

        assert result.system == "procurement", f"Expected system=procurement, got {result.system}"

    def test_finance_dispatch(
        self,
        tmp_path: Path,
        system_corpus: dict,
    ) -> None:
        from core.handoff_manager import HandoffManager
        from core.intent_router import IntentRouter
        from core.recommended_actions_engine import RecommendedActionsEngine
        from core.retriever import Retriever
        from core.sla_engine import SlaEngine
        from core.summary_engine import SummaryEngine
        from core.ticket_api import TicketAPI
        from core.tool_router import ToolRouter
        from core.workflow_engine import WorkflowEngine
        from storage.models import InboundEnvelope
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow
        from workflows.support_intake_workflow import SupportIntakeWorkflow

        repo = TicketRepository(tmp_path / "tickets.db")
        repo.apply_migrations()
        ticket_api = TicketAPI(repo)

        tool_router = ToolRouter(
            ticket_api=ticket_api,
            retriever=Retriever(Path(__file__).resolve().parents[2] / "seed_data"),
        )
        policy_path = (
            Path(__file__).resolve().parents[2]
            / "seed_data"
            / "sla_rules"
            / "default_sla_rules.json"
        )
        engine = WorkflowEngine(
            ticket_api=ticket_api,
            intent_router=IntentRouter(),
            tool_router=tool_router,
            summary_engine=SummaryEngine(),
            handoff_manager=HandoffManager.from_file(policy_path),
            sla_engine=SlaEngine.from_file(policy_path),
            recommendation_engine=RecommendedActionsEngine(),
        )
        workflow = SupportIntakeWorkflow(
            engine, case_collab_workflow=CaseCollabWorkflow(ticket_api)
        )

        sample = system_corpus["systems"]["finance"]["samples"][0]
        envelope = InboundEnvelope(
            channel="wecom",
            session_id=f"test-{sample['id']}",
            message_text=sample["text"],
            metadata={"sender_id": "test_user"},
        )
        result = workflow.run(envelope)

        assert result.system == "finance", f"Expected system=finance, got {result.system}"

    def test_kb_faq_dispatch(
        self,
        tmp_path: Path,
        system_corpus: dict,
    ) -> None:
        from core.handoff_manager import HandoffManager
        from core.intent_router import IntentRouter
        from core.recommended_actions_engine import RecommendedActionsEngine
        from core.retriever import Retriever
        from core.sla_engine import SlaEngine
        from core.summary_engine import SummaryEngine
        from core.ticket_api import TicketAPI
        from core.tool_router import ToolRouter
        from core.workflow_engine import WorkflowEngine
        from storage.models import InboundEnvelope
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow
        from workflows.support_intake_workflow import SupportIntakeWorkflow

        repo = TicketRepository(tmp_path / "tickets.db")
        repo.apply_migrations()
        ticket_api = TicketAPI(repo)

        tool_router = ToolRouter(
            ticket_api=ticket_api,
            retriever=Retriever(Path(__file__).resolve().parents[2] / "seed_data"),
        )
        policy_path = (
            Path(__file__).resolve().parents[2]
            / "seed_data"
            / "sla_rules"
            / "default_sla_rules.json"
        )
        engine = WorkflowEngine(
            ticket_api=ticket_api,
            intent_router=IntentRouter(),
            tool_router=tool_router,
            summary_engine=SummaryEngine(),
            handoff_manager=HandoffManager.from_file(policy_path),
            sla_engine=SlaEngine.from_file(policy_path),
            recommendation_engine=RecommendedActionsEngine(),
        )
        workflow = SupportIntakeWorkflow(
            engine, case_collab_workflow=CaseCollabWorkflow(ticket_api)
        )

        sample = system_corpus["systems"]["kb"]["samples"][0]
        envelope = InboundEnvelope(
            channel="wecom",
            session_id=f"test-{sample['id']}",
            message_text=sample["text"],
            metadata={"sender_id": "test_user"},
        )
        result = workflow.run(envelope)

        assert result.system == "kb", f"Expected system=kb, got {result.system}"
