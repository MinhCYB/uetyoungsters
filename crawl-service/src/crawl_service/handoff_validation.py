"""Read-only Data Layer handoff readiness validation.

This command never runs collectors and never writes data. It validates local
production Parquet tables when available, or deterministic integration fixtures
for fresh-clone contract checks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable

import pandas as pd

from .paths import PROJECT_ROOT

from core.shared.contracts.market import (
    JobPostingRecord,
    ExtractedSkill,
)
from core.shared.schemas import StudentProfile
from core.shared.taxonomy import load_taxonomy


PROCESSED_FILENAMES = {
    "jobs": "jobs_clean.parquet",
    "skills": "job_skills.parquet",
    "demand": "career_demand_summary.parquet",
    "matrix": "career_skill_matrix.parquet",
    "lifecycle": "job_lifecycle.parquet",
}
WORK_MODES = {"ONSITE", "HYBRID", "REMOTE", "UNSPECIFIED"}
REQUIREMENT_LEVELS = {
    "required",
    "preferred",
    "not_required",
    "mentioned",
    "nice_to_have",
}
EXPECTED_PRODUCTION_COUNTS = {
    "jobs": 106,
    "greenhouse": 16,
    "viecoi": 90,
    "active": 106,
    "invalid": 2,
    "jobs_with_skills": 101,
    "remote": 2,
    "salary": 89,
}


class HandoffValidationError(ValueError):
    """Raised when a handoff readiness invariant is broken."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HandoffValidationError(message)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _nonempty(series: pd.Series) -> pd.Series:
    return series.notna() & series.astype(str).str.strip().ne("")


def _require_columns(
    table: pd.DataFrame,
    columns: Iterable[str],
    table_name: str,
) -> None:
    missing = sorted(set(columns) - set(table.columns))
    require(not missing, f"{table_name} missing columns: {missing}")


def validate_taxonomy(payload: Any) -> dict[str, set[str]]:
    require(isinstance(payload, dict), "Taxonomy root must be an object")
    require(
        payload.get("taxonomy_version") == "0.4.0",
        "Canonical taxonomy_version must be 0.4.0",
    )

    definitions = (
        ("careers", "career_id", "canonical_name", "CAREER_"),
        ("skills", "skill_id", "canonical_name", "SKILL_"),
    )
    ids: dict[str, set[str]] = {}
    for collection, id_key, name_key, prefix in definitions:
        entities = payload.get(collection)
        require(
            isinstance(entities, list) and bool(entities),
            f"Taxonomy {collection} must be a non-empty list",
        )
        entity_ids = [entity.get(id_key) for entity in entities]
        require(
            len(entity_ids) == len(set(entity_ids)),
            f"Duplicate {id_key} in taxonomy",
        )
        for entity in entities:
            entity_id = entity.get(id_key)
            require(
                isinstance(entity_id, str)
                and entity_id.startswith(prefix)
                and not any(char.isspace() for char in entity_id),
                f"Invalid {id_key}: {entity_id!r}",
            )
            require(
                isinstance(entity.get(name_key), str)
                and bool(entity[name_key].strip()),
                f"Empty {name_key} for {entity_id}",
            )
            aliases = entity.get("aliases")
            require(
                isinstance(aliases, list) and bool(aliases),
                f"Aliases must be non-empty for {entity_id}",
            )
            alias_keys = [
                alias.strip().casefold()
                for alias in aliases
                if isinstance(alias, str) and alias.strip()
            ]
            require(
                len(alias_keys) == len(aliases),
                f"Empty alias for {entity_id}",
            )
            require(
                len(alias_keys) == len(set(alias_keys)),
                f"Duplicate alias for {entity_id}",
            )
        ids[collection] = set(entity_ids)

    locations = payload.get("locations")
    require(
        isinstance(locations, list) and bool(locations),
        "Taxonomy locations must be a non-empty list",
    )
    provinces: set[str] = set()
    for location in locations:
        province = location.get("province")
        require(
            isinstance(province, str) and bool(province.strip()),
            "Location province must be non-empty",
        )
        require(province not in provinces, f"Duplicate province: {province}")
        provinces.add(province)
        aliases = location.get("aliases")
        require(
            isinstance(aliases, list) and bool(aliases),
            f"Aliases must be non-empty for province {province}",
        )
        alias_keys = [
            alias.strip().casefold()
            for alias in aliases
            if isinstance(alias, str) and alias.strip()
        ]
        require(
            len(alias_keys) == len(aliases),
            f"Empty alias for province {province}",
        )
        require(
            len(alias_keys) == len(set(alias_keys)),
            f"Duplicate alias for province {province}",
        )
    ids["locations"] = provinces
    return ids


