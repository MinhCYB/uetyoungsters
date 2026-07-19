"""Offline CLI demo for controlled Student Companion content generation."""

from __future__ import annotations

import argparse
import sys

from phase1_demo.student_companion.application.content_service import (
    ReassessmentSpecification,
    StudentCompanionContentService,
)
from phase1_demo.student_companion.application.service import DemoService
from phase1_demo.student_companion.llm.contracts import (
    CONTENT_CONTRACT_VERSION,
    ContentGenerationMetadata,
    FeedbackGenerationRequest,
)
from phase1_demo.student_companion.llm.orchestrator import (
    StudentCompanionContentOrchestrator,
)
from phase1_demo.student_companion.llm.prompts import (
    FEEDBACK_PROMPT_VERSION,
    PLAN_EXPANSION_PROMPT_VERSION,
    REASSESSMENT_PROMPT_VERSION,
)
from phase1_demo.student_companion.llm.providers import (
    ExistingProviderAdapter,
    FakeLLMProvider,
    TemplateProvider,
)


def _metadata(request_id: str, prompt_version: str, service: DemoService):
    return ContentGenerationMetadata(
        content_contract_version=CONTENT_CONTRACT_VERSION,
        request_id=request_id,
        prompt_version=prompt_version,
        student_id=service.initial.student.student_id,
        language="vi",
        grade_level=service.initial.student.grade_level,
    )


def run_demo(provider_name: str = "template", write=print) -> None:
    template = TemplateProvider()
    providers = {
        "template": template,
        "fake": FakeLLMProvider(delegate=template),
        "external": ExistingProviderAdapter(),
    }
    provider = providers[provider_name]
    orchestrator = StudentCompanionContentOrchestrator(provider, template)
    content_service = StudentCompanionContentService(orchestrator)

    engine = DemoService()
    engine.analyze_initial_state()
    engine.generate_weekly_plan()
    metadata_by_task = {
        task.task_id: _metadata(
            f"CONTENT_PLAN_{index + 1}", PLAN_EXPANSION_PROMPT_VERSION, engine
        )
        for index, task in enumerate(engine.plan_t0.tasks)
    }
    difficulty_by_task = {
        task.task_id: ("foundation" if task.skill_id else "standard")
        for task in engine.plan_t0.tasks
    }
    plans = content_service.expand_weekly_plan(
        engine.plan_t0,
        metadata_by_task=metadata_by_task,
        difficulty_by_task=difficulty_by_task,
        ability_profile=engine.ability_t0,
        gaps=engine.gaps_t0,
        prohibited_topics=["SQL", "Python", "portfolio"],
    )

    reassessment = content_service.generate_reassessment(
        metadata=_metadata("CONTENT_REASSESSMENT_001", REASSESSMENT_PROMPT_VERSION, engine),
        assessment_id="REASSESS_TRIG_V1",
        specification=ReassessmentSpecification(
            target_skill_id="SKILL_TRIG_TRANSFORMATION",
            question_count=5,
            difficulty="foundation",
            max_score=10,
            estimated_minutes=10,
            reassessment_after_days=14,
        ),
        allowed_question_types=["multiple_choice"],
        prior_question_fingerprints=[],
        learning_objective="Kiểm tra khả năng nhận diện và áp dụng biến đổi lượng giác.",
    )
    feedback = content_service.generate_feedback(
        FeedbackGenerationRequest(
            metadata=_metadata("CONTENT_FEEDBACK_001", FEEDBACK_PROMPT_VERSION, engine),
            question_id=reassessment.questions[0].question_id,
            skill_id="SKILL_TRIG_TRANSFORMATION",
            question_prompt=reassessment.questions[0].prompt,
            student_answer="sin(x)",
            expected_answer=reassessment.questions[0].correct_answer,
            is_correct=False,
            detected_error_type="dấu khi dịch góc",
            feedback_depth="explanation",
            max_followup_questions=1,
        )
    )

    write(f"Provider mode: {plans[0].result_metadata.content_mode}")
    write(f"Prompt version: {PLAN_EXPANSION_PROMPT_VERSION}")
    for plan in plans:
        write(f"Detailed plan: {plan.title} — {plan.total_minutes} phút, {len(plan.steps)} bước")
    write(
        f"Reassessment: {len(reassessment.questions)} câu, tổng {reassessment.total_score:g} điểm"
    )
    write(f"Feedback: {feedback.summary}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run offline LLM content orchestration demo")
    parser.add_argument(
        "--provider", choices=("template", "fake", "external"), default="template"
    )
    args = parser.parse_args(argv)
    run_demo(args.provider)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
