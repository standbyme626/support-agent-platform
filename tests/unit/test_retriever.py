from __future__ import annotations

import json
from pathlib import Path

from core.retrieval.normalized_docs import load_normalized_documents
from core.retriever import Retriever


def test_retriever_returns_faq_and_sop_documents() -> None:
    seed_root = Path(__file__).resolve().parents[2] / "seed_data"
    retriever = Retriever(seed_root)

    faq_docs = retriever.search_faq("如何 查询 工单 进度", top_k=2)
    sop_docs = retriever.search_sop("投诉 升级 人工", top_k=2)

    assert faq_docs
    assert faq_docs[0].source_type == "faq"
    assert sop_docs
    assert sop_docs[0].source_type == "sop"


def test_retriever_grounded_prefers_history_cases() -> None:
    seed_root = Path(__file__).resolve().parents[2] / "seed_data"
    retriever = Retriever(seed_root)

    docs = retriever.search_grounded("支付 重复 扣费 退款", top_k=5)
    assert docs
    assert docs[0].source_type == "history_case"
    assert any(doc.source_type == "history_case" for doc in docs[:3])


def test_retriever_supports_vector_and_hybrid_modes() -> None:
    seed_root = Path(__file__).resolve().parents[2] / "seed_data"
    retriever = Retriever(seed_root)

    vector_docs = retriever.search_history("电梯停运无法启动", top_k=3, mode="vector")
    hybrid_docs = retriever.search_history("电梯停运无法启动", top_k=3, mode="hybrid")

    assert vector_docs
    assert hybrid_docs
    assert all(doc.source_type == "history_case" for doc in hybrid_docs)
    assert hybrid_docs[0].score >= 0


def test_normalized_documents_have_required_schema_fields() -> None:
    seed_root = Path(__file__).resolve().parents[2] / "seed_data"
    docs = load_normalized_documents(seed_root)

    assert docs
    sample = docs[0]
    assert sample.doc_id
    assert sample.source_type in {"faq", "sop", "history_case"}
    assert isinstance(sample.title, str)
    assert isinstance(sample.content, str)
    assert isinstance(sample.tags, tuple)
    assert sample.updated_at
    assert isinstance(sample.metadata, dict)


def test_load_normalized_documents_supports_multiple_seed_files(tmp_path: Path) -> None:
    seed_root = tmp_path / "seed_data"
    faq_dir = seed_root / "faq"
    sop_dir = seed_root / "sop"
    history_dir = seed_root / "historical_cases"
    faq_dir.mkdir(parents=True)
    sop_dir.mkdir(parents=True)
    history_dir.mkdir(parents=True)

    (faq_dir / "faq_documents.json").write_text(
        json.dumps(
            [
                {
                    "doc_id": "faq-main-1",
                    "source_type": "faq",
                    "title": "Main FAQ",
                    "content": "Main document",
                    "tags": ["main"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (faq_dir / "faq_external_documents.json").write_text(
        json.dumps(
            [
                {
                    "doc_id": "faq-ext-1",
                    "source_type": "faq",
                    "title": "External FAQ",
                    "content": "External document",
                    "tags": ["external"],
                    "metadata": {"source_dataset": "external_demo"},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sop_dir / "sop_documents.json").write_text("[]", encoding="utf-8")
    (history_dir / "history_documents.json").write_text("[]", encoding="utf-8")

    docs = load_normalized_documents(seed_root)
    faq_ids = {doc.doc_id for doc in docs if doc.source_type == "faq"}
    assert "faq-main-1" in faq_ids
    assert "faq-ext-1" in faq_ids

    external_doc = next(doc for doc in docs if doc.doc_id == "faq-ext-1")
    assert external_doc.metadata.get("source_dataset") == "external_demo"
    assert external_doc.metadata.get("source_file") == "faq_external_documents.json"