def validate_profile(
    profile: Any,
    taxonomy: dict[str, Any],
    taxonomy_ids: dict[str, set[str]],
) -> StudentProfile:
    require(isinstance(profile, dict), "Student profile must be an object")
    profile_id = profile.get("profile_id") or profile.get("id")
    require(bool(profile_id), "Student profile requires profile_id or id")
    require(
        profile.get("taxonomy_version") == taxonomy["taxonomy_version"],
        "Student profile taxonomy_version is inconsistent",
    )
    require(
        not ({"posted_at", "collected_at", "salary_min_vnd"} & profile.keys()),
        "Student profile contains market-only fields",
    )

    skills = profile.get("skills", [])
    require(isinstance(skills, list), "Student profile skills must be a list")
    for skill in skills:
        require(
            skill.get("skill_id") in taxonomy_ids["skills"],
            f"Unknown profile skill_id: {skill.get('skill_id')}",
        )

    constraints = profile.get("location_constraints", {})
    alias_to_province: dict[str, str] = {}
    for location in taxonomy["locations"]:
        for alias in [location["province"], *location["aliases"]]:
            alias_to_province[alias.strip().casefold()] = location["province"]
    for province in constraints.get("preferred_provinces", []):
        require(
            str(province).strip().casefold() in alias_to_province,
            f"Unknown preferred province: {province}",
        )
    for mode in constraints.get("preferred_work_modes", []):
        require(mode in WORK_MODES, f"Invalid preferred work mode: {mode}")

    model = StudentProfile.model_validate(profile)
    serialized = model.model_dump(mode="json")
    require(
        StudentProfile.model_validate(serialized) == model,
        "Student profile is not serialization-stable",
    )
    return model


def validate_market_contracts(
    jobs: pd.DataFrame,
    skills: pd.DataFrame,
) -> None:
    def clean_record(record: dict[str, Any]) -> dict[str, Any]:
        return {
            key: None if pd.isna(value) else value
            for key, value in record.items()
        }

    JobPostingRecord.model_validate(clean_record(jobs.iloc[0].to_dict()))
    ExtractedSkill.model_validate(clean_record(skills.iloc[0].to_dict()))


