"""Application helpers connecting immutable engine outputs to content requests."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from phase1_demo.student_companion.domain import AbilityEstimate, Gap, WeeklyPlan
from phase1_demo.student_companion.llm.contracts import (
    ContentGenerationMetadata,
    DetailedLearningPlan,
    Difficulty,
    FeedbackGenerationRequest,
    PersonalizedFeedback,
    PlanExpansionRequest,
    ReassessmentGenerationRequest,
    ReassessmentPackage,
)
from phase1_demo.student_companion.llm.orchestrator import (
    StudentCompanionContentOrchestrator,
)


class ReassessmentSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    target_skill_id: Annotated[str, Field(min_length=1)]
    question_count: Annotated[int, Field(ge=3, le=10)]
    difficulty: Difficulty
    max_score: Annotated[float, Field(gt=0)]
    estimated_minutes: Annotated[int, Field(gt=0)]
    reassessment_after_days: Annotated[int, Field(gt=0)]


class StudentCompanionContentService:
    def __init__(self, orchestrator: StudentCompanionContentOrchestrator) -> None:
        self._orchestrator = orchestrator

    def expand_weekly_plan(
        self,
        plan: WeeklyPlan,
        *,
        metadata_by_task: dict[str, ContentGenerationMetadata],
        difficulty_by_task: dict[str, Difficulty],
        ability_profile: list[AbilityEstimate] | tuple[AbilityEstimate, ...] = (),
        gaps: list[Gap] | tuple[Gap, ...] = (),
        student_preferences: list[str] | tuple[str, ...] = (),
        prohibited_topics: list[str] | tuple[str, ...] = (),
        max_steps: int = 4,
    ) -> list[DetailedLearningPlan]:
        ability_by_skill = {item.skill_id: item for item in ability_profile}
        results: list[DetailedLearningPlan] = []
        for task in plan.tasks:
            if task.task_id not in metadata_by_task or task.task_id not in difficulty_by_task:
                raise ValueError("every plan task requires caller-owned metadata and difficulty")
            metadata = metadata_by_task[task.task_id]
            if metadata.student_id != plan.student_id:
                raise ValueError("content metadata student_id must match plan.student_id")
            relevant_gap = next(
                (
                    item
                    for item in gaps
                    if (task.skill_id and item.skill_id == task.skill_id)
                    or (
                        task.career_group_id
                        and task.career_group_id in item.career_group_ids
                    )
                ),
                None,
            )
            request = PlanExpansionRequest(
                metadata=metadata,
                task=task,
                relevant_ability=ability_by_skill.get(task.skill_id or ""),
                relevant_gap=relevant_gap,
                student_preferences=list(student_preferences),
                prohibited_topics=list(prohibited_topics),
                max_steps=max_steps,
                difficulty=difficulty_by_task[task.task_id],
            )
            results.append(self._orchestrator.expand_plan(request))
        return results

    def generate_reassessment(
        self,
        *,
        metadata: ContentGenerationMetadata,
        assessment_id: str,
        specification: ReassessmentSpecification,
        allowed_question_types: list[str],
        prior_question_fingerprints: list[str],
        learning_objective: str,
    ) -> ReassessmentPackage:
        request = ReassessmentGenerationRequest(
            metadata=metadata,
            assessment_id=assessment_id,
            target_skill_id=specification.target_skill_id,
            question_count=specification.question_count,
            difficulty=specification.difficulty,
            max_score=specification.max_score,
            estimated_minutes=specification.estimated_minutes,
            allowed_question_types=allowed_question_types,
            prior_question_fingerprints=prior_question_fingerprints,
            learning_objective=learning_objective,
        )
        return self._orchestrator.generate_reassessment(request)

    def generate_feedback(
        self,
        request: FeedbackGenerationRequest,
    ) -> PersonalizedFeedback:
        return self._orchestrator.generate_feedback(request)
