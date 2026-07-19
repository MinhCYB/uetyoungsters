"""Profile-to-core orchestration for the Student Companion golden path."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from modules.candidate.analysis_contracts import (
    FollowupEvaluationRequest as ProfileFollowupRequest,
    InitialAnalysisRequest as ProfileInitialRequest,
    to_followup_evaluation_request,
    to_initial_analysis_request,
)
from phase1_demo.student_companion.application.facade import StudentCompanionFacade
from phase1_demo.student_companion.contracts import (
    CONTRACT_VERSION,
    ContractMetadata,
    FollowupEvaluationRequest,
    InitialAnalysisRequest,
    PlanGenerationRequest,
)
from phase1_demo.student_companion.domain import (
    AcademicRecord,
    ActivityResult,
    AssessmentAttempt,
    CareerClarity,
    SelfReport,
    SkillScore,
    StudentProfile,
    TeacherObservation,
)
from phase1_demo.student_companion.infrastructure.market import ReadOnlyMarketContextProvider
from phase1_demo.student_companion.llm.contracts import (
    CONTENT_CONTRACT_VERSION,
    ContentGenerationMetadata,
    FeedbackGenerationRequest,
    PlanExpansionRequest,
    ReassessmentGenerationRequest,
)
from phase1_demo.student_companion.llm.orchestrator import StudentCompanionContentOrchestrator
from phase1_demo.student_companion.llm.prompts import (
    FEEDBACK_PROMPT_VERSION,
    PLAN_EXPANSION_PROMPT_VERSION,
    REASSESSMENT_PROMPT_VERSION,
)
from phase1_demo.student_companion.llm.providers import (
    AIWorkerConfigurationError,
    AIWorkerConnectionError,
    AIWorkerEmptyResponseError,
    AIWorkerHTTPError,
    AIWorkerInvalidResponseError,
    AIWorkerProvider,
    AIWorkerTimeoutError,
    AIWorkerUnparsedResponseError,
    TemplateProvider,
)
from phase1_demo.student_companion.llm.validators import (
    LLMInvariantViolation,
    LLMOutputParseError,
    LLMOutputValidationError,
    LLMProviderError,
)

from .presentation import present_analysis, present_followup, present_plan
from .store import AnalysisRecord, CompanionStore, PlanRecord, companion_store


MODULE_PATH = Path(__file__).resolve()
REPOSITORY_ROOT = next(
    candidate
    for candidate in (MODULE_PATH.parents[3], MODULE_PATH.parents[2])
    if (candidate / "phase1_demo").is_dir()
)
PROFILE_FIXTURES = {
    "initial": REPOSITORY_ROOT / "tests" / "fixtures" / "student_profile_initial.json",
    "week3": REPOSITORY_ROOT / "tests" / "fixtures" / "student_profile_week3.json",
}
DEFAULT_CAREER_GROUPS = ["CAREER_GROUP_DATA_AI", "CAREER_GROUP_ECONOMICS"]
SKILL_MAP = {
    "skill_data_literacy": "SKILL_TRIG_TRANSFORMATION",
    "skill_problem_solving": "SKILL_LOGICAL_THINKING",
    "skill_communication": "SKILL_COMMUNICATION",
    "skill_collaboration": "SKILL_COMMUNICATION",
}
# Compatibility calibration for the existing 45-minute Engine V1 activity slot.
DATA_LITERACY_CALIBRATION = 3 / 11
ACADEMIC_DATA_CALIBRATION = 15 / 82


class CompanionError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _positive_env_number(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return -1


def _positive_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return -1


def _enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def build_content_orchestrator() -> StudentCompanionContentOrchestrator:
    mode = os.getenv("COMPANION_LLM_MODE", "live").strip().casefold()
    if mode == "template":
        return StudentCompanionContentOrchestrator(TemplateProvider())
    if mode != "live":
        raise RuntimeError("COMPANION_LLM_MODE must be 'live' or 'template'")
    provider = AIWorkerProvider(
        base_url=os.getenv("AI_WORKER_URL", ""),
        timeout_seconds=_positive_env_number("AI_WORKER_TIMEOUT_SECONDS", 30),
        max_tokens=_positive_env_int("COMPANION_LLM_MAX_TOKENS", 2048),
    )
    return StudentCompanionContentOrchestrator(
        provider,
        TemplateProvider(),
        allow_fallback=_enabled("COMPANION_LLM_FALLBACK_ENABLED"),
    )


def _token(prefix: str, *parts: object) -> str:
    raw = "|".join(str(item) for item in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _read_fixture(selector: str) -> dict:
    return json.loads(PROFILE_FIXTURES[selector].read_text(encoding="utf-8"))


def _career_groups(profile) -> list[str]:
    values: list[str] = []
    if profile.self_report:
        source = [*profile.self_report.preferred_career_ids, *profile.self_report.interest_ids]
        for value in source:
            mapped = None
            if "data" in value or "technology" in value:
                mapped = "CAREER_GROUP_DATA_AI"
            elif "business" in value or "economic" in value:
                mapped = "CAREER_GROUP_ECONOMICS"
            if mapped and mapped not in values:
                values.append(mapped)
    return values or list(DEFAULT_CAREER_GROUPS)


def _student(profile) -> StudentProfile:
    grade = int(profile.student.grade_level or 11)
    interests = _career_groups(profile)
    weekly_minutes = 45
    return StudentProfile(
        student_id=profile.student.student_id,
        display_name=profile.student.display_name,
        grade_level=max(10, min(12, grade)),
        weekly_available_minutes=weekly_minutes,
        career_interest_ids=interests,
        career_clarity=CareerClarity.EXPLORING if len(interests) > 1 else CareerClarity.NARROWING,
        exam_week=False,
        schema_version=profile.schema_version,
    )


def _skill_score(item) -> SkillScore:
    skill_id = SKILL_MAP.get(item.skill_id, item.skill_id.upper())
    score = item.score
    if item.skill_id == "skill_data_literacy":
        score = score * DATA_LITERACY_CALIBRATION
    return SkillScore(skill_id=skill_id, score=score, max_score=item.max_score)


def _assessments(profile) -> list[AssessmentAttempt]:
    return [AssessmentAttempt(
        attempt_id=item.attempt_id,
        student_id=item.student_id,
        assessment_id="ASSESSMENT_FOUNDATION_MATH" if "data_literacy" in item.assessment_id else item.assessment_id.upper(),
        assessment_type=item.purpose.value,
        skill_scores=[_skill_score(score) for score in item.skill_scores],
        completed_at=item.submitted_at or item.started_at,
        assessment_version=profile.schema_version,
        schema_version=profile.schema_version,
    ) for item in profile.assessment_attempts]


def _academic_records(profile) -> list[AcademicRecord]:
    return [AcademicRecord(
        record_id=item.record_id,
        student_id=item.student_id,
        subject_id=item.subject_id.upper(),
        topic_id="SKILL_TRIG_TRANSFORMATION" if "math" in item.subject_id else item.subject_id.upper(),
        score=item.score * ACADEMIC_DATA_CALIBRATION if "math" in item.subject_id else item.score,
        max_score=float(item.score_scale),
        observed_at=item.recorded_at,
        source=item.source,
        schema_version=profile.schema_version,
    ) for item in profile.academic_records]


def _observations(profile) -> list[TeacherObservation]:
    result = []
    for observation in profile.teacher_observations:
        for index, source_skill in enumerate(observation.skill_ids):
            result.append(TeacherObservation(
                observation_id=f"{observation.observation_id}_{index + 1}",
                student_id=observation.student_id,
                skill_id=SKILL_MAP.get(source_skill, source_skill.upper()),
                observation_type="strength",
                severity="medium",
                confidence=0.75,
                note=observation.observation,
                observed_at=observation.observed_at,
                schema_version=profile.schema_version,
            ))
    return result


def _self_report(profile) -> SelfReport | None:
    item = profile.self_report
    if item is None:
        return None
    groups = _career_groups(profile)
    return SelfReport(
        report_id=_token("SELF_REPORT", profile.student.student_id, item.submitted_at.isoformat()),
        student_id=profile.student.student_id,
        career_interests=[{"career_group_id": group, "interest_score": 3.0, "max_score": 5.0} for group in groups],
        preferred_task_types=[],
        stated_strength_skill_ids=[],
        stated_weakness_skill_ids=[],
        note=item.free_text,
        observed_at=item.submitted_at,
        schema_version=profile.schema_version,
    )


def _activities(profile) -> list[ActivityResult]:
    return [ActivityResult(
        activity_result_id=item.activity_result_id,
        activity_id="ACTIVITY_DATA_INSIGHTS",
        student_id=item.student_id,
        career_group_id="CAREER_GROUP_DATA_AI",
        completed=True,
        rubric_score=item.score,
        max_score=item.max_score,
        interest_before=3.0,
        interest_after=4.0,
        interest_max_score=5.0,
        preferred_part=item.evidence,
        completed_at=item.completed_at,
        activity_version=profile.schema_version,
        schema_version=profile.schema_version,
    ) for item in profile.activity_results]


def map_initial_profile(request: ProfileInitialRequest) -> InitialAnalysisRequest:
    profile = request.profile
    return InitialAnalysisRequest(
        metadata=ContractMetadata(contract_version=CONTRACT_VERSION, request_id=request.request_id, source_system="backend.profile_contract", taxonomy_version=f"profile-v{profile.profile_version}", requested_at=request.requested_at),
        student=_student(profile),
        academic_records=_academic_records(profile),
        teacher_observations=_observations(profile),
        assessment_attempts=_assessments(profile),
        self_report=_self_report(profile),
        prior_activity_results=_activities(profile),
    )


def map_followup_profile(request: ProfileFollowupRequest, previous_snapshot) -> FollowupEvaluationRequest:
    profile = request.profile
    return FollowupEvaluationRequest(
        metadata=ContractMetadata(contract_version=CONTRACT_VERSION, request_id=request.request_id, source_system="backend.profile_contract", taxonomy_version=f"profile-v{profile.profile_version}", requested_at=request.requested_at),
        student=_student(profile),
        previous_snapshot=previous_snapshot,
        assessment_attempts=_assessments(profile),
        activity_results=_activities(profile),
    )


class CompanionService:
    def __init__(
        self,
        store: CompanionStore = companion_store,
        content: StudentCompanionContentOrchestrator | None = None,
    ) -> None:
        self.store = store
        self.facade = StudentCompanionFacade(ReadOnlyMarketContextProvider())
        self.content = content or build_content_orchestrator()

    def analyze(self, *, student_id: str, profile_version: int, fixture_selector: str) -> dict:
        payload = _read_fixture(fixture_selector)
        if payload["student"]["student_id"] != student_id or payload["profile_version"] != profile_version:
            raise CompanionError("contract_validation_failed", "Student or profile version does not match the selected profile.", 422)
        request_id = _token("iar", student_id, profile_version).lower()
        profile_request = to_initial_analysis_request(payload, request_id=request_id, requested_at=payload_datetime(payload))
        core_request = map_initial_profile(profile_request)
        response = self.facade.analyze(core_request)
        analysis_id = _token("ANALYSIS", student_id, profile_version, response.snapshot.snapshot_id)
        record = AnalysisRecord(analysis_id, profile_version, core_request.student.display_name, core_request, response)
        self.store.save_analysis(record)
        return present_analysis(response, analysis_id=analysis_id, profile_version=profile_version, display_name=record.display_name)

    def generate_plan(self, analysis_id: str) -> dict:
        analysis = self.store.get_analysis(analysis_id)
        if analysis is None:
            raise CompanionError("analysis_not_found", "Run analysis before generating a plan.", 404)
        request = PlanGenerationRequest(
            metadata=ContractMetadata(contract_version=CONTRACT_VERSION, request_id=_token("PLAN_REQUEST", analysis_id), source_system="backend.companion", taxonomy_version=f"profile-v{analysis.profile_version}", requested_at=analysis.core_response.snapshot.created_at),
            student=analysis.core_request.student,
            snapshot=analysis.core_response.snapshot,
            completed_activity_ids=[],
        )
        response = self.facade.generate_plan(request)
        self.store.save_plan(PlanRecord(response.plan.plan_id, analysis_id, response))
        return present_plan(response, analysis_id=analysis_id, display_name=analysis.display_name)

    def followup(self, *, baseline_analysis_id: str, student_id: str, profile_version: int, fixture_selector: str) -> dict:
        baseline = self.store.get_analysis(baseline_analysis_id)
        if baseline is None:
            raise CompanionError("baseline_not_found", "A baseline analysis is required for follow-up.", 404)
        payload = _read_fixture(fixture_selector)
        if payload["student"]["student_id"] != student_id or payload["profile_version"] != profile_version:
            raise CompanionError("contract_validation_failed", "Student or profile version does not match the selected profile.", 422)
        if student_id != baseline.core_request.student.student_id or profile_version <= baseline.profile_version:
            raise CompanionError("invalid_transition", "Follow-up must use a newer profile for the same student.")
        requested_at = payload_datetime(payload)
        profile_request = to_followup_evaluation_request(payload, request_id=_token("fer", student_id, profile_version).lower(), requested_at=requested_at, baseline_analysis_id=baseline_analysis_id, window_started_at=baseline.core_response.snapshot.created_at, window_ended_at=requested_at)
        response = self.facade.evaluate_followup(map_followup_profile(profile_request, baseline.core_response.snapshot))
        return present_followup(response, baseline_analysis_id=baseline_analysis_id, profile_version=profile_version, display_name=baseline.display_name)

    def expand_plan(self, plan_id: str, task_id: str, max_steps: int) -> dict:
        plan_record = self.store.get_plan(plan_id)
        if plan_record is None:
            raise CompanionError("plan_not_found", "Generate a plan before expanding a task.", 404)
        task = next((item for item in plan_record.core_response.plan.tasks if item.task_id == task_id), None)
        if task is None:
            raise CompanionError("invalid_transition", "The selected task does not belong to this plan.")
        metadata = self._content_metadata(_token("CONTENT_REQUEST", plan_id, task_id), task.skill_id or task.career_group_id or "task", PLAN_EXPANSION_PROMPT_VERSION, plan_record)
        result = self._generate_content(lambda: self.content.expand_plan(PlanExpansionRequest(metadata=metadata, task=task, relevant_ability=None, relevant_gap=None, student_preferences=[], prohibited_topics=[], max_steps=max_steps, difficulty="foundation")))
        return result.model_dump(mode="json")

    def reassessment(self, plan_id: str, target_skill_id: str, question_count: int, max_score: float) -> dict:
        plan_record = self._require_plan(plan_id)
        metadata = self._content_metadata(_token("REASSESS_REQUEST", plan_id, target_skill_id), target_skill_id, REASSESSMENT_PROMPT_VERSION, plan_record)
        request = ReassessmentGenerationRequest(metadata=metadata, assessment_id=_token("REASSESSMENT", plan_id, target_skill_id), target_skill_id=target_skill_id, question_count=question_count, difficulty="foundation", max_score=max_score, estimated_minutes=question_count * 2, allowed_question_types=["multiple_choice"], prior_question_fingerprints=[], learning_objective="Kiểm tra lại kỹ năng mục tiêu sau hoạt động.")
        return self._generate_content(lambda: self.content.generate_reassessment(request)).model_dump(mode="json")

    def feedback(self, payload) -> dict:
        metadata = ContentGenerationMetadata(content_contract_version=CONTENT_CONTRACT_VERSION, request_id=_token("FEEDBACK_REQUEST", payload.question_id, payload.student_id), prompt_version=FEEDBACK_PROMPT_VERSION, student_id=payload.student_id, language="vi", grade_level=12)
        request = FeedbackGenerationRequest(metadata=metadata, question_id=payload.question_id, skill_id=payload.skill_id, question_prompt=payload.question_prompt, student_answer=payload.student_answer, expected_answer=payload.expected_answer, is_correct=payload.is_correct, detected_error_type=payload.detected_error_type, feedback_depth="explanation", max_followup_questions=1)
        result = self._generate_content(lambda: self.content.generate_feedback(request)).model_dump(mode="json")
        result["graded_answer"] = {"is_correct": payload.is_correct}
        return result

    @staticmethod
    def _generate_content(operation):
        try:
            return operation()
        except AIWorkerConfigurationError as exc:
            raise CompanionError("llm_configuration_missing", "Live content generation is not configured.", 503) from exc
        except AIWorkerConnectionError as exc:
            raise CompanionError("ai_worker_unreachable", "The content generation service is unavailable.", 503) from exc
        except AIWorkerTimeoutError as exc:
            raise CompanionError("ai_worker_timeout", "The content generation request timed out.", 504) from exc
        except AIWorkerHTTPError as exc:
            raise CompanionError("ai_worker_http_error", "The content generation service returned an error.", 502) from exc
        except AIWorkerUnparsedResponseError as exc:
            raise CompanionError("ai_worker_unparsed_response", "The content generation service returned invalid JSON.", 502) from exc
        except AIWorkerEmptyResponseError as exc:
            raise CompanionError("ai_worker_empty_response", "The content generation service returned no content.", 502) from exc
        except AIWorkerInvalidResponseError as exc:
            raise CompanionError("ai_worker_invalid_response", "The content generation service returned an invalid response.", 502) from exc
        except LLMOutputParseError as exc:
            raise CompanionError("llm_output_invalid_json", "Generated content was not valid JSON.", 502) from exc
        except LLMOutputValidationError as exc:
            raise CompanionError("llm_output_schema_invalid", "Generated content did not satisfy the required schema.", 502) from exc
        except LLMInvariantViolation as exc:
            raise CompanionError("llm_output_rejected", "Generated content did not satisfy safety constraints.", 502) from exc
        except LLMProviderError as exc:
            raise CompanionError("llm_provider_failed", "Content generation failed.", 502) from exc

    def _require_plan(self, plan_id: str) -> PlanRecord:
        record = self.store.get_plan(plan_id)
        if record is None:
            raise CompanionError("plan_not_found", "Generate a plan first.", 404)
        return record

    def _content_metadata(self, request_id: str, subject: str, prompt_version: str, plan: PlanRecord) -> ContentGenerationMetadata:
        analysis = self.store.get_analysis(plan.analysis_id)
        if analysis is None:
            raise CompanionError("analysis_not_found", "The plan baseline is unavailable.", 404)
        return ContentGenerationMetadata(content_contract_version=CONTENT_CONTRACT_VERSION, request_id=request_id, prompt_version=prompt_version, student_id=analysis.core_request.student.student_id, language="vi", grade_level=analysis.core_request.student.grade_level)


def payload_datetime(payload: dict):
    from datetime import datetime
    return datetime.fromisoformat(payload["generated_at"].replace("Z", "+00:00"))


companion_service = CompanionService()