def validate_tables(
    tables: dict[str, pd.DataFrame],
    taxonomy: dict[str, Any],
    taxonomy_ids: dict[str, set[str]],
    *,
    production: bool,
) -> dict[str, Any]:
    jobs = tables["jobs"]
    skills = tables["skills"]
    demand = tables["demand"]
    matrix = tables["matrix"]
    lifecycle = tables.get("lifecycle", pd.DataFrame())
    for name, table in tables.items():
        if name != "lifecycle" or production:
            require(not table.empty, f"{name} table is empty")

    _require_columns(
        jobs,
        {
            "job_id", "source", "source_id", "source_job_id", "source_url",
            "job_title_raw", "career_id", "career_name", "province",
            "work_mode", "salary_disclosed", "posted_at", "snapshot_version",
            "taxonomy_version", "overall_confidence", "is_active",
        },
        "jobs",
    )
    for column in (
        "job_id", "source_id", "source_job_id", "source_url",
        "job_title_raw", "career_id", "career_name", "snapshot_version",
        "taxonomy_version",
    ):
        require(_nonempty(jobs[column]).all(), f"jobs.{column} contains null/empty")
    require(not jobs["job_id"].duplicated().any(), "Duplicate current job_id")
    require(
        not jobs.duplicated(["source_id", "source_job_id"]).any(),
        "Duplicate source_id + source_job_id",
    )
    require(
        jobs["overall_confidence"].between(0, 1, inclusive="both").all(),
        "Job confidence outside [0, 1]",
    )
    require(
        set(jobs["work_mode"].dropna()) <= WORK_MODES,
        "Invalid work_mode in jobs",
    )
    require(
        set(jobs["career_id"]) <= taxonomy_ids["careers"],
        "Unknown warehouse career_id in jobs",
    )
    require(
        not jobs["source_url"].str.contains(
            "/viec-lam/danh-muc-", case=False, na=False
        ).any(),
        "Category false-positive URL in current jobs",
    )
    viecoi = jobs[jobs["source"].astype(str).str.casefold().eq("viecoi")]
    require(
        not viecoi["source_job_id"].astype(str).isin({"2", "8"}).any(),
        "Invalid ViecOi category source_job_id in current jobs",
    )
    if "content_hash" in jobs:
        require(not jobs["content_hash"].duplicated().any(), "Duplicate content hash")
    if "lifecycle_status" in jobs:
        require(
            set(jobs["lifecycle_status"].dropna()) <= {"active"},
            "Invalid/inactive lifecycle row in current jobs",
        )

    _require_columns(
        skills,
        {
            "job_id", "career_id", "skill_id", "skill_name", "raw_mention",
            "requirement_level", "confidence",
        },
        "job_skills",
    )
    for column in ("job_id", "skill_id", "skill_name"):
        require(_nonempty(skills[column]).all(), f"job_skills.{column} is empty")
    require(
        skills["confidence"].between(0, 1, inclusive="both").all(),
        "Skill confidence outside [0, 1]",
    )
    require(
        set(skills["requirement_level"]) <= REQUIREMENT_LEVELS,
        "Invalid requirement_level",
    )
    require(
        set(skills["job_id"]) <= set(jobs["job_id"]),
        "Orphan job skill",
    )
    require(
        set(skills["skill_id"]) <= taxonomy_ids["skills"],
        "Unknown job skill_id",
    )
    require(
        set(skills["career_id"].dropna()) <= taxonomy_ids["careers"],
        "Unknown job-skill career_id",
    )
    require(
        not skills.duplicated(["job_id", "skill_id", "raw_mention"]).any(),
        "Duplicate job skill mention",
    )

    _require_columns(
        demand,
        {"career_id", "snapshot_version", "posting_count", "salary_sample_size"},
        "career_demand_summary",
    )
    require(
        set(demand["career_id"]) <= taxonomy_ids["careers"],
        "Unknown warehouse career_id in demand",
    )
    require((demand["posting_count"] >= 0).all(), "Negative posting_count")
    require(
        (demand["salary_sample_size"] <= demand["posting_count"]).all(),
        "salary_sample_size exceeds posting_count",
    )
    grouping_columns = [
        column
        for column in ("career_id", "province", "work_mode")
        if column in demand.columns and column in jobs.columns
    ]
    if "salary_mid_vnd" in jobs.columns:
        for demand_row in demand.itertuples(index=False):
            group = jobs
            for column in grouping_columns:
                value = getattr(demand_row, column)
                group = group[
                    group[column].isna()
                    if pd.isna(value)
                    else group[column].eq(value)
                ]
            salary_values = group.loc[
                group["salary_disclosed"].fillna(False),
                "salary_mid_vnd",
            ].dropna()
            require(
                int(getattr(demand_row, "salary_sample_size"))
                == len(salary_values),
                "Demand salary_sample_size does not reconcile",
            )
            if "salary_median_vnd" in demand.columns:
                actual_median = getattr(demand_row, "salary_median_vnd")
                expected_median = (
                    float(salary_values.median())
                    if not salary_values.empty
                    else None
                )
                require(
                    (expected_median is None and pd.isna(actual_median))
                    or (
                        expected_median is not None
                        and not pd.isna(actual_median)
                        and abs(float(actual_median) - expected_median) < 0.01
                    ),
                    "Demand salary median does not reconcile",
                )
    if "data_from" in demand and "data_to" in demand:
        dated = demand.dropna(subset=["data_from", "data_to"])
        require(
            all(str(row.data_from) <= str(row.data_to) for row in dated.itertuples()),
            "Demand data_from is after data_to",
        )
        if jobs["posted_at"].isna().all():
            require(
                demand[["data_from", "data_to"]].isna().all().all(),
                "Demand period was invented without posted_at evidence",
            )

    _require_columns(
        matrix,
        {"career_id", "skill_id", "skill_posting_count", "posting_count"},
        "career_skill_matrix",
    )
    require(
        set(matrix["career_id"]) <= taxonomy_ids["careers"],
        "Unknown matrix career_id",
    )
    require(
        set(matrix["skill_id"]) <= taxonomy_ids["skills"],
        "Unknown matrix skill_id",
    )
    require(
        (matrix[["skill_posting_count", "posting_count"]] >= 0).all().all(),
        "Negative matrix count",
    )
    if "share_of_career_jobs" in matrix:
        require(
            matrix["share_of_career_jobs"].between(0, 1, inclusive="both").all(),
            "Matrix share outside [0, 1]",
        )
    matrix_key = [
        column for column in ("career_id", "province", "work_mode", "skill_id")
        if column in matrix
    ]
    require(not matrix.duplicated(matrix_key).any(), "Duplicate matrix key")

    job_snapshots = set(jobs["snapshot_version"].dropna().astype(str))
    demand_snapshots = set(demand["snapshot_version"].dropna().astype(str))
    require(
        len(job_snapshots) == 1 and demand_snapshots == job_snapshots,
        "Inconsistent snapshot_version across current tables",
    )
    require(
        set(jobs["taxonomy_version"].dropna().astype(str))
        == {taxonomy["taxonomy_version"]},
        "Inconsistent taxonomy_version in jobs",
    )

    metrics = {
        "current_jobs": len(jobs),
        "source_distribution": {
            str(key): int(value) for key, value in jobs["source"].value_counts().items()
        },
        "career_mapped": int(jobs["career_id"].notna().sum()),
        "location_mapped": int(jobs["province"].notna().sum()),
        "jobs_with_skills": int(jobs["job_id"].isin(set(skills["job_id"])).sum()),
        "salary_disclosed": int(jobs["salary_disclosed"].fillna(False).sum()),
        "remote_jobs": int(jobs["work_mode"].eq("REMOTE").sum()),
        "duplicate_source_keys": int(
            jobs.duplicated(["source_id", "source_job_id"]).sum()
        ),
        "snapshot_version": next(iter(job_snapshots)),
        "taxonomy_version": taxonomy["taxonomy_version"],
    }

    if production:
        expected = EXPECTED_PRODUCTION_COUNTS
        require(len(jobs) == expected["jobs"], "Production current job count is not 106")
        require(metrics["source_distribution"].get("greenhouse") == expected["greenhouse"], "Greenhouse count is not 16")
        require(metrics["source_distribution"].get("viecoi") == expected["viecoi"], "ViecOi count is not 90")
        require("topcv" not in metrics["source_distribution"], "TopCV found in production")
        require(int(demand["posting_count"].sum()) == len(jobs), "Demand posting_count does not reconcile")
        require(metrics["jobs_with_skills"] == expected["jobs_with_skills"], "Mapped-skill job count is not 101")
        require(metrics["salary_disclosed"] == expected["salary"], "Salary count is not 89")
        require(metrics["remote_jobs"] == expected["remote"], "Remote count is not 2")

        _require_columns(
            lifecycle,
            {"source_id", "source_job_id", "first_seen_at", "last_seen_at", "consecutive_missing_runs", "lifecycle_status"},
            "job_lifecycle",
        )
        require(
            not lifecycle.duplicated(["source_id", "source_job_id"]).any(),
            "Duplicate lifecycle key",
        )
        require(
            (lifecycle["consecutive_missing_runs"] >= 0).all(),
            "Negative consecutive_missing_runs",
        )
        require(
            (pd.to_datetime(lifecycle["first_seen_at"], utc=True) <= pd.to_datetime(lifecycle["last_seen_at"], utc=True)).all(),
            "Lifecycle first_seen_at is after last_seen_at",
        )
        active = int(lifecycle["lifecycle_status"].eq("active").sum())
        invalid = int(lifecycle["lifecycle_status"].eq("invalid").sum())
        require(active == expected["active"], "Lifecycle active count is not 106")
        require(invalid == expected["invalid"], "Lifecycle invalid count is not 2")
        metrics.update({"lifecycle_active": active, "lifecycle_invalid": invalid})

    validate_market_contracts(jobs, skills)
    return metrics


