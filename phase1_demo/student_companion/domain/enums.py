"""Stable vocabulary used by the Phase 1 domain contracts."""

from enum import Enum


class CareerClarity(str, Enum):
    EXPLORING = "exploring"
    NARROWING = "narrowing"
    DECIDED = "decided"


class EvidenceSourceType(str, Enum):
    ACADEMIC_RECORD = "academic_record"
    TEACHER_OBSERVATION = "teacher_observation"
    ASSESSMENT = "assessment"
    SELF_REPORT = "self_report"
    ACTIVITY_RESULT = "activity_result"


class ObservationType(str, Enum):
    STRENGTH = "strength"
    WEAKNESS = "weakness"
    NEUTRAL = "neutral"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AssessmentType(str, Enum):
    DIAGNOSTIC = "diagnostic"
    PRETEST = "pretest"
    POSTTEST = "posttest"


class GapType(str, Enum):
    ACADEMIC = "academic"
    EXPLORATION = "exploration"
    DECISION = "decision"


class GapPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AbilityTrend(str, Enum):
    UNKNOWN = "unknown"
    STABLE = "stable"
    IMPROVING = "improving"
    DECLINING = "declining"


class TaskType(str, Enum):
    ACADEMIC_PRACTICE = "academic_practice"
    CAREER_MICRO_EXPERIENCE = "career_micro_experience"
    REFLECTION = "reflection"
    REASSESSMENT = "reassessment"


class OutcomeStatus(str, Enum):
    MEANINGFUL_IMPROVEMENT = "meaningful_improvement"
    PARTIAL_IMPROVEMENT = "partial_improvement"
    NO_MEANINGFUL_CHANGE = "no_meaningful_change"
    REGRESSION = "regression"


class CareerExplorationStatus(str, Enum):
    NOT_STARTED = "not_started"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    IN_PROGRESS = "in_progress"
    EXPLORED = "explored"

