"""Run the deterministic Student Companion Engine V1 scenario matrix."""

from __future__ import annotations

from phase1_demo.engine_scenarios import ENGINE_SCENARIOS


def run_scenarios(write=print) -> None:
    passed = 0
    for scenario in ENGINE_SCENARIOS:
        try:
            scenario.run()
        except Exception as exc:
            write(f"[FAIL] {scenario.scenario_id} {scenario.name}: {exc}")
            raise
        passed += 1
        write(f"[PASS] {scenario.scenario_id} {scenario.name}")
    write(f"ENGINE SCENARIOS PASSED: {passed}/{len(ENGINE_SCENARIOS)}")


if __name__ == "__main__":
    run_scenarios()
