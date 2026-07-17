from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


SENSITIVE_FIELDS = {
    "gender",
    "ethnicity",
    "religion",
    "family_income",
    "birthplace",
}


def load_career_profiles(path: str | Path) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize_student_profile(profile: Dict) -> Dict:
    return {k: v for k, v in profile.items() if k not in SENSITIVE_FIELDS}


def recommend_careers(
    profile: Dict,
    careers: List[Dict],
    jobs: pd.DataFrame,
    top_k: int = 5,
) -> List[Dict]:
    profile = sanitize_student_profile(profile)

    student_skills = set(profile.get("skills", []))
    interests = " ".join(profile.get("interests", [])).lower()
    preferred_location = profile.get("location")

    results = []
    for career in careers:
        required = set(career["skills"])
        skill_overlap = len(student_skills & required) / max(len(required), 1)

        activity_match = sum(
            1 for activity in career["activities"]
            if any(token in interests for token in activity.lower().split())
        ) / max(len(career["activities"]), 1)

        career_jobs = jobs[
            jobs["title"].str.contains(career["career"], case=False, na=False)
        ]
        if preferred_location:
            local_jobs = career_jobs[
                career_jobs["location"].str.contains(
                    preferred_location, case=False, na=False
                )
            ]
        else:
            local_jobs = career_jobs

        market_count = len(local_jobs) if len(local_jobs) else len(career_jobs)
        market_score = min(market_count / 3.0, 1.0)

        score = 0.45 * skill_overlap + 0.30 * activity_match + 0.25 * market_score

        missing_skills = sorted(required - student_skills)
        evidence = []
        if student_skills & required:
            evidence.append(
                "Bạn đã có một số kỹ năng liên quan: "
                + ", ".join(sorted(student_skills & required))
            )
        if market_count:
            evidence.append(
                f"Baseline ghi nhận {market_count} tin tuyển dụng phù hợp trong dữ liệu mẫu."
            )
        if missing_skills:
            evidence.append(
                "Kỹ năng cần bổ sung: " + ", ".join(missing_skills)
            )
        if not evidence:
            evidence.append(
                "Chưa đủ bằng chứng; đây chỉ là hướng khám phá ban đầu."
            )

        results.append(
            {
                "career": career["career"],
                "score": round(score, 3),
                "skill_match": round(skill_overlap, 3),
                "activity_match": round(activity_match, 3),
                "market_score": round(market_score, 3),
                "missing_skills": missing_skills,
                "route": career["route"],
                "explanation": evidence,
                "uncertainty": (
                    "cao" if score < 0.35 else "trung bình" if score < 0.65 else "thấp"
                ),
            }
        )

    # Diversity baseline: avoid returning only near-identical careers.
    results = sorted(results, key=lambda x: x["score"], reverse=True)
    return results[:top_k]
