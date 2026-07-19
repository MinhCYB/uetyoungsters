from __future__ import annotations

import pandas as pd

from crawl_service.career_profiles import build_career_detail_tables, extract_typical_tasks


def test_extracts_tasks_only_from_responsibility_section():
    description = """
    <p><strong>Your daily tasks:</strong></p><ul>
      <li>Develop and maintain frontend services for customers</li>
      <li>Implement server-side rendering and monitoring solutions</li>
    </ul><p><strong>Your background:</strong></p><ul>
      <li>Five years of JavaScript experience is required</li>
    </ul>
    """
    assert extract_typical_tasks(description) == [
        "Develop and maintain frontend services for customers",
        "Implement server-side rendering and monitoring solutions",
    ]


def test_builds_evidence_facts_and_profile():
    jobs = pd.DataFrame([{
        "job_id": "job_1", "career_id": "CAREER_DATA_ANALYST", "job_title_raw": "Data Analyst",
        "company_name": "Example", "description_clean": "Analyze data and build reports.",
        "source": "fixture", "source_url": "https://example.test/job/1", "source_job_id": "1",
        "content_hash": "abc", "snapshot_version": "v1", "taxonomy_version": "0.4.0",
        "collected_at": pd.Timestamp("2026-07-19", tz="UTC"), "is_active": True,
        "lifecycle_status": "active", "work_mode": "HYBRID", "province": "Hà Nội",
        "salary_disclosed": True, "salary_mid_vnd": 15_000_000,
    }])
    skills = pd.DataFrame()
    demand = pd.DataFrame([{"career_id": "CAREER_DATA_ANALYST", "posting_count": 1}])
    matrix = pd.DataFrame([{
        "career_id": "CAREER_DATA_ANALYST", "skill_id": "SKILL_SQL", "skill_name": "SQL",
        "skill_posting_count": 1, "share_of_career_jobs": 1.0,
    }])
    taxonomy = {"taxonomy_version": "0.4.0", "careers": [{
        "career_id": "CAREER_DATA_ANALYST", "canonical_name": "Data Analyst", "aliases": []
    }]}
    evidence, facts, profiles = build_career_detail_tables(jobs, skills, demand, matrix, taxonomy)
    assert evidence.iloc[0]["source_url"] == "https://example.test/job/1"
    assert facts.iloc[0]["fact_key"] == "SKILL_SQL"
    profile = profiles.iloc[0]
    assert profile["detail_status"] == "available"
    assert profile["posting_count"] == 1
    assert profile["top_skills"][0]["skill_id"] == "SKILL_SQL"


def test_onet_tasks_are_used_as_the_occupation_baseline():
    jobs = pd.DataFrame(columns=["career_id"])
    taxonomy = {"taxonomy_version": "0.4.0", "careers": [{
        "career_id": "CAREER_DATA_ANALYST", "canonical_name": "Data Analyst", "aliases": []
    }]}
    onet = {"CAREER_DATA_ANALYST": {
        "version": "30.3", "map_version": "0.1.0",
        "occupations": [{"onetsoc_code": "15-2051.00", "title": "Data Scientists", "description": "Analyze data."}],
        "tasks": [{"onetsoc_code": "15-2051.00", "task_id": 1, "task": "Analyze large data sets.", "task_type": "Core"}],
        "interests": [{"Realistic": 2.0, "Investigative": 7.0, "Artistic": 3.0,
                       "Social": 2.5, "Enterprising": 3.5, "Conventional": 5.0}],
    }}
    evidence, _, profiles = build_career_detail_tables(
        jobs, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), taxonomy, onet_profiles=onet,
        vi_translations={"CAREER_DATA_ANALYST": {
            "overview_vi": "Phân tích dữ liệu.",
            "tasks": [{"id": "0", "text_vi": "Phân tích các tập dữ liệu lớn."}],
        }},
    )
    assert evidence.iloc[0]["source_type"] == "occupation_reference"
    assert profiles.iloc[0]["overview"] == "Analyze data."
    assert profiles.iloc[0]["typical_tasks"][0]["source_name"] == "O*NET 30.3"
    assert profiles.iloc[0]["typical_tasks"][0]["text_vi"] == "Phân tích các tập dữ liệu lớn."
    assert profiles.iloc[0]["riasec_code"] == "ICE"
    assert profiles.iloc[0]["riasec_scores"]["I"] == 7.0
