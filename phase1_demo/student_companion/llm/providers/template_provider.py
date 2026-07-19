"""Offline deterministic provider backed by safe templates."""

from __future__ import annotations

import json

from ..fallback_templates import (
    build_feedback_template,
    build_plan_template,
    build_reassessment_template,
)


class TemplateProvider:
    @property
    def provider_name(self) -> str:
        return "student_companion_template_v1"

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> dict:
        del system_prompt
        context = json.loads(user_prompt)
        builders = {
            "DetailedLearningPlan": build_plan_template,
            "ReassessmentPackage": build_reassessment_template,
            "PersonalizedFeedback": build_feedback_template,
        }
        if schema_name not in builders:
            raise ValueError("unsupported template schema")
        return builders[schema_name](context)
