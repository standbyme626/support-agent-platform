from __future__ import annotations

from core.intent_router import IntentRouter


def test_intent_router_classifies_and_handles_low_confidence() -> None:
    router = IntentRouter(threshold=0.6)

    complaint = router.route("我要投诉你们的服务")
    assert complaint.intent == "complaint"
    assert complaint.is_low_confidence is False

    unknown = router.route("abc xyz 123")
    assert unknown.intent == "other"
    assert unknown.is_low_confidence is True
