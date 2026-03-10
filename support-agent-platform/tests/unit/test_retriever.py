from __future__ import annotations

from pathlib import Path

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
