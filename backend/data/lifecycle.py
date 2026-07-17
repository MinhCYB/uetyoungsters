from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


KEY_COLUMNS = [
    "source_id",
    "source_job_id",
]

DEFAULT_HASH_COLUMN = "content_hash_sha256"


def to_utc_timestamp(value: Any) -> pd.Timestamp | pd.NaT:
    if value is None or pd.isna(value):
        return pd.NaT

    timestamp = pd.Timestamp(value)

    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")

    return timestamp.tz_convert("UTC")


def resolve_observed_at(
    dataframe: pd.DataFrame,
    observed_at: Any = None,
) -> pd.Timestamp:
    if observed_at is not None:
        timestamp = to_utc_timestamp(observed_at)

        if pd.isna(timestamp):
            raise ValueError("observed_at không hợp lệ.")

        return timestamp

    for column in ["collected_at", "last_seen_at"]:
        if column not in dataframe.columns:
            continue

        values = pd.to_datetime(
            dataframe[column],
            errors="coerce",
            utc=True,
        ).dropna()

        if not values.empty:
            return values.max()

    return pd.Timestamp.now(tz="UTC")


def validate_current_jobs(
    dataframe: pd.DataFrame,
    hash_column: str,
) -> None:
    required_columns = {
        *KEY_COLUMNS,
        hash_column,
    }

    missing_columns = (
        required_columns - set(dataframe.columns)
    )

    if missing_columns:
        raise KeyError(
            f"Thiếu các cột bắt buộc: "
            f"{sorted(missing_columns)}"
        )

    for column in KEY_COLUMNS:
        if dataframe[column].isna().any():
            raise ValueError(
                f"Cột {column} chứa giá trị null."
            )


def prepare_keys(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    dataframe = dataframe.copy()

    for column in KEY_COLUMNS:
        dataframe[column] = (
            dataframe[column]
            .astype("string")
            .str.strip()
        )

    return dataframe


def job_key(record: dict[str, Any]) -> tuple[str, str]:
    return (
        str(record["source_id"]),
        str(record["source_job_id"]),
    )


def update_job_lifecycle(
    current_jobs: pd.DataFrame,
    state_path: str | Path,
    *,
    inactive_after_missing_runs: int = 3,
    hash_column: str = DEFAULT_HASH_COLUMN,
    observed_at: Any = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Cập nhật vòng đời của các tin tuyển dụng.

    Trả về:
    - current_enriched: các tin xuất hiện trong lần crawl hiện tại;
    - lifecycle_state: toàn bộ tin từng quan sát, gồm cả tin đã mất.
    """
    if inactive_after_missing_runs < 1:
        raise ValueError(
            "inactive_after_missing_runs phải >= 1."
        )

    validate_current_jobs(
        current_jobs,
        hash_column,
    )

    current = prepare_keys(current_jobs)

    current = (
        current
        .drop_duplicates(
            subset=KEY_COLUMNS,
            keep="last",
        )
        .reset_index(drop=True)
    )

    checked_at = resolve_observed_at(
        current,
        observed_at,
    )

    state_path = Path(state_path)

    if state_path.exists():
        previous_state = pd.read_parquet(
            state_path
        )
        previous_state = prepare_keys(
            previous_state
        )
    else:
        previous_state = pd.DataFrame()

    previous_lookup: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    if not previous_state.empty:
        for record in previous_state.to_dict(
            orient="records"
        ):
            previous_lookup[
                job_key(record)
            ] = record

    current_records: list[dict[str, Any]] = []
    current_keys: set[tuple[str, str]] = set()

    for record in current.to_dict(orient="records"):
        key = job_key(record)
        current_keys.add(key)

        previous = previous_lookup.get(key)
        current_hash = record.get(hash_column)

        if previous is None:
            first_seen_at = to_utc_timestamp(
                record.get("first_seen_at")
            )

            if pd.isna(first_seen_at):
                first_seen_at = to_utc_timestamp(
                    record.get("collected_at")
                )

            if pd.isna(first_seen_at):
                first_seen_at = checked_at

            previous_hash = None
            content_changed = False
            reactivated = False

        else:
            first_seen_at = to_utc_timestamp(
                previous.get("first_seen_at")
            )

            if pd.isna(first_seen_at):
                first_seen_at = checked_at

            previous_hash = previous.get(
                hash_column
            )

            content_changed = bool(
                previous_hash
                and current_hash
                and previous_hash != current_hash
            )

            previous_is_active = previous.get(
                "is_active",
                True,
            )

            reactivated = (
                False
                if pd.isna(previous_is_active)
                else not bool(previous_is_active)
            )

        record.update(
            {
                "first_seen_at": first_seen_at,
                "last_seen_at": checked_at,
                "last_checked_at": checked_at,
                "is_active": True,
                "consecutive_missing_runs": 0,
                "content_changed": content_changed,
                "previous_content_hash": (
                    previous_hash
                ),
                "inactive_at": pd.NaT,
                "lifecycle_status": "active",
                "reactivated": reactivated,
            }
        )

        current_records.append(record)

    missing_records: list[dict[str, Any]] = []

    for key, previous in previous_lookup.items():
        if key in current_keys:
            continue

        record = dict(previous)

        previous_missing_runs = record.get(
            "consecutive_missing_runs",
            0,
        )

        if pd.isna(previous_missing_runs):
            previous_missing_runs = 0

        missing_runs = (
            int(previous_missing_runs) + 1
        )

        is_inactive = (
            missing_runs
            >= inactive_after_missing_runs
        )

        previous_inactive_at = to_utc_timestamp(
            record.get("inactive_at")
        )

        if is_inactive:
            inactive_at = (
                previous_inactive_at
                if not pd.isna(previous_inactive_at)
                else checked_at
            )
            lifecycle_status = "inactive"
        else:
            inactive_at = pd.NaT
            lifecycle_status = (
                "missing_unconfirmed"
            )

        record.update(
            {
                "last_checked_at": checked_at,
                "consecutive_missing_runs": (
                    missing_runs
                ),
                "is_active": not is_inactive,
                "content_changed": False,
                "inactive_at": inactive_at,
                "lifecycle_status": (
                    lifecycle_status
                ),
                "reactivated": False,
            }
        )

        missing_records.append(record)

    current_enriched = pd.DataFrame(
        current_records
    )

    lifecycle_state = pd.DataFrame(
        current_records + missing_records
    )

    lifecycle_state = (
        lifecycle_state
        .sort_values(KEY_COLUMNS)
        .reset_index(drop=True)
    )

    state_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lifecycle_state.to_parquet(
        state_path,
        index=False,
    )

    return current_enriched, lifecycle_state
