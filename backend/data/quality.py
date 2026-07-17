from __future__ import annotations

import json
from pathlib import Path
import pandas as pd


def create_quality_report(jobs_path: str | Path, output_path: str | Path) -> dict:
    jobs = pd.read_parquet(jobs_path)
    total = len(jobs)

    report = {
        "total_rows": total,
        "unique_content_hashes": int(jobs["content_hash"].nunique()),
        "duplicate_rows": int(total - jobs["content_hash"].nunique()),
        "mapped_career_rows": int(jobs["career_id"].notna().sum()),
        "mapped_location_rows": int(jobs["province"].notna().sum()),
        "salary_disclosed_rows": int(jobs["salary_disclosed"].sum()),
        "average_extraction_confidence": (
            round(float(jobs["overall_confidence"].mean()), 3) if total else None
        ),
        "sources": sorted(jobs["source"].dropna().unique().tolist()),
        "snapshot_versions": sorted(jobs["snapshot_version"].dropna().unique().tolist()),
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report
