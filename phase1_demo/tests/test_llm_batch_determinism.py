from __future__ import annotations

from phase1_demo.student_companion.llm.orchestrator import (
    StudentCompanionContentOrchestrator,
)
from phase1_demo.student_companion.llm.providers import TemplateProvider
from phase1_demo.tests.content_factory import plan_request


def test_twenty_template_content_requests_are_deterministic_and_isolated() -> None:
    orchestrator = StudentCompanionContentOrchestrator(TemplateProvider())
    requests = []
    for index in range(20):
        request = plan_request(
            metadata=plan_request().metadata.model_copy(
                update={"request_id": f"BATCH_CONTENT_{index:02d}"}
            ),
            max_steps=2 + index % 3,
            difficulty=("foundation" if index % 2 == 0 else "standard"),
            student_preferences=[f"cách học {index % 4}"],
        )
        requests.append(request)

    before = [item.model_dump_json() for item in requests]
    first = [orchestrator.expand_plan(item).model_dump_json() for item in requests]
    second = [orchestrator.expand_plan(item).model_dump_json() for item in requests]

    assert first == second
    assert [item.model_dump_json() for item in requests] == before
    assert len({item for item in first}) == 20