def build_matching_demo(
    profile: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    taxonomy_version: str,
) -> dict[str, Any]:
    skill_ids = {skill["skill_id"] for skill in profile.get("skills", [])}
    matrix = tables["matrix"]
    matched = matrix[matrix["skill_id"].isin(skill_ids)]
    require(not matched.empty, "Profile has no matching career-skill rows")
    ranking = (
        matched.groupby("career_id")["skill_id"]
        .nunique()
        .sort_values(ascending=False, kind="stable")
    )
    career_id = str(ranking.index[0])
    matched_skill_ids = sorted(
        matched.loc[matched["career_id"].eq(career_id), "skill_id"].unique()
    )
    demand = tables["demand"]
    demand_rows = demand[demand["career_id"].eq(career_id)]
    require(not demand_rows.empty, "Matched career is absent from demand summary")
    jobs = tables["jobs"]
    sample_jobs = jobs[
        jobs["career_id"].eq(career_id) & jobs["is_active"].fillna(False)
    ].head(3)
    require(not sample_jobs.empty, "Matched career has no active sample jobs")
    snapshot_versions = sorted(
        set(demand_rows["snapshot_version"].dropna().astype(str))
    )
    require(len(snapshot_versions) == 1, "Demo career has inconsistent snapshots")
    return {
        "profile_id": profile.get("profile_id") or profile.get("id"),
        "career_id": career_id,
        "matched_skill_ids": matched_skill_ids,
        "market_posting_count": int(demand_rows["posting_count"].sum()),
        "sample_job_ids": sample_jobs["job_id"].astype(str).tolist(),
        "taxonomy_version": taxonomy_version,
        "snapshot_version": snapshot_versions[0],
    }


