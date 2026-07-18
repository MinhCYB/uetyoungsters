from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawl_service.cli import cli as crawl_cli
from crawl_service.cli import main as crawl_main

from crawl_service.shared_contracts.market import (
    MarketJobRecord,
    MarketSkillRecord,
)
from crawl_service.shared_contracts.schemas import StudentProfile
from crawl_service.shared_contracts.taxonomy import (
    CANONICAL_TAXONOMY_PATH,
    load_canonical_taxonomy,
    load_taxonomy,
)


FIXTURE_ROOT = Path("tests/fixtures/integration")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_core_loads_canonical_taxonomy():
    taxonomy = load_taxonomy()

    assert CANONICAL_TAXONOMY_PATH.exists()
    assert taxonomy["taxonomy_version"] == "0.4.0"
    assert taxonomy["careers"]
    assert taxonomy["skills"]


def test_taxonomy_loader_aliases_are_consistent():
    assert load_taxonomy() == load_canonical_taxonomy()


def test_crawl_wrapper_rejects_unknown_action():
    with pytest.raises(
        ValueError,
        match="Unknown crawl-service command",
    ):
        crawl_main("unknown-action")


def test_crawl_cli_reads_status_argument(capsys):
    crawl_cli(["status"])

    assert "crawl-service is ready" in capsys.readouterr().out


def test_canonical_taxonomy_is_unique_and_versioned():
    taxonomy = load_canonical_taxonomy()

    assert CANONICAL_TAXONOMY_PATH.exists()
    assert taxonomy["taxonomy_version"] == "0.4.0"
    assert not Path("backend/shared/taxonomy.json").exists()

    career_ids = [item["career_id"] for item in taxonomy["careers"]]
    skill_ids = [item["skill_id"] for item in taxonomy["skills"]]
    assert len(career_ids) == len(set(career_ids))
    assert len(skill_ids) == len(set(skill_ids))
    assert all(item.get("aliases") for item in taxonomy["careers"])
    assert all(item.get("aliases") for item in taxonomy["skills"])


def test_market_contract_fixtures_use_taxonomy_ids():
    taxonomy = load_canonical_taxonomy()
    valid_careers = {item["career_id"] for item in taxonomy["careers"]}
    valid_skills = {item["skill_id"] for item in taxonomy["skills"]}
    jobs = [
        MarketJobRecord.model_validate(item)
        for item in _read_json(FIXTURE_ROOT / "jobs_clean_sample.json")
    ]
    skills = [
        MarketSkillRecord.model_validate(item)
        for item in _read_json(FIXTURE_ROOT / "job_skills_sample.json")
    ]

    assert 5 <= len(jobs) <= 10
    assert len({job.career_id for job in jobs}) >= 2
    assert any(job.work_mode.value == "REMOTE" for job in jobs)
    assert {job.career_id for job in jobs} <= valid_careers
    assert {skill.skill_id for skill in skills} <= valid_skills


def test_student_profile_fixture_matches_profile_contract():
    profile = StudentProfile.model_validate(
        _read_json(FIXTURE_ROOT / "student_profile_sample.json")
    )
    assert profile.id == "sample_profile_001"
    assert profile.consent_settings.data_usage_ack is True


def test_main_application_skeleton_is_preserved():
    required_paths = [
        "crawl-service/main.py",
        "backend-api/main.py",
        "docker-compose.yml",
        "docs/career-compass-notes.md",
        "docs/career-compass-schema-draft.md",
        "docs/database-notes.md",
    ]
    assert all(Path(path).exists() for path in required_paths)
