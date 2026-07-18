"""Common public models for the Student Companion integration contract."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from phase1_demo.student_companion.domain.enums import EvidenceSourceType


CONTRACT_VERSION = "1.0.0"
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ContractModel(BaseModel):
    """Strict deterministic serialization policy for public contracts."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ContractMetadata(ContractModel):
    contract_version: Literal["1.0.0"]
    request_id: NonEmptyStr
    source_system: NonEmptyStr
    taxonomy_version: NonEmptyStr | None
    requested_at: datetime


class EvidenceReference(ContractModel):
    evidence_id: NonEmptyStr
    source_type: EvidenceSourceType
    source_reference: NonEmptyStr


class EvidenceSummary(ContractModel):
    source_type: EvidenceSourceType
    evidence_count: Annotated[int, Field(gt=0)]


class ContractWarning(ContractModel):
    warning_code: NonEmptyStr
    message: NonEmptyStr
    affected_field: NonEmptyStr | None

