from __future__ import annotations

from datetime import datetime, timezone

from phase1_demo.student_companion.domain import PlanTask, WeeklyPlan
from phase1_demo.student_companion.llm.contracts import (
    CONTENT_CONTRACT_VERSION,
    ContentGenerationMetadata,
    FeedbackGenerationRequest,
    PlanExpansionRequest,
    ReassessmentGenerationRequest,
)
from phase1_demo.student_companion.llm.prompts import (
    FEEDBACK_PROMPT_VERSION,
    PLAN_EXPANSION_PROMPT_VERSION,
    REASSESSMENT_PROMPT_VERSION,
    build_feedback_prompts,
    build_plan_prompts,
    build_reassessment_prompts,
)
from phase1_demo.student_companion.llm.providers import TemplateProvider


def metadata(prompt_version: str, request_id: str = "CONTENT_REQUEST_001"):
    return ContentGenerationMetadata(
        content_contract_version=CONTENT_CONTRACT_VERSION,
        request_id=request_id,
        prompt_version=prompt_version,
        student_id="STUDENT_001",
        language="vi",
        grade_level=11,
    )


def academic_task(minutes: int = 20) -> PlanTask:
    return PlanTask(
        task_id="TASK_TRIG_001",
        task_type="academic_practice",
        title="Luyện biến đổi lượng giác",
        skill_id="SKILL_TRIG_TRANSFORMATION",
        career_group_id=None,
        estimated_minutes=minutes,
        reason="Cần củng cố nội dung nền tảng.",
        evidence_ids=["EVIDENCE_PRIVATE_001"],
        activity_version="activity-catalog-1.0.0",
    )


def career_task() -> PlanTask:
    return PlanTask(
        task_id="TASK_DATA_001",
        task_type="career_micro_experience",
        title="Phân tích bảng khảo sát và tìm ba insight",
        skill_id=None,
        career_group_id="CAREER_GROUP_DATA_AI",
        estimated_minutes=25,
        reason="Cần thêm trải nghiệm thực hành.",
        evidence_ids=[],
        activity_version="activity-catalog-1.0.0",
    )


def weekly_plan() -> WeeklyPlan:
    return WeeklyPlan(
        plan_id="PLAN_001",
        student_id="STUDENT_001",
        weekly_budget_minutes=45,
        total_planned_minutes=45,
        tasks=[academic_task(), career_task()],
        generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        rule_version="phase1-rules-1.0.0",
    )


def plan_request(**updates) -> PlanExpansionRequest:
    values = {
        "metadata": metadata(PLAN_EXPANSION_PROMPT_VERSION),
        "task": academic_task(),
        "relevant_ability": None,
        "relevant_gap": None,
        "student_preferences": ["ví dụ ngắn"],
        "prohibited_topics": ["SQL", "Python", "portfolio"],
        "max_steps": 4,
        "difficulty": "foundation",
    }
    values.update(updates)
    return PlanExpansionRequest(**values)


def reassessment_request(**updates) -> ReassessmentGenerationRequest:
    values = {
        "metadata": metadata(REASSESSMENT_PROMPT_VERSION, "REASSESS_REQUEST_001"),
        "assessment_id": "REASSESS_TRIG_001",
        "target_skill_id": "SKILL_TRIG_TRANSFORMATION",
        "question_count": 5,
        "difficulty": "foundation",
        "max_score": 10.0,
        "estimated_minutes": 10,
        "allowed_question_types": ["multiple_choice"],
        "prior_question_fingerprints": [],
        "learning_objective": "Nhận diện và áp dụng biến đổi lượng giác.",
    }
    values.update(updates)
    return ReassessmentGenerationRequest(**values)


def feedback_request(**updates) -> FeedbackGenerationRequest:
    values = {
        "metadata": metadata(FEEDBACK_PROMPT_VERSION, "FEEDBACK_REQUEST_001"),
        "question_id": "QUESTION_001",
        "skill_id": "SKILL_TRIG_TRANSFORMATION",
        "question_prompt": "Biểu thức nào bằng sin(x + π)?",
        "student_answer": "sin(x)",
        "expected_answer": "-sin(x)",
        "is_correct": False,
        "detected_error_type": "dấu khi dịch góc",
        "feedback_depth": "explanation",
        "max_followup_questions": 1,
    }
    values.update(updates)
    return FeedbackGenerationRequest(**values)


def template_raw(request) -> dict:
    provider = TemplateProvider()
    if isinstance(request, PlanExpansionRequest):
        system, user = build_plan_prompts(request)
        schema = "DetailedLearningPlan"
    elif isinstance(request, ReassessmentGenerationRequest):
        system, user = build_reassessment_prompts(request)
        schema = "ReassessmentPackage"
    else:
        system, user = build_feedback_prompts(request)
        schema = "PersonalizedFeedback"
    return provider.generate_structured(
        system_prompt=system,
        user_prompt=user,
        schema_name=schema,
    )
