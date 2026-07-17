from __future__ import annotations

import hashlib
from .normalization import clean_text, match_text, normalize_company


def build_content_hash(
    title_raw: str,
    company_name_raw: str | None,
    location_raw: str | None,
    description_raw: str,
) -> str:
    canonical = "|".join([
        match_text(title_raw),
        normalize_company(company_name_raw),
        match_text(location_raw),
        match_text(description_raw),
    ])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_job_id(source: str, source_job_id: str | None, source_url: str | None, content_hash: str) -> str:
    seed = f"{source}|{source_job_id or source_url or content_hash}"
    return "job_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def build_dedup_group_id(content_hash: str) -> str:
    return "dup_" + content_hash[:16]
