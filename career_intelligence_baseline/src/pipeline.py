from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd


def normalize_text(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def load_taxonomy(path: str | Path) -> Dict[str, List[str]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_skills(text: str, taxonomy: Dict[str, List[str]]) -> List[str]:
    normalized = normalize_text(text)
    found = []
    for canonical_skill, aliases in taxonomy.items():
        if any(normalize_text(alias) in normalized for alias in aliases):
            found.append(canonical_skill)
    return sorted(set(found))


def preprocess_jobs(
    jobs_path: str | Path,
    taxonomy_path: str | Path,
) -> pd.DataFrame:
    jobs = pd.read_csv(jobs_path)
    taxonomy = load_taxonomy(taxonomy_path)

    jobs["text"] = (
        jobs["title"].fillna("") + " " + jobs["description"].fillna("")
    )
    jobs["skills"] = jobs["text"].apply(lambda x: extract_skills(x, taxonomy))
    jobs["salary_mid"] = (
        pd.to_numeric(jobs["salary_min"], errors="coerce")
        + pd.to_numeric(jobs["salary_max"], errors="coerce")
    ) / 2
    jobs["posted_date"] = pd.to_datetime(jobs["posted_date"], errors="coerce")
    jobs["month"] = jobs["posted_date"].dt.to_period("M").astype(str)
    return jobs


def build_market_signals(jobs: pd.DataFrame) -> pd.DataFrame:
    exploded = jobs.explode("skills").dropna(subset=["skills"])
    signals = (
        exploded.groupby(["skills", "location"], as_index=False)
        .agg(
            posting_count=("job_id", "count"),
            avg_salary=("salary_mid", "mean"),
            latest_post=("posted_date", "max"),
        )
        .sort_values(["posting_count", "avg_salary"], ascending=False)
    )
    return signals
