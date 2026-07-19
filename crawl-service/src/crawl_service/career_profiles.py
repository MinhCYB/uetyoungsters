"""Build evidence-backed career detail datasets from market outputs."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import re
import pandas as pd
from bs4 import BeautifulSoup
import yaml


def _records(frame: pd.DataFrame, columns: list[str], limit: int) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    selected = frame[[c for c in columns if c in frame.columns]].head(limit).copy()
    return selected.astype(object).where(pd.notna(selected), None).to_dict(orient="records")


_TASK_HEADINGS = (
    "responsibilities", "responsibility", "your daily tasks", "daily tasks",
    "what you will do", "what you'll do", "what you’ll do", "the role",
    "job description", "role description", "mô tả công việc", "nhiệm vụ",
    "trách nhiệm", "công việc của bạn",
)
_STOP_HEADINGS = (
    "requirements", "qualifications", "your background", "what you need",
    "who you are", "skills", "experience", "benefits", "why join",
    "yêu cầu", "quyền lợi", "phúc lợi", "kinh nghiệm",
)


def _is_heading(tag) -> bool:
    if not getattr(tag, "name", None):
        return False
    if tag.name in {"h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"}:
        return True
    return tag.name == "p" and tag.find(["strong", "b"]) is not None


def extract_typical_tasks(description: str | None, limit: int = 8) -> list[str]:
    """Extract responsibility bullets, excluding requirements and benefits."""
    if not description:
        return []
    soup = BeautifulSoup(description, "lxml")
    tasks: list[str] = []
    collecting = False
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "strong", "b", "li"]):
        item_text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip(" •-–—\t")
        if not item_text:
            continue
        lowered = item_text.lower().strip(" :")
        if _is_heading(tag):
            if any(marker in lowered for marker in _TASK_HEADINGS):
                collecting = True
                continue
            if collecting and any(marker in lowered for marker in _STOP_HEADINGS):
                collecting = False
                continue
        if collecting and tag.name == "li" and 12 <= len(item_text) <= 350:
            key = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
            if key and all(re.sub(r"[^a-z0-9]+", " ", item.lower()).strip() != key for item in tasks):
                tasks.append(item_text)
                if len(tasks) >= limit:
                    break
    return tasks


def load_onet_profiles(project_root: Path) -> dict[str, dict[str, Any]]:
    """Load O*NET data through the explicit, reviewable career mapping."""
    mapping_path = project_root / "config" / "onet_career_map.yaml"
    if not mapping_path.is_file():
        return {}
    mapping = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
    version = str(mapping["onet_version"])
    root = project_root / "data" / "raw" / "onet" / version
    occupation_path, tasks_path = root / "occupation_data.json", root / "task_statements.json"
    interests_path = root / "career_interest_types.json"
    essential_path = root / "essential_skills.json"
    transferable_path = root / "transferable_skills.json"
    software_path = root / "software_skills.json"
    required = (occupation_path, tasks_path, interests_path, essential_path, transferable_path, software_path)
    if not all(path.is_file() for path in required):
        return {}
    occupations = {row["onetsoc_code"]: row for row in json.loads(
        occupation_path.read_text(encoding="utf-8")
    )["row"]}
    tasks_by_code: dict[str, list[dict[str, Any]]] = {}
    for row in json.loads(tasks_path.read_text(encoding="utf-8"))["row"]:
        tasks_by_code.setdefault(row["onetsoc_code"], []).append(row)
    interests_by_code: dict[str, dict[str, float]] = {}
    for row in json.loads(interests_path.read_text(encoding="utf-8"))["row"]:
        if row.get("scale_id") == "OI":
            interests_by_code.setdefault(row["onetsoc_code"], {})[row["element_name"]] = float(row["data_value"])
    rated_skills_by_code: dict[str, dict[str, dict[str, Any]]] = {}
    for path, skill_type in ((essential_path, "essential"), (transferable_path, "transferable")):
        for row in json.loads(path.read_text(encoding="utf-8"))["row"]:
            if row.get("recommend_suppress") == "Y" or row.get("not_relevant") == "Y":
                continue
            item = rated_skills_by_code.setdefault(row["onetsoc_code"], {}).setdefault(
                row["element_id"],
                {"element_id": row["element_id"], "name": row["element_name"], "skill_type": skill_type},
            )
            if row.get("scale_id") == "IM":
                item["importance"] = float(row["data_value"])
            elif row.get("scale_id") == "LV":
                item["level"] = float(row["data_value"])
    software_by_code: dict[str, list[dict[str, Any]]] = {}
    for row in json.loads(software_path.read_text(encoding="utf-8"))["row"]:
        software_by_code.setdefault(row["onetsoc_code"], []).append({
            "name": row["workplace_example"], "category": row.get("element_name"),
            "hot_technology": row.get("hot_technology") == "Y",
            "in_demand": row.get("in_demand") == "Y",
        })
    profiles = {}
    for career_id, codes in mapping.get("mappings", {}).items():
        selected_occupations = [occupations[code] for code in codes if code in occupations]
        selected_tasks = [task for code in codes for task in tasks_by_code.get(code, [])]
        selected_tasks.sort(key=lambda item: (item.get("task_type") != "Core", item.get("task_id", 0)))
        profiles[career_id] = {
            "version": version, "map_version": str(mapping["version"]),
            "source_url": mapping["source_url"], "occupations": selected_occupations,
            "tasks": selected_tasks,
            "interests": [interests_by_code[code] for code in codes if code in interests_by_code],
            "rated_skills": [item for code in codes for item in rated_skills_by_code.get(code, {}).values()],
            "software_skills": [item for code in codes for item in software_by_code.get(code, [])],
        }
    return profiles


def load_vi_translations(project_root: Path) -> dict[str, dict[str, Any]]:
    path = project_root / "data" / "interim" / "career_profile_vi.json"
    if not path.is_file():
        path = project_root / "data" / "interim" / "career_profile_vi.partial.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {item["career_id"]: item for item in payload.get("careers", [])}


def build_career_detail_tables(
    jobs, skills, demand, skill_matrix, taxonomy, onet_profiles=None, vi_translations=None
):
    generated_at = datetime.now(timezone.utc)
    taxonomy_version = str(taxonomy["taxonomy_version"])
    active = jobs.copy()
    if "is_active" in active:
        active = active[active["is_active"].fillna(False)]
    if "lifecycle_status" in active:
        active = active[active["lifecycle_status"] != "invalid"]
    active = active[active["career_id"].notna()]
    onet_profiles = onet_profiles or {}
    vi_translations = vi_translations or {}

    evidence_rows = []
    for row in active.to_dict(orient="records"):
        content = str(row.get("description_clean") or "").strip()
        if content:
            evidence_rows.append({
                "evidence_id": f"job:{row['job_id']}", "career_id": row["career_id"],
                "source_name": row.get("source"), "source_type": "job_posting",
                "source_url": row.get("source_url"), "source_record_id": row.get("source_job_id"),
                "title": row.get("job_title_raw"), "content": content,
                "content_hash": row.get("content_hash"), "snapshot_version": row.get("snapshot_version"),
                "taxonomy_version": taxonomy_version, "collected_at": row.get("collected_at"),
                "is_active": True,
            })
    for career_id, profile in onet_profiles.items():
        for occupation in profile["occupations"]:
            code = occupation["onetsoc_code"]
            occupation_tasks = [item["task"] for item in profile["tasks"] if item["onetsoc_code"] == code]
            evidence_rows.append({
                "evidence_id": f"onet:{profile['version']}:{code}", "career_id": career_id,
                "source_name": f"O*NET {profile['version']} Database", "source_type": "occupation_reference",
                "source_url": f"https://www.onetonline.org/link/summary/{code}", "source_record_id": code,
                "title": occupation["title"], "content": occupation["description"] + "\n" + "\n".join(occupation_tasks),
                "content_hash": None, "snapshot_version": f"onet-{profile['version']}",
                "taxonomy_version": taxonomy_version, "collected_at": None, "is_active": True,
            })
    evidence_columns = ["evidence_id", "career_id", "source_name", "source_type", "source_url",
                        "source_record_id", "title", "content", "content_hash", "snapshot_version",
                        "taxonomy_version", "collected_at", "is_active"]
    evidence = pd.DataFrame(evidence_rows, columns=evidence_columns)

    fact_rows = []
    for row in skill_matrix.to_dict(orient="records"):
        if pd.notna(row.get("career_id")) and pd.notna(row.get("skill_id")):
            fact_rows.append({
                "career_id": row["career_id"], "fact_type": "market_skill",
                "fact_key": row["skill_id"], "fact_label": row.get("skill_name"),
                "numeric_value": row.get("share_of_career_jobs"),
                "sample_size": row.get("skill_posting_count"),
                "snapshot_version": None, "taxonomy_version": taxonomy_version,
                "generated_at": generated_at,
            })
    for career_id, profile in onet_profiles.items():
        interest_sets = profile.get("interests", [])
        if not interest_sets:
            continue
        for dimension in ("Realistic", "Investigative", "Artistic", "Social", "Enterprising", "Conventional"):
            values = [item[dimension] for item in interest_sets if dimension in item]
            if values:
                fact_rows.append({
                    "career_id": career_id, "fact_type": "riasec_score",
                    "fact_key": dimension[0], "fact_label": dimension,
                    "numeric_value": round(sum(values) / len(values), 3),
                    "sample_size": len(values), "snapshot_version": f"onet-{profile['version']}",
                    "taxonomy_version": taxonomy_version, "generated_at": generated_at,
                })
    fact_columns = ["career_id", "fact_type", "fact_key", "fact_label", "numeric_value",
                    "sample_size", "snapshot_version", "taxonomy_version", "generated_at"]
    facts = pd.DataFrame(fact_rows, columns=fact_columns)

    profiles = []
    for career in taxonomy.get("careers", []):
        career_id, title = career["career_id"], career["canonical_name"]
        career_jobs = active[active["career_id"] == career_id]
        career_demand = demand[demand["career_id"] == career_id] if not demand.empty else demand
        career_skills = skill_matrix[skill_matrix["career_id"] == career_id].copy() if not skill_matrix.empty else skill_matrix
        if not career_skills.empty:
            career_skills = career_skills.sort_values("skill_posting_count", ascending=False).drop_duplicates("skill_id")
        posting_count = int(career_jobs["job_id"].nunique()) if not career_jobs.empty else 0
        company_count = int(career_jobs["company_name"].nunique()) if not career_jobs.empty else 0
        evidence_count = int((evidence["career_id"] == career_id).sum()) if not evidence.empty else 0
        typical_tasks = []
        seen_tasks = set()
        onet_profile = onet_profiles.get(career_id)
        riasec_scores = {}
        if onet_profile:
            for dimension in ("Realistic", "Investigative", "Artistic", "Social", "Enterprising", "Conventional"):
                values = [item[dimension] for item in onet_profile.get("interests", []) if dimension in item]
                if values:
                    riasec_scores[dimension[0]] = round(sum(values) / len(values), 3)
        riasec_code = "".join(key for key, _ in sorted(riasec_scores.items(), key=lambda item: item[1], reverse=True)[:3])
        top_skills = _records(
            career_skills,
            ["skill_id", "skill_name", "skill_posting_count", "share_of_career_jobs"],
            10,
        )
        for item in top_skills:
            item["source_type"] = "job_posting"
        if not top_skills and onet_profile:
            # O*NET's in-demand flag is derived from employer postings for this occupation.
            preferred_tools = (
                "sql", "python", "tableau", "power bi", "excel", " r ",
                "javascript", "react", "git", "amazon web services", "azure", "adobe",
            )
            def software_rank(item):
                padded_name = f" {item['name'].casefold()} "
                preferred = next(
                    (index for index, marker in enumerate(preferred_tools) if marker in padded_name),
                    len(preferred_tools),
                )
                return (not item.get("in_demand"), preferred, not item.get("hot_technology"), item["name"])
            software = sorted(
                onet_profile.get("software_skills", []),
                key=software_rank,
            )
            seen = set()
            for item in software:
                key = item["name"].casefold()
                if key in seen or not (item.get("in_demand") or item.get("hot_technology")):
                    continue
                seen.add(key)
                top_skills.append({
                    "skill_id": "ONET_SOFTWARE_" + re.sub(r"[^A-Z0-9]+", "_", item["name"].upper()).strip("_"),
                    "skill_name": item["name"], "source_type": "onet_software",
                    "in_demand": item.get("in_demand", False),
                    "hot_technology": item.get("hot_technology", False),
                    "category": item.get("category"),
                })
                if len(top_skills) >= 6:
                    break
            rated = sorted(
                (item for item in onet_profile.get("rated_skills", []) if item.get("importance") is not None),
                key=lambda item: item["importance"], reverse=True,
            )
            for item in rated:
                if len(top_skills) >= 10:
                    break
                key = item["name"].casefold()
                if key in seen:
                    continue
                seen.add(key)
                top_skills.append({
                    "skill_id": f"ONET_{item['element_id'].replace('.', '_')}",
                    "skill_name": item["name"], "source_type": "onet_rating",
                    "importance_score": item["importance"], "level_score": item.get("level"),
                    "skill_type": item.get("skill_type"),
                })
        for job in career_jobs.to_dict(orient="records"):
            description = job.get("description_role_specific") or job.get("description_raw") or job.get("description_clean")
            for task in extract_typical_tasks(description):
                key = re.sub(r"\W+", " ", task.lower()).strip()
                if key in seen_tasks:
                    continue
                seen_tasks.add(key)
                typical_tasks.append({
                    "text": task, "evidence_id": f"job:{job['job_id']}",
                    "source_url": job.get("source_url"), "source_name": job.get("source"),
                })
                if len(typical_tasks) >= 10:
                    break
            if len(typical_tasks) >= 10:
                break
        if onet_profile and len(typical_tasks) < 10:
            for task in onet_profile["tasks"]:
                task_text = task["task"].strip()
                key = re.sub(r"\W+", " ", task_text.lower()).strip()
                if key in seen_tasks:
                    continue
                seen_tasks.add(key)
                typical_tasks.append({
                    "text": task_text,
                    "evidence_id": f"onet:{onet_profile['version']}:{task['onetsoc_code']}",
                    "source_url": f"https://www.onetonline.org/link/summary/{task['onetsoc_code']}",
                    "source_name": f"O*NET {onet_profile['version']}",
                    "task_type": task.get("task_type"),
                })
                if len(typical_tasks) >= 10:
                    break
        translation = vi_translations.get(career_id, {})
        translated_tasks = {
            str(item.get("id")): item.get("text_vi") or item.get("text")
            for item in translation.get("tasks", [])
        }
        for index, task in enumerate(typical_tasks):
            translated_text = translated_tasks.get(str(index))
            if translated_text:
                task["text_vi"] = translated_text
        salary_values = pd.Series(dtype="float")
        if not career_jobs.empty and {"salary_disclosed", "salary_mid_vnd"} <= set(career_jobs):
            salary_values = career_jobs.loc[career_jobs["salary_disclosed"].fillna(False), "salary_mid_vnd"].dropna()
        onet_description = " ".join(
            item["description"] for item in (onet_profile or {}).get("occupations", [])
        )
        overview = onet_description or ((
            f"Hồ sơ thị trường của {title} được tổng hợp từ {posting_count} tin tuyển dụng "
            f"tại {company_count} doanh nghiệp trong các nguồn đang theo dõi."
        ) if posting_count else (
            f"Chưa có đủ bằng chứng tuyển dụng hiện hành để mô tả chi tiết nghề {title}."
        ))
        profiles.append({
            "career_id": career_id, "title": title, "aliases": career.get("aliases", []),
            "overview": overview, "overview_vi": translation.get("overview_vi"),
            "top_skills": top_skills,
            "work_modes": sorted(career_jobs["work_mode"].dropna().astype(str).unique().tolist()) if not career_jobs.empty else [],
            "provinces": sorted(career_jobs["province"].dropna().astype(str).unique().tolist()) if not career_jobs.empty else [],
            "market_breakdown": _records(career_demand.sort_values("posting_count", ascending=False) if not career_demand.empty else career_demand,
                                         ["province", "work_mode", "posting_count", "unique_company_count", "salary_median_vnd", "salary_sample_size", "snapshot_version"], 20),
            "typical_tasks": typical_tasks, "posting_count": posting_count, "company_count": company_count,
            "riasec_scores": riasec_scores, "riasec_code": riasec_code,
            "salary_median_vnd": float(salary_values.median()) if not salary_values.empty else None,
            "salary_sample_size": len(salary_values), "evidence_count": evidence_count,
            "detail_status": "available" if evidence_count else "insufficient_evidence",
            "profile_version": f"{taxonomy_version}:{generated_at.date().isoformat()}",
            "taxonomy_version": taxonomy_version, "generated_at": generated_at,
        })
    return evidence, facts, pd.DataFrame(profiles)


def write_career_detail_outputs(jobs_path, skills_path, demand_path, skill_matrix_path, taxonomy, output_dir):
    output_root = Path(output_dir)
    project_root = output_root.parents[1]
    tables = build_career_detail_tables(pd.read_parquet(jobs_path), pd.read_parquet(skills_path),
        pd.read_parquet(demand_path), pd.read_parquet(skill_matrix_path), taxonomy,
        onet_profiles=load_onet_profiles(project_root),
        vi_translations=load_vi_translations(project_root))
    root = Path(output_dir); root.mkdir(parents=True, exist_ok=True)
    for name, frame in zip(("career_evidence", "career_evidence_facts", "career_profiles"), tables):
        frame.to_parquet(root / f"{name}.parquet", index=False)
    return tables
