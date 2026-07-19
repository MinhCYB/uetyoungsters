"""Structured public errors raised by contract-facing operations."""

from __future__ import annotations

from phase1_demo.student_companion.contracts.common import ContractModel, NonEmptyStr


class ContractError(ContractModel):
    error_code: NonEmptyStr
    message: NonEmptyStr
    field_path: NonEmptyStr | None
    recoverable: bool


class ContractExecutionError(RuntimeError):
    """Exception wrapper carrying a serializable :class:`ContractError`."""

    def __init__(self, error: ContractError) -> None:
        super().__init__(error.message)
        self.error = error

