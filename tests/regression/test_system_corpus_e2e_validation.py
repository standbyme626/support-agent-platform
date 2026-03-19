from __future__ import annotations

import json
from pathlib import Path

import pytest

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


class TestSystemCorpusE2EValidation:
    """十系统端到端验证 - 验证 system 推断准确性"""

    def test_ticket_system_dispatch(
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
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow

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

        samples = system_corpus["systems"]["ticket"]["samples"][:3]
        for sample in samples:
            envelope = InboundEnvelope(
                channel="wecom",
                session_id=f"test-{sample['id']}",
                message_text=sample["text"],
                metadata={"sender_id": "test_user"},
            )
            result = workflow.run(envelope)
            assert result.system == "ticket", (
                f"Sample {sample['id']}: expected system=ticket, got {result.system}"
            )

    def test_procurement_system_dispatch(
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
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow

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

        samples = system_corpus["systems"]["procurement"]["samples"][:3]
        for sample in samples:
            envelope = InboundEnvelope(
                channel="wecom",
                session_id=f"test-{sample['id']}",
                message_text=sample["text"],
                metadata={"sender_id": "test_user"},
            )
            result = workflow.run(envelope)
            assert result.system == "procurement", (
                f"Sample {sample['id']}: expected system=procurement, got {result.system}"
            )

    def test_finance_system_dispatch(
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
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow

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

        samples = system_corpus["systems"]["finance"]["samples"][:3]
        for sample in samples:
            envelope = InboundEnvelope(
                channel="wecom",
                session_id=f"test-{sample['id']}",
                message_text=sample["text"],
                metadata={"sender_id": "test_user"},
            )
            result = workflow.run(envelope)
            assert result.system == "finance", (
                f"Sample {sample['id']}: expected system=finance, got {result.system}"
            )

    def test_approval_system_dispatch(
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
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow

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

        samples = system_corpus["systems"]["approval"]["samples"][:3]
        for sample in samples:
            envelope = InboundEnvelope(
                channel="wecom",
                session_id=f"test-{sample['id']}",
                message_text=sample["text"],
                metadata={"sender_id": "test_user"},
            )
            result = workflow.run(envelope)
            assert result.system == "approval", (
                f"Sample {sample['id']}: expected system=approval, got {result.system}"
            )

    def test_hr_system_dispatch(
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
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow

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

        samples = system_corpus["systems"]["hr"]["samples"][:3]
        for sample in samples:
            envelope = InboundEnvelope(
                channel="wecom",
                session_id=f"test-{sample['id']}",
                message_text=sample["text"],
                metadata={"sender_id": "test_user"},
            )
            result = workflow.run(envelope)
            assert result.system == "hr", (
                f"Sample {sample['id']}: expected system=hr, got {result.system}"
            )

    def test_kb_system_dispatch(
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
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow

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

        samples = system_corpus["systems"]["kb"]["samples"][:3]
        for sample in samples:
            envelope = InboundEnvelope(
                channel="wecom",
                session_id=f"test-{sample['id']}",
                message_text=sample["text"],
                metadata={"sender_id": "test_user"},
            )
            result = workflow.run(envelope)
            assert result.system == "kb", (
                f"Sample {sample['id']}: expected system=kb, got {result.system}"
            )

    def test_crm_system_dispatch(
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
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow

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

        samples = system_corpus["systems"]["crm"]["samples"][:3]
        for sample in samples:
            envelope = InboundEnvelope(
                channel="wecom",
                session_id=f"test-{sample['id']}",
                message_text=sample["text"],
                metadata={"sender_id": "test_user"},
            )
            result = workflow.run(envelope)
            assert result.system == "crm", (
                f"Sample {sample['id']}: expected system=crm, got {result.system}"
            )

    def test_project_system_dispatch(
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
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow

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

        samples = system_corpus["systems"]["project"]["samples"][:3]
        for sample in samples:
            envelope = InboundEnvelope(
                channel="wecom",
                session_id=f"test-{sample['id']}",
                message_text=sample["text"],
                metadata={"sender_id": "test_user"},
            )
            result = workflow.run(envelope)
            assert result.system == "project", (
                f"Sample {sample['id']}: expected system=project, got {result.system}"
            )

    def test_supply_chain_system_dispatch(
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
        from storage.ticket_repository import TicketRepository
        from workflows.case_collab_workflow import CaseCollabWorkflow

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

        samples = system_corpus["systems"]["supply_chain"]["samples"][:3]
        for sample in samples:
            envelope = InboundEnvelope(
                channel="wecom",
                session_id=f"test-{sample['id']}",
                message_text=sample["text"],
                metadata={"sender_id": "test_user"},
            )
            result = workflow.run(envelope)
            assert result.system == "supply_chain", (
                f"Sample {sample['id']}: expected system=supply_chain, got {result.system}"
            )
