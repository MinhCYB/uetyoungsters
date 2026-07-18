"""Export deterministic public-contract examples from the real facade."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from phase1_demo.student_companion.application.facade import StudentCompanionFacade
from phase1_demo.student_companion.infrastructure.demo_contract_adapter import (
    DemoContractAdapter,
)
from phase1_demo.student_companion.infrastructure.market import (
    ReadOnlyMarketContextProvider,
)


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "integration_examples"


def _stable_json(model: BaseModel) -> str:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def export_contract_examples(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    adapter = DemoContractAdapter()
    facade = StudentCompanionFacade(ReadOnlyMarketContextProvider())

    initial_request = adapter.load_initial_request()
    initial_response = facade.analyze(initial_request)
    plan_request = adapter.load_plan_request(
        initial_request.student,
        initial_response.snapshot,
    )
    plan_response = facade.generate_plan(plan_request)
    planned_snapshot = initial_response.snapshot.model_copy(
        update={"active_plan": plan_response.plan},
        deep=True,
    )
    followup_request = adapter.load_followup_request(planned_snapshot)
    followup_response = facade.evaluate_followup(followup_request)

    examples = {
        "initial_analysis_request.json": initial_request,
        "initial_analysis_response.json": initial_response,
        "plan_generation_request.json": plan_request,
        "plan_generation_response.json": plan_response,
        "followup_evaluation_request.json": followup_request,
        "followup_evaluation_response.json": followup_response,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, model in sorted(examples.items()):
        path = output_dir / filename
        path.write_text(_stable_json(model), encoding="utf-8", newline="\n")
        written.append(path)
    return written


def main() -> int:
    paths = export_contract_examples()
    print(f"Exported {len(paths)} contract examples to {DEFAULT_OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
