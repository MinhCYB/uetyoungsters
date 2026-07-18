"""Postgres persistence for canonical crawl-service warehouse tables."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np

from .paths import PROCESSED_DIR


PROCESSED_TABLE_FILES = {
    "jobs_clean": "jobs_clean.parquet",
    "job_skills": "job_skills.parquet",
    "job_lifecycle": "job_lifecycle.parquet",
    "career_demand_summary": "career_demand_summary.parquet",
    "career_skill_matrix": "career_skill_matrix.parquet",
    "career_evidence": "career_evidence.parquet",
    "career_evidence_facts": "career_evidence_facts.parquet",
    "career_profiles": "career_profiles.parquet",
}

INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS ix_crawl_jobs_career ON {schema}.jobs_clean (career_id)",
    "CREATE INDEX IF NOT EXISTS ix_crawl_jobs_source ON {schema}.jobs_clean (source_id, source_job_id)",
    "CREATE INDEX IF NOT EXISTS ix_crawl_jobs_active ON {schema}.jobs_clean (is_active)",
    "CREATE INDEX IF NOT EXISTS ix_crawl_skills_career ON {schema}.job_skills (career_id, skill_id)",
    "CREATE INDEX IF NOT EXISTS ix_crawl_lifecycle_source ON {schema}.job_lifecycle (source_id, source_job_id)",
    "CREATE INDEX IF NOT EXISTS ix_crawl_demand_career ON {schema}.career_demand_summary (career_id)",
    "CREATE INDEX IF NOT EXISTS ix_crawl_matrix_career ON {schema}.career_skill_matrix (career_id, skill_id)",
    "CREATE INDEX IF NOT EXISTS ix_crawl_evidence_career ON {schema}.career_evidence (career_id)",
    "CREATE INDEX IF NOT EXISTS ix_crawl_facts_career ON {schema}.career_evidence_facts (career_id, fact_type)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_crawl_profiles_career ON {schema}.career_profiles (career_id)",
)


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for crawl-service database persistence")
    return value


def database_schema() -> str:
    schema = _required_environment("CRAWL_DATABASE_SCHEMA")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
        raise RuntimeError("CRAWL_DATABASE_SCHEMA must be a lowercase SQL identifier")
    return schema


def _json_value(value):
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _json_columns(dataframe: pd.DataFrame) -> list[str]:
    columns = []
    for column in dataframe.columns:
        if not pd.api.types.is_object_dtype(dataframe[column].dtype):
            continue
        values = dataframe[column].dropna()
        if any(isinstance(value, (dict, list, tuple, np.ndarray)) for value in values.head(100)):
            columns.append(column)
    return columns


def _engine():
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:
        raise RuntimeError(
            "SQLAlchemy is required; install crawl-service dependencies"
        ) from exc
    return create_engine(_required_environment("DATABASE_URL"), pool_pre_ping=True)


def publish_dataframes(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Atomically replace the canonical warehouse snapshot in Postgres."""
    unknown = set(tables) - set(PROCESSED_TABLE_FILES)
    if unknown:
        raise ValueError(f"Unsupported crawl warehouse tables: {sorted(unknown)}")

    from sqlalchemy import JSON, text

    schema = database_schema()
    published_at = datetime.now(timezone.utc)
    manifest_rows = []

    with _engine().begin() as connection:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        for table_name, dataframe in tables.items():
            json_types = {column: JSON for column in _json_columns(dataframe)}
            dataframe = dataframe.copy()
            for column in json_types:
                dataframe[column] = dataframe[column].map(_json_value)
            dataframe.to_sql(
                table_name,
                con=connection,
                schema=schema,
                if_exists="replace",
                index=False,
                dtype=json_types,
                method="multi",
                chunksize=500,
            )
            versions = []
            if "snapshot_version" in dataframe.columns:
                versions = sorted(
                    dataframe["snapshot_version"].dropna().astype(str).unique().tolist()
                )
            manifest_rows.append({
                "dataset_name": table_name,
                "row_count": len(dataframe),
                "snapshot_versions": versions,
                "published_at": published_at,
            })

        manifest = pd.DataFrame(manifest_rows)
        manifest.to_sql(
            "warehouse_manifest",
            con=connection,
            schema=schema,
            if_exists="replace",
            index=False,
            dtype={"snapshot_versions": JSON},
        )
        for statement in INDEX_STATEMENTS:
            connection.execute(text(statement.format(schema=schema)))

    return manifest


def publish_processed_outputs(processed_dir: str | Path = PROCESSED_DIR) -> pd.DataFrame:
    """Load canonical Parquet outputs and publish all of them to Postgres."""
    root = Path(processed_dir)
    missing = [filename for filename in PROCESSED_TABLE_FILES.values() if not (root / filename).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing processed datasets for database publish: {missing}")
    tables = {
        table_name: pd.read_parquet(root / filename)
        for table_name, filename in PROCESSED_TABLE_FILES.items()
    }
    return publish_dataframes(tables)


def read_table(table_name: str) -> pd.DataFrame:
    """Read one canonical crawl dataset from Postgres as a DataFrame."""
    if table_name not in {*PROCESSED_TABLE_FILES, "warehouse_manifest"}:
        raise ValueError(f"Unsupported crawl warehouse table: {table_name}")
    return pd.read_sql_table(table_name, con=_engine(), schema=database_schema())
