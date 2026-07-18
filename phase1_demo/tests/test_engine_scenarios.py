import pytest

from phase1_demo.engine_scenarios import ENGINE_SCENARIOS


@pytest.mark.parametrize(
    "scenario",
    ENGINE_SCENARIOS,
    ids=lambda item: item.scenario_id,
)
def test_engine_scenario(scenario) -> None:
    scenario.run()
