from backend.data.extraction import load_taxonomy, normalize_career, extract_skills
from backend.data.normalization import parse_salary, normalize_location


def taxonomy():
    return load_taxonomy("backend/shared/taxonomy.json")


def test_career_normalization():
    career_id, name, confidence = normalize_career(
        "Nhân viên phân tích dữ liệu", taxonomy()
    )
    assert career_id == "CAREER_DATA_ANALYST"
    assert name == "Data Analyst"
    assert confidence == 1.0


def test_salary_range():
    minimum, maximum, midpoint, disclosed = parse_salary("12 - 18 triệu")
    assert minimum == 12_000_000
    assert maximum == 18_000_000
    assert midpoint == 15_000_000
    assert disclosed is True


def test_salary_negotiable():
    minimum, maximum, midpoint, disclosed = parse_salary("Thỏa thuận")
    assert minimum is None
    assert maximum is None
    assert disclosed is False


def test_location_alias():
    assert normalize_location("KCN Quế Võ", taxonomy()) == "Bắc Ninh"


def test_skill_negation_and_preference():
    skills = extract_skills(
        "Yêu cầu SQL. Python là lợi thế. Không bắt buộc Power BI.",
        taxonomy(),
    )
    levels = {skill.skill_name: skill.requirement_level for skill in skills}
    assert levels["SQL"] == "required"
    assert levels["Python"] == "preferred"
    assert levels["Power BI"] == "not_required"
