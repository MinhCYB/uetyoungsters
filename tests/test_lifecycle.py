from __future__ import annotations

import pandas as pd

from backend.data.lifecycle import (
    update_job_lifecycle,
)


def make_jobs(
    content_hash: str = "hash-v1",
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_id": "greenhouse_test",
                "source_job_id": "job-001",
                "content_hash_sha256": content_hash,
                "collected_at": "2026-07-17T10:00:00Z",
            }
        ]
    )


def make_empty_jobs() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "source_id",
            "source_job_id",
            "content_hash_sha256",
            "collected_at",
        ]
    )


def test_new_job_is_active(tmp_path):
    state_path = tmp_path / "lifecycle.parquet"

    current, state = update_job_lifecycle(
        current_jobs=make_jobs(),
        state_path=state_path,
        inactive_after_missing_runs=3,
        observed_at="2026-07-17T10:00:00Z",
    )

    assert len(current) == 1
    assert len(state) == 1

    row = state.iloc[0]

    assert bool(row["is_active"]) is True
    assert row["lifecycle_status"] == "active"
    assert row["consecutive_missing_runs"] == 0
    assert bool(row["content_changed"]) is False
    assert bool(row["reactivated"]) is False


def test_job_becomes_inactive_after_three_missing_runs(
    tmp_path,
):
    state_path = tmp_path / "lifecycle.parquet"

    update_job_lifecycle(
        current_jobs=make_jobs(),
        state_path=state_path,
        inactive_after_missing_runs=3,
        observed_at="2026-07-17T10:00:00Z",
    )

    _, state_1 = update_job_lifecycle(
        current_jobs=make_empty_jobs(),
        state_path=state_path,
        inactive_after_missing_runs=3,
        observed_at="2026-07-18T10:00:00Z",
    )

    row_1 = state_1.iloc[0]

    assert row_1["consecutive_missing_runs"] == 1
    assert row_1["lifecycle_status"] == (
        "missing_unconfirmed"
    )
    assert bool(row_1["is_active"]) is True

    _, state_2 = update_job_lifecycle(
        current_jobs=make_empty_jobs(),
        state_path=state_path,
        inactive_after_missing_runs=3,
        observed_at="2026-07-19T10:00:00Z",
    )

    row_2 = state_2.iloc[0]

    assert row_2["consecutive_missing_runs"] == 2
    assert row_2["lifecycle_status"] == (
        "missing_unconfirmed"
    )
    assert bool(row_2["is_active"]) is True

    _, state_3 = update_job_lifecycle(
        current_jobs=make_empty_jobs(),
        state_path=state_path,
        inactive_after_missing_runs=3,
        observed_at="2026-07-20T10:00:00Z",
    )

    row_3 = state_3.iloc[0]

    assert row_3["consecutive_missing_runs"] == 3
    assert row_3["lifecycle_status"] == "inactive"
    assert bool(row_3["is_active"]) is False
    assert pd.notna(row_3["inactive_at"])


def test_content_change_is_detected(tmp_path):
    state_path = tmp_path / "lifecycle.parquet"

    update_job_lifecycle(
        current_jobs=make_jobs("hash-v1"),
        state_path=state_path,
        observed_at="2026-07-17T10:00:00Z",
    )

    current, _ = update_job_lifecycle(
        current_jobs=make_jobs("hash-v2"),
        state_path=state_path,
        observed_at="2026-07-18T10:00:00Z",
    )

    row = current.iloc[0]

    assert bool(row["content_changed"]) is True
    assert row["previous_content_hash"] == "hash-v1"
    assert row["content_hash_sha256"] == "hash-v2"


def test_inactive_job_can_be_reactivated(tmp_path):
    state_path = tmp_path / "lifecycle.parquet"

    update_job_lifecycle(
        current_jobs=make_jobs(),
        state_path=state_path,
        inactive_after_missing_runs=1,
        observed_at="2026-07-17T10:00:00Z",
    )

    _, inactive_state = update_job_lifecycle(
        current_jobs=make_empty_jobs(),
        state_path=state_path,
        inactive_after_missing_runs=1,
        observed_at="2026-07-18T10:00:00Z",
    )

    assert bool(
        inactive_state.iloc[0]["is_active"]
    ) is False

    current, _ = update_job_lifecycle(
        current_jobs=make_jobs(),
        state_path=state_path,
        inactive_after_missing_runs=1,
        observed_at="2026-07-19T10:00:00Z",
    )

    row = current.iloc[0]

    assert bool(row["is_active"]) is True
    assert bool(row["reactivated"]) is True
    assert row["consecutive_missing_runs"] == 0
    assert row["lifecycle_status"] == "active"
    assert pd.isna(row["inactive_at"])
