from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

import pandas as pd
import pytest

from crawl_service.shared_contracts.taxonomy import load_taxonomy
from crawl_service.handoff_validation import (
    HandoffValidationError,
    PROJECT_ROOT,
    build_matching_demo,
    load_fixture_tables,
    run_validation,
    validate_generated_file_guard,
    validate_profile,
    validate_tables,
    validate_taxonomy,
)


def fixture_bundle():
    taxonomy = load_taxonomy()
    taxonomy_ids = validate_taxonomy(taxonomy)
    tables, profile = load_fixture_tables(PROJECT_ROOT)
    return taxonomy, taxonomy_ids, tables, profile


def copy_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {name: table.copy(deep=True) for name, table in tables.items()}


def validate_fixture_tables(tables: dict[str, pd.DataFrame]) -> dict:
    taxonomy, taxonomy_ids, _, _ = fixture_bundle()
    return validate_tables(
        tables,
        taxonomy,
        taxonomy_ids,
        production=False,
    )


def test_canonical_taxonomy_passes():
    taxonomy = load_taxonomy()
    ids = validate_taxonomy(taxonomy)
    assert "CAREER_DATA_ANALYST" in ids["careers"]
    assert "SKILL_SQL" in ids["skills"]


def test_duplicate_career_id_fails():
    taxonomy = deepcopy(load_taxonomy())
    taxonomy["careers"].append(deepcopy(taxonomy["careers"][0]))
    with pytest.raises(HandoffValidationError, match="Duplicate career_id"):
        validate_taxonomy(taxonomy)


def test_unknown_profile_skill_id_fails():
    taxonomy, taxonomy_ids, _, profile = fixture_bundle()
    profile = deepcopy(profile)
    profile["skills"][0]["skill_id"] = "SKILL_UNKNOWN"
    with pytest.raises(HandoffValidationError, match="Unknown profile skill_id"):
        validate_profile(profile, taxonomy, taxonomy_ids)


def test_unknown_warehouse_career_id_fails():
    _, _, tables, _ = fixture_bundle()
    tables = copy_tables(tables)
    tables["demand"].loc[0, "career_id"] = "CAREER_UNKNOWN"
    with pytest.raises(HandoffValidationError, match="Unknown warehouse career_id"):
        validate_fixture_tables(tables)


def test_unknown_job_skill_id_fails():
    _, _, tables, _ = fixture_bundle()
    tables = copy_tables(tables)
    tables["skills"].loc[0, "skill_id"] = "SKILL_UNKNOWN"
    with pytest.raises(HandoffValidationError, match="Unknown job skill_id"):
        validate_fixture_tables(tables)


def test_cross_table_orphan_job_skill_fails():
    _, _, tables, _ = fixture_bundle()
    tables = copy_tables(tables)
    tables["skills"].loc[0, "job_id"] = "orphan_job"
    with pytest.raises(HandoffValidationError, match="Orphan job skill"):
        validate_fixture_tables(tables)


def test_duplicate_source_job_key_fails():
    _, _, tables, _ = fixture_bundle()
    tables = copy_tables(tables)
    duplicate = tables["jobs"].iloc[[0]].copy()
    duplicate["job_id"] = "another_job_id"
    tables["jobs"] = pd.concat([tables["jobs"], duplicate], ignore_index=True)
    with pytest.raises(HandoffValidationError, match="Duplicate source_id"):
        validate_fixture_tables(tables)


def test_category_false_positive_url_fails():
    _, _, tables, _ = fixture_bundle()
    tables = copy_tables(tables)
    tables["jobs"].loc[0, "source_url"] = (
        "https://viecoi.vn/viec-lam/danh-muc-ban-hang-2.html"
    )
    with pytest.raises(HandoffValidationError, match="Category false-positive"):
        validate_fixture_tables(tables)


def test_profile_to_career_fixture_join_succeeds():
    taxonomy, _, tables, profile = fixture_bundle()
    demo = build_matching_demo(profile, tables, taxonomy["taxonomy_version"])
    assert demo["career_id"] == "CAREER_DATA_ANALYST"
    assert demo["matched_skill_ids"] == ["SKILL_EXCEL", "SKILL_SQL"]


def test_career_to_demand_join_succeeds():
    taxonomy, _, tables, profile = fixture_bundle()
    demo = build_matching_demo(profile, tables, taxonomy["taxonomy_version"])
    assert demo["market_posting_count"] == 1
    assert demo["snapshot_version"] == "fixture-v1"


def test_career_to_sample_job_join_succeeds():
    taxonomy, _, tables, profile = fixture_bundle()
    demo = build_matching_demo(profile, tables, taxonomy["taxonomy_version"])
    assert demo["sample_job_ids"] == ["sample_job_001"]


def test_nullable_posted_at_does_not_fail():
    _, _, tables, _ = fixture_bundle()
    assert tables["jobs"]["posted_at"].isna().all()
    assert validate_fixture_tables(tables)["current_jobs"] == 5


def test_remote_job_with_null_province_passes():
    _, _, tables, _ = fixture_bundle()
    remote = tables["jobs"][tables["jobs"]["work_mode"].eq("REMOTE")]
    assert len(remote) == 1
    assert remote["province"].isna().all()
    validate_fixture_tables(tables)


def test_invalid_work_mode_fails():
    _, _, tables, _ = fixture_bundle()
    tables = copy_tables(tables)
    tables["jobs"].loc[0, "work_mode"] = "ANYWHERE"
    with pytest.raises(HandoffValidationError, match="Invalid work_mode"):
        validate_fixture_tables(tables)


@pytest.mark.parametrize(
    ("table_name", "column", "value", "message"),
    [
        ("jobs", "overall_confidence", 1.1, "Job confidence"),
        ("skills", "confidence", -0.1, "Skill confidence"),
    ],
)
def test_score_or_confidence_outside_range_fails(
    table_name: str,
    column: str,
    value: float,
    message: str,
):
    _, _, tables, _ = fixture_bundle()
    tables = copy_tables(tables)
    tables[table_name].loc[0, column] = value
    with pytest.raises(HandoffValidationError, match=message):
        validate_fixture_tables(tables)


def test_fixture_only_validation_passes_without_production_parquet():
    result = run_validation(fixtures_only=True)
    assert result["mode"] == "FIXTURE"
    assert result["matching_demo"]["sample_job_ids"]


def test_production_only_mode_fails_clearly_when_files_missing(tmp_path: Path):
    with pytest.raises(HandoffValidationError, match="Production Parquet files missing"):
        run_validation(root=tmp_path, production_only=True)


def test_validation_script_does_not_modify_input_files():
    fixture_root = PROJECT_ROOT / "tests" / "fixtures" / "integration"
    paths = sorted(fixture_root.glob("*.json"))

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    before = {path: digest(path) for path in paths}
    run_validation(fixtures_only=True)
    after = {path: digest(path) for path in paths}
    assert after == before


def test_all_taxonomy_and_snapshot_versions_are_consistent():
    _, _, tables, _ = fixture_bundle()
    tables = copy_tables(tables)
    tables["jobs"].loc[0, "taxonomy_version"] = "0.3.0"
    with pytest.raises(HandoffValidationError, match="taxonomy_version"):
        validate_fixture_tables(tables)


def test_generated_file_guard_passes():
    validate_generated_file_guard(PROJECT_ROOT)
