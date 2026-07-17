from __future__ import annotations

from pathlib import Path
import pandas as pd


def build_demand_summary(
    jobs_path: str | Path,
    skills_path: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    jobs = pd.read_parquet(jobs_path)
    skills = pd.read_parquet(skills_path)

    # Một tin đại diện cho mỗi content_hash.
    jobs = jobs.sort_values("collected_at").drop_duplicates("content_hash", keep="first")
    valid_jobs = jobs.dropna(subset=["career_id", "province"])

    base = (
    valid_jobs.groupby(
        [
            "career_id",
            "career_name",
            "province",
            "snapshot_version",
        ],
        as_index=False,
    )
    .agg(
        posting_count=("job_id", "count"),
        unique_company_count=("company_name", "nunique"),
        salary_median_vnd=("salary_mid_vnd", "median"),
        salary_sample_size=("salary_mid_vnd", "count"),
        average_confidence=("overall_confidence", "mean"),
        data_from=("posted_at", "min"),
        data_to=("posted_at", "max"),
    )
)

    if skills.empty:
        skill_counts = pd.DataFrame(
            columns=[
                "career_id",
                "province",
                "skill_id",
                "skill_name",
                "skill_posting_count",
                "posting_count",
                "share_of_career_jobs",
            ]
        )
    else:
        skill_counts = (
            skills[skills["requirement_level"].isin(["required", "preferred"])]
            .drop_duplicates(["dedup_group_id", "skill_id"])
            .groupby(
                ["career_id", "province", "skill_id", "skill_name"],
                as_index=False,
            )
            .agg(skill_posting_count=("dedup_group_id", "nunique"))
        )

    if not skill_counts.empty:
        skill_counts = skill_counts.merge(
            base[["career_id", "province", "posting_count"]],
            on=["career_id", "province"],
            how="left",
        )
        skill_counts["share_of_career_jobs"] = (
            skill_counts["skill_posting_count"] / skill_counts["posting_count"]
        )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    base.to_parquet(output_path, index=False)

    skill_matrix_path = Path(output_path).with_name("career_skill_matrix.parquet")
    skill_counts.to_parquet(skill_matrix_path, index=False)

    return base
