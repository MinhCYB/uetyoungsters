from crawl_service.extraction import load_taxonomy, normalize_career, extract_skills
from crawl_service.normalization import (
    normalize_location,
    normalize_work_mode,
    parse_salary,
)


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


def test_normalize_location_handles_nan():
    result = normalize_location(float("nan"), taxonomy())
    assert result is None


def test_normalize_lang_son():
    data = taxonomy()

    assert normalize_location("Lạng Sơn", data) == "Lạng Sơn"
    assert normalize_location("Lang Son", data) == "Lạng Sơn"


def test_normalize_remote_work_mode():
    assert normalize_work_mode(
        work_mode_raw=None,
        location_raw="Việc làm tại nhà",
        description_raw=None,
    ) == "REMOTE"


def test_location_does_not_imply_onsite():
    assert normalize_work_mode(
        work_mode_raw=None,
        location_raw="TP.HCM",
        description_raw=None,
    ) == "UNSPECIFIED"


def test_normalize_hybrid_work_mode():
    assert normalize_work_mode(
        work_mode_raw="Hybrid",
        location_raw="Hà Nội",
        description_raw=None,
    ) == "HYBRID"


def test_skill_negation_and_preference():
    skills = extract_skills(
        "Yêu cầu SQL. Python là lợi thế. Không bắt buộc Power BI.",
        taxonomy(),
    )
    levels = {skill.skill_name: skill.requirement_level for skill in skills}
    assert levels["SQL"] == "required"
    assert levels["Python"] == "preferred"
    assert levels["Power BI"] == "not_required"


def test_new_career_aliases_and_title_noise():
    cases = {
        "Gấp Kỹ Sư Thiết Kế Hạ Tầng Kỹ Thuật "
        "(Mức lương 15 - 22 Triệu)": (
            "CAREER_CIVIL_INFRASTRUCTURE_ENGINEER"
        ),
        "TUYỂN DỤNG EDITOR –XE ĐẠP ĐIỆN TRỢ LỰC GẤP GỌN": (
            "CAREER_VIDEO_EDITOR"
        ),
        "Thực Tập Sinh Kinh Doanh": "CAREER_SALES_EXECUTIVE",
        "Nhân viên Helpdesk": "CAREER_HELPDESK_TECHNICIAN",
        "Nhân Viên Kế Hoạch Sản Xuất": "CAREER_PRODUCTION_PLANNER",
    }

    for title, expected_id in cases.items():
        career_id, _, confidence = normalize_career(title, taxonomy())
        assert career_id == expected_id
        assert confidence >= 0.9


def test_new_skill_aliases_and_noise():
    skills = extract_skills(
        "Auto Cad\nTelesales\nAdobe Premiere\nKhông Cần Kinh Nghiệm",
        taxonomy(),
        default_requirement_level="mentioned",
    )
    names = {skill.skill_name for skill in skills}

    assert {"AutoCAD", "Telesales", "Adobe Premiere"} <= names
    assert all(skill.requirement_level == "mentioned" for skill in skills)
    assert "Không Cần Kinh Nghiệm" not in names


def test_new_location_aliases():
    data = taxonomy()
    assert normalize_location("Hung Yen", data) == "Hưng Yên"
    assert normalize_location("Đà Lạt", data) == "Lâm Đồng"
    assert normalize_location("Hai Phong", data) == "Hải Phòng"
