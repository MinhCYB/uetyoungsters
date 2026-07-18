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


def build_cross_source_dedup_key(
    title: str,
    company: str | None,
    province: str | None,
) -> str | None:
    """Return a conservative candidate key; it never merges records itself."""
    normalized_company = normalize_company(company)
    normalized_title = match_text(title)
    normalized_province = match_text(province)

    if not all(
        [normalized_company, normalized_title, normalized_province]
    ):
        return None

    return "|".join(
        [normalized_company, normalized_title, normalized_province]
    )
