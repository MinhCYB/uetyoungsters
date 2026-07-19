from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from crawl_service.database import PROCESSED_TABLE_FILES, _json_columns, database_schema, read_table


def test_database_schema_is_required(monkeypatch):
    monkeypatch.delenv("CRAWL_DATABASE_SCHEMA", raising=False)
    with pytest.raises(RuntimeError, match="CRAWL_DATABASE_SCHEMA is required"):
        database_schema()


def test_database_schema_rejects_unsafe_identifier(monkeypatch):
    monkeypatch.setenv("CRAWL_DATABASE_SCHEMA", "crawl;drop schema public")
    with pytest.raises(RuntimeError, match="lowercase SQL identifier"):
        database_schema()


def test_json_columns_detect_nested_values():
    dataframe = pd.DataFrame({
        "job_id": ["job_1"],
        "raw_payload": [{"source": "fixture"}],
        "aliases": [["one", "two"]],
        "arrow_list": [np.array(["three", "four"], dtype=object)],
    })
    assert _json_columns(dataframe) == ["raw_payload", "aliases", "arrow_list"]


def test_read_table_rejects_unknown_table_before_connecting():
    with pytest.raises(ValueError, match="Unsupported crawl warehouse table"):
        read_table("users")


def test_processed_table_registry_contains_runtime_consumer_tables():
    assert set(PROCESSED_TABLE_FILES) == {
        "jobs_clean",
        "job_skills",
        "job_lifecycle",
        "career_demand_summary",
        "career_skill_matrix",
        "career_evidence",
        "career_evidence_facts",
        "career_profiles",
    }
