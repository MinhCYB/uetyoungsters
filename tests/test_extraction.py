from pathlib import Path

import pandas as pd

from crawl_service.description_cleaning import clean_job_descriptions
from crawl_service.extraction import (
    extract_experience_years,
    extract_skills,
    load_taxonomy,
)
from crawl_service.normalization import normalize_location


TAXONOMY_PATH = Path("backend/shared/taxonomy.json")


def test_extract_3d_character_skills():
    description = """
    Proficiency with Unreal Engine, Unity, Maya,
    Blender, ZBrush and Substance Painter.
    """
    skills = extract_skills(description, load_taxonomy(TAXONOMY_PATH))
    names = {skill.skill_name for skill in skills}

    assert {"Unreal Engine", "Unity", "Maya", "Blender", "ZBrush"} <= names


def test_extract_experience():
    description = "3+ years of experience in 3D production."
    assert extract_experience_years(description) == 3.0


def test_normalize_location():
    taxonomy = load_taxonomy(TAXONOMY_PATH)
    assert normalize_location("Ho Chi Minh city, Vietnam", taxonomy) == "TP.HCM"


def test_company_boilerplate_removed():
    common = "<p>NAVER Vietnam is an equal opportunity employer.</p>"
    dataframe = pd.DataFrame(
        {
            "source_id": ["greenhouse_navervietnam"] * 3,
            "description_raw": [
                f"<p>Build 3D characters.</p>{common}",
                f"<p>Develop backend services.</p>{common}",
                f"<p>Analyze product data.</p>{common}",
            ],
        }
    )

    result = clean_job_descriptions(dataframe)
    assert result["boilerplate_text"].str.contains(
        "equal opportunity", case=False
    ).all()
    assert not result["description_role_specific"].str.contains(
        "equal opportunity", case=False
    ).any()
