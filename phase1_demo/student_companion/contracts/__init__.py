"""Public versioned integration contract for Student Companion core."""

from .common import (
    CONTRACT_VERSION,
    ContractMetadata,
    ContractWarning,
    EvidenceReference,
    EvidenceSummary,
)
from .errors import ContractError, ContractExecutionError
from .requests import (
    FollowupEvaluationRequest,
    InitialAnalysisRequest,
    PlanGenerationRequest,
)
from .responses import (
    FollowupEvaluationResponse,
    InitialAnalysisResponse,
    PlanGenerationResponse,
)

__all__ = [
    "CONTRACT_VERSION",
    "ContractError",
    "ContractExecutionError",
    "ContractMetadata",
    "ContractWarning",
    "EvidenceReference",
    "EvidenceSummary",
    "FollowupEvaluationRequest",
    "FollowupEvaluationResponse",
    "InitialAnalysisRequest",
    "InitialAnalysisResponse",
    "PlanGenerationRequest",
    "PlanGenerationResponse",
]
