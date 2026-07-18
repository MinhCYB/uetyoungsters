"""Read-only market snapshot adapter with a deterministic offline fallback."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from phase1_demo.student_companion.config import (
    ALLOWED_FOUNDATION_SKILLS,
    MARKET_GROUP_MAPPING_VERSION,
    MARKET_GROUPS,
    MARKET_SKILL_TO_FOUNDATION,
)
from phase1_demo.student_companion.domain import MarketCareerGroup


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROCESSED_ROOT = REPOSITORY_ROOT / "data" / "processed"
DEFAULT_FALLBACK_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "market_fallback.json"
MARKET_OUTPUT_FILES = (
    "career_skill_matrix.parquet",
    "career_demand_summary.parquet",
    "jobs_clean.parquet",
    "job_skills.parquet",
)


class MarketDataError(RuntimeError):
    """Raised when pipeline market output cannot satisfy the demo contract."""


class ReadOnlyMarketContextProvider:
    """Protocol-compatible provider backed by pipeline output with fallback."""

    def __init__(
        self,
        processed_root: Path = DEFAULT_PROCESSED_ROOT,
        fallback_path: Path = DEFAULT_FALLBACK_PATH,
    ) -> None:
        self.processed_root = processed_root
        self.fallback_path = fallback_path

    def get_market_context(
        self,
        career_group_ids: list[str],
    ) -> list[MarketCareerGroup]:
        context_by_id = {
            item.career_group_id: item
            for item in build_market_snapshot(self.processed_root, self.fallback_path)
        }
        return [
            context_by_id[group_id]
            for group_id in career_group_ids
            if group_id in context_by_id
        ]


def _require_columns(frame: pd.DataFrame, required: set[str], filename: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise MarketDataError(f"{filename} is missing columns: {', '.join(missing)}")


def load_fallback_market(path: Path = DEFAULT_FALLBACK_PATH) -> list[MarketCareerGroup]:
    records = json.loads(path.read_text(encoding="utf-8"))
    result = [MarketCareerGroup.model_validate(item) for item in records]
    return sorted(result, key=lambda item: item.career_group_id)


def build_market_snapshot(
    processed_root: Path = DEFAULT_PROCESSED_ROOT,
    fallback_path: Path = DEFAULT_FALLBACK_PATH,
) -> list[MarketCareerGroup]:
    try:
        frames = {
            name: pd.read_parquet(processed_root / name)
            for name in MARKET_OUTPUT_FILES
        }
        demand = frames["career_demand_summary.parquet"]
        matrix = frames["career_skill_matrix.parquet"]
        jobs = frames["jobs_clean.parquet"]
        job_skills = frames["job_skills.parquet"]
        _require_columns(
            demand,
            {"career_id", "posting_count", "snapshot_version"},
            "career_demand_summary.parquet",
        )
        _require_columns(
            matrix,
            {"career_id", "skill_id"},
            "career_skill_matrix.parquet",
        )
        _require_columns(
            jobs,
            {"career_id", "taxonomy_version"},
            "jobs_clean.parquet",
        )
        _require_columns(
            job_skills,
            {"career_id", "skill_id"},
            "job_skills.parquet",
        )
        groups = _build_pipeline_groups(demand, matrix, jobs, job_skills)
        if len(groups) != len(MARKET_GROUPS):
            raise MarketDataError("market mapping did not produce every configured career group")
        return groups
    except (OSError, ValueError, KeyError, ImportError, MarketDataError):
        return load_fallback_market(fallback_path)


def _build_pipeline_groups(
    demand: pd.DataFrame,
    matrix: pd.DataFrame,
    jobs: pd.DataFrame,
    job_skills: pd.DataFrame,
) -> list[MarketCareerGroup]:
    result: list[MarketCareerGroup] = []
    for group_id, mapping in sorted(MARKET_GROUPS.items()):
        source_ids = set(mapping["source_career_ids"])
        demand_rows = demand[demand["career_id"].isin(source_ids)]
        if demand_rows.empty:
            raise MarketDataError(f"no demand rows mapped for {group_id}")

        skill_ids = set(matrix[matrix["career_id"].isin(source_ids)]["skill_id"].dropna())
        skill_ids.update(
            job_skills[job_skills["career_id"].isin(source_ids)]["skill_id"].dropna()
        )
        foundation_skills = sorted(
            {
                MARKET_SKILL_TO_FOUNDATION[skill_id]
                for skill_id in skill_ids
                if skill_id in MARKET_SKILL_TO_FOUNDATION
            }
            & set(ALLOWED_FOUNDATION_SKILLS)
        )
        if not foundation_skills:
            raise MarketDataError(f"no student foundation skills mapped for {group_id}")

        snapshots = sorted(str(item) for item in demand_rows["snapshot_version"].dropna().unique())
        if not snapshots:
            raise MarketDataError(f"no snapshot version mapped for {group_id}")
        taxonomy_rows = jobs[jobs["career_id"].isin(source_ids)]["taxonomy_version"].dropna()
        taxonomy_versions = sorted(str(item) for item in taxonomy_rows.unique())
        sample_size = int(demand_rows["posting_count"].fillna(0).sum())
        mapped_ids = sorted(source_ids & set(demand_rows["career_id"].dropna()))
        market_signal = (
            f"{sample_size} lượt tin trong snapshot; mapping từ "
            f"{', '.join(mapped_ids)}."
        )
        result.append(
            MarketCareerGroup(
                career_group_id=group_id,
                display_name=mapping["display_name"],
                market_signal=market_signal,
                sample_size=sample_size,
                foundation_skill_ids=foundation_skills,
                snapshot_version=f"{snapshots[-1]}|{MARKET_GROUP_MAPPING_VERSION}",
                taxonomy_version=taxonomy_versions[-1] if taxonomy_versions else None,
                data_mode="pipeline_export",
                source_output_files=list(MARKET_OUTPUT_FILES),
            )
        )
    return result
