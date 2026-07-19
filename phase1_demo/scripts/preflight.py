"""Deterministic preflight checks for the complete local demo."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from phase1_demo.run_demo import create_server
from phase1_demo.student_companion.application import DemoService
from phase1_demo.student_companion.domain import GapType
from phase1_demo.student_companion.infrastructure import (
    build_market_snapshot,
    load_followup_fixtures,
    load_initial_fixtures,
)


STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"


class PreflightFailure(RuntimeError):
    pass


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise PreflightFailure(message)


def run_preflight(write: Callable[[str], None] = print) -> None:
    initial = load_initial_fixtures()
    _check(initial.student.student_id == initial.pretest_attempt.student_id, "T0 student mismatch")
    write("[PASS] fixtures T0")

    followup = load_followup_fixtures()
    _check(followup.posttest_attempt.student_id == initial.student.student_id, "T1 student mismatch")
    write("[PASS] fixtures T1")

    market = build_market_snapshot()
    _check(bool(market), "market adapter returned no career groups")
    market_modes = sorted({item.data_mode for item in market})
    _check(set(market_modes) <= {"pipeline_export", "fallback_demo"}, "invalid market mode")
    write(f"[PASS] market adapter: {','.join(market_modes)}")

    service = DemoService()
    analyzed = service.analyze_initial_state()
    _check(analyzed["stage"] == "analyzed", "T0 analyze did not reach analyzed stage")
    _check(
        any(
            gap.gap_type is GapType.ACADEMIC
            and gap.skill_id == "SKILL_TRIG_TRANSFORMATION"
            for gap in service.gaps_t0
        ),
        "trigonometry academic gap missing",
    )
    _check(
        any(gap.gap_type is GapType.EXPLORATION for gap in service.gaps_t0),
        "exploration gap missing",
    )
    _check(
        any(gap.gap_type is GapType.DECISION for gap in service.gaps_t0),
        "decision gap missing",
    )
    write("[PASS] analyze T0: academic + exploration + decision gaps")

    service.generate_weekly_plan()
    _check(
        service.plan_t0.total_planned_minutes <= service.plan_t0.weekly_budget_minutes,
        "plan exceeds weekly budget",
    )
    _check(service.plan_t0.total_planned_minutes == 45, "main fixture plan is not 45 minutes")
    write(
        f"[PASS] plan: {service.plan_t0.total_planned_minutes}/"
        f"{service.plan_t0.weekly_budget_minutes} minutes"
    )

    t0_before_advance = service.snapshot_t0.model_dump_json()
    service.advance_two_weeks()
    trig_outcome = next(
        item for item in service.outcomes_t1 if item.metric_type == "SKILL_TRIG_TRANSFORMATION"
    )
    _check(trig_outcome.after_value > trig_outcome.before_value, "trigonometry did not improve")
    _check(
        trig_outcome.status.value == "meaningful_improvement",
        "trigonometry outcome is not meaningful_improvement",
    )
    write(f"[PASS] outcome: {trig_outcome.status.value}")

    _check(
        not any(
            gap.gap_type is GapType.EXPLORATION
            and gap.career_group_ids == ["CAREER_GROUP_DATA_AI"]
            for gap in service.gaps_t1
        ),
        "Data/AI exploration gap was not updated",
    )
    write("[PASS] Data/AI exploration gap updated")

    _check(
        service.next_step is not None
        and service.next_step.career_group_id == "CAREER_GROUP_ECONOMICS",
        "next step is not the Economics micro-experience",
    )
    write("[PASS] next step: CAREER_GROUP_ECONOMICS")

    _check(
        service.snapshot_t0.model_dump_json() == t0_before_advance,
        "T0 snapshot mutated during T1 advance",
    )
    write("[PASS] T0 snapshot immutable during advance")

    required_static = [STATIC_ROOT / name for name in ("index.html", "styles.css", "app.js")]
    _check(all(path.is_file() for path in required_static), "one or more static UI files are missing")
    write("[PASS] static UI")

    _check(callable(create_server), "local server create_server import failed")
    write("[PASS] local server import")
    write("PRE-FLIGHT PASSED")


def main() -> int:
    try:
        run_preflight()
    except (PreflightFailure, OSError, ValueError) as exc:
        print(f"[FAIL] {exc}")
        print("PRE-FLIGHT FAILED")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