def derive_fixture_matrix(
    jobs: pd.DataFrame,
    skills: pd.DataFrame,
) -> pd.DataFrame:
    skill_counts = (
        skills.groupby(["career_id", "skill_id", "skill_name"], dropna=False)["job_id"]
        .nunique()
        .rename("skill_posting_count")
        .reset_index()
    )
    career_counts = jobs.groupby("career_id")["job_id"].nunique().rename("posting_count")
    matrix = skill_counts.join(career_counts, on="career_id")
    matrix["share_of_career_jobs"] = (
        matrix["skill_posting_count"] / matrix["posting_count"]
    )
    return matrix


def load_fixture_tables(root: Path) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    fixture_root = root / "tests" / "fixtures" / "integration"
    jobs = pd.DataFrame(read_json(fixture_root / "jobs_clean_sample.json"))
    skills = pd.DataFrame(read_json(fixture_root / "job_skills_sample.json"))
    tables = {
        "jobs": jobs,
        "skills": skills,
        "demand": pd.DataFrame(read_json(fixture_root / "career_demand_sample.json")),
        "matrix": derive_fixture_matrix(jobs, skills),
        "lifecycle": pd.DataFrame(),
    }
    return tables, read_json(fixture_root / "student_profile_sample.json")


def load_production_tables(root: Path) -> dict[str, pd.DataFrame]:
    processed = root / "data" / "processed"
    return {
        name: pd.read_parquet(processed / filename)
        for name, filename in PROCESSED_FILENAMES.items()
    }


def missing_production_files(root: Path) -> list[Path]:
    processed = root / "data" / "processed"
    return [
        processed / filename
        for filename in PROCESSED_FILENAMES.values()
        if not (processed / filename).exists()
    ]


