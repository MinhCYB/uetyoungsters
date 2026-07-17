from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data.lifecycle import (
    update_job_lifecycle,
)


JOBS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "jobs_clean.parquet"
)

STATE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "job_lifecycle.parquet"
)


def main() -> None:
    jobs = pd.read_parquet(JOBS_PATH)

    current_jobs, lifecycle_state = (
        update_job_lifecycle(
            current_jobs=jobs,
            state_path=STATE_PATH,
            inactive_after_missing_runs=3,
        )
    )

    # Tạm thời cập nhật jobs_clean bằng bản có lifecycle.
    current_jobs.to_parquet(
        JOBS_PATH,
        index=False,
    )

    print(
        f"Current jobs: {len(current_jobs)}"
    )
    print(
        f"Lifecycle records: "
        f"{len(lifecycle_state)}"
    )

    print("\nLifecycle status:")
    print(
        lifecycle_state[
            "lifecycle_status"
        ].value_counts(dropna=False)
    )

    print("\nCurrent sample:")
    print(
        current_jobs[
            [
                "source_id",
                "source_job_id",
                "first_seen_at",
                "last_seen_at",
                "is_active",
                "consecutive_missing_runs",
                "content_changed",
                "lifecycle_status",
            ]
        ]
        .head()
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
