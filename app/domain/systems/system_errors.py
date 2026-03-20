from __future__ import annotations


class SystemError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        retryable: bool = False,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }


class ValidationError(SystemError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__("validation_error", message, retryable=False, details=details)


class EntityNotFoundError(SystemError):
    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            "entity_not_found",
            f"{entity_type} {entity_id} not found",
            retryable=False,
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


class InvalidStateTransitionError(SystemError):
    def __init__(
        self,
        current_status: str,
        action: str,
        allowed_from: list[str],
    ) -> None:
        super().__init__(
            "invalid_state_transition",
            f"Cannot perform {action} from status {current_status}",
            retryable=False,
            details={
                "current_status": current_status,
                "action": action,
                "allowed_from": allowed_from,
            },
        )


class ForbiddenActionError(SystemError):
    def __init__(self, action: str, reason: str) -> None:
        super().__init__(
            "forbidden_action",
            f"Action {action} is forbidden: {reason}",
            retryable=False,
            details={"action": action, "reason": reason},
        )


class DuplicateRequestError(SystemError):
    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            "duplicate_request",
            f"Duplicate request for {entity_type} {entity_id}",
            retryable=True,
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


class InternalError(SystemError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__("internal_error", message, retryable=False, details=details)