def validate_quality_reports(
    root: Path,
    metrics: dict[str, Any],
) -> None:
    report_root = root / "reports"
    paths = [
        report_root / "data_quality.json",
        report_root / "source_coverage.json",
        report_root / "taxonomy_coverage.json",
    ]
    if not all(path.exists() for path in paths):
        return
    reports = [read_json(path) for path in paths]
    for path, report in zip(paths, reports):
        require(isinstance(report, dict), f"{path.name} root must be an object")
        require(report.get("generated_at"), f"{path.name} missing generated_at")
        require(report.get("snapshot_version"), f"{path.name} missing snapshot_version")
        require(
            report.get("taxonomy_version") == metrics["taxonomy_version"],
            f"{path.name} taxonomy_version is inconsistent",
        )
        text = json.dumps(report, ensure_ascii=False).casefold()
        require("growth_rate" not in text, f"{path.name} contains unsupported growth_rate")
    source = reports[1]
    for key in (
        "career_mapping_rate", "skill_mapping_rate",
        "location_mapping_rate_non_remote",
    ):
        require(0 <= source[key] <= 1, f"source_coverage {key} outside [0, 1]")
    require(source["duplicate_count"] == 0, "Quality duplicate_count is not zero")
    require(
        source["source_distribution"] == metrics["source_distribution"],
        "Quality source distribution does not reconcile",
    )
    require(
        source["jobs_with_mapped_skills"] == metrics["jobs_with_skills"],
        "Quality mapped-skill count does not reconcile",
    )
    require(
        source["total_lifecycle_records"]
        == source["valid_lifecycle_records"]
        + source["invalid_records_excluded"],
        "Quality lifecycle counts do not reconcile",
    )
    require(
        source["salary_available_count"] == metrics["salary_disclosed"],
        "Quality salary count does not reconcile",
    )
    require(
        source["remote_job_count"] == metrics["remote_jobs"],
        "Quality remote count does not reconcile",
    )
    note = str(source.get("coverage_note", "")).casefold()
    require(
        "does not represent the entire" in note,
        "Quality report lacks market-coverage limitation",
    )


def validate_generated_file_guard(root: Path) -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    allowed_data = {
        "data/raw/.gitkeep",
        "data/interim/.gitkeep",
        "data/processed/.gitkeep",
        "data/quality/.gitkeep",
    }
    violations: list[str] = []
    for raw_path in result.stdout.splitlines():
        path = raw_path.replace("\\", "/")
        lowered = path.casefold()
        if path.startswith("tests/fixtures/"):
            continue
        if path in allowed_data:
            continue
        if (
            lowered.endswith(".parquet")
            or lowered.endswith(".csv")
            or lowered.endswith(".html")
            or "node_modules/" in lowered
            or ".pytest_cache" in lowered
            or "pytest_tmp" in lowered
            or path.startswith(("data/raw/", "data/interim/", "data/processed/", "data/debug/"))
        ):
            violations.append(path)
    require(not violations, f"Generated files tracked by Git: {violations}")


def run_validation(
    root: Path = PROJECT_ROOT,
    *,
    fixtures_only: bool = False,
    production_only: bool = False,
) -> dict[str, Any]:
    require(
        not (fixtures_only and production_only),
        "Choose either fixtures-only or production-only",
    )
    missing = missing_production_files(root)
    if production_only:
        require(
            not missing,
            "Production Parquet files missing: " + ", ".join(str(path) for path in missing),
        )
        production = True
    elif fixtures_only:
        production = False
    else:
        production = not missing

    taxonomy_path = root / "backend" / "shared" / "taxonomy.json"
    taxonomy = load_taxonomy(taxonomy_path)
    taxonomy_ids = validate_taxonomy(taxonomy)
    require(
        not (root / "core" / "shared" / "taxonomy.json").exists(),
        "Competing core taxonomy JSON exists",
    )
    fixture_root = root / "tests" / "fixtures" / "integration"
    profile = read_json(fixture_root / "student_profile_sample.json")
    validate_profile(profile, taxonomy, taxonomy_ids)
    if production:
        tables = load_production_tables(root)
    else:
        tables, profile = load_fixture_tables(root)
    metrics = validate_tables(
        tables,
        taxonomy,
        taxonomy_ids,
        production=production,
    )
    demo = build_matching_demo(profile, tables, taxonomy["taxonomy_version"])
    if production:
        validate_quality_reports(root, metrics)
    validate_generated_file_guard(root)
    return {
        "mode": "PRODUCTION" if production else "FIXTURE",
        "metrics": metrics,
        "matching_demo": demo,
    }


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fixtures-only", action="store_true")
    mode.add_argument("--production-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_validation(
            fixtures_only=args.fixtures_only,
            production_only=args.production_only,
        )
    except (HandoffValidationError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"BLOCKER: {exc}", file=sys.stderr)
        print("DATA HANDOFF READINESS: FAIL")
        return 1

    print(f"DATA MODE: {result['mode']}")
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    print("MATCHING INPUT SMOKE TEST")
    print(json.dumps(result["matching_demo"], ensure_ascii=False, indent=2))
    print("DATA HANDOFF READINESS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
