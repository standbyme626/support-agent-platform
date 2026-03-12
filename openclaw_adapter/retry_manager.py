from __future__ import annotations

from dataclasses import dataclass

from channel_adapters.base import ChannelAdapterError

_TEMPORARY_ERROR_CODES = (
    "timeout",
    "temporary",
    "network",
    "rate_limit",
    "busy",
)


@dataclass(frozen=True)
class RetryDecision:
    attempt: int
    max_attempts: int
    classification: str
    should_retry: bool
    exhausted: bool
    error_code: str
    error_message: str

    def to_payload(self) -> dict[str, object]:
        return {
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "classification": self.classification,
            "should_retry": self.should_retry,
            "exhausted": self.exhausted,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class RetryManager:
    """Classify outbound failures and decide retry behavior."""

    def decide(
        self,
        *,
        error: ChannelAdapterError,
        attempt: int,
        max_attempts: int,
    ) -> RetryDecision:
        classification = self._classify(error)
        should_retry = classification == "temporary" and attempt < max_attempts
        return RetryDecision(
            attempt=attempt,
            max_attempts=max_attempts,
            classification=classification,
            should_retry=should_retry,
            exhausted=not should_retry,
            error_code=error.code,
            error_message=str(error),
        )

    @staticmethod
    def _classify(error: ChannelAdapterError) -> str:
        code = error.code.lower()
        if error.retryable:
            return "temporary"
        if any(fragment in code for fragment in _TEMPORARY_ERROR_CODES):
            return "temporary"
        return "permanent"
