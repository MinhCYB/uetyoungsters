from pathlib import Path

from src.pipeline import preprocess_jobs
from src.recommender import load_career_profiles, recommend_careers


ROOT = Path(__file__).resolve().parents[1]


def test_skill_extraction():
    jobs = preprocess_jobs(
        ROOT / "data" / "raw" / "jobs.csv",
        ROOT / "data" / "skill_taxonomy.json",
    )
    assert "sql" in jobs.loc[jobs["job_id"] == 1, "skills"].iloc[0]


def test_sensitive_fields_do_not_change_recommendation():
    jobs = preprocess_jobs(
        ROOT / "data" / "raw" / "jobs.csv",
        ROOT / "data" / "skill_taxonomy.json",
    )
    careers = load_career_profiles(ROOT / "data" / "career_profiles.json")

    base = {
        "location": "Hà Nội",
        "skills": ["excel", "analytics"],
        "interests": ["phân tích số liệu và tìm quy luật"],
    }
    profile_a = {**base, "gender": "nam"}
    profile_b = {**base, "gender": "nữ"}

    rec_a = recommend_careers(profile_a, careers, jobs)
    rec_b = recommend_careers(profile_b, careers, jobs)

    assert [x["career"] for x in rec_a] == [x["career"] for x in rec_b]
