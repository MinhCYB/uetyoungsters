from crawl_service.collectors.viecoi import (
    extract_location,
    extract_salary,
    infer_company,
    infer_skills,
    normalize_job_url,
)


def test_reject_viecoi_category_page():
    url = (
        "https://viecoi.vn/viec-lam/"
        "danh-muc-ban-hang-kinh-doanh-2.html"
    )

    assert normalize_job_url(url) is None


def test_title_salary_does_not_swap_company_location():
    title = (
        "Chỉ Huy Trưởng Công Trình "
        "(Lương 28-33 triệu/tháng)"
    )

    lines = [
        title,
        "Công ty Cổ phần Đức Anh",
        "28-33 triệu",
        "Lạng Sơn",
        "15/08/2026",
    ]

    salary = extract_salary(lines, title)
    location = extract_location(lines, title)
    company = infer_company(
        lines,
        title,
        salary,
        location,
        "15/08/2026",
    )

    assert salary == "28-33 triệu"
    assert location == "Lạng Sơn"
    assert company == "Công ty Cổ phần Đức Anh"


def test_infer_skills_from_one_tag_per_line():
    lines = [
        "Nhân viên marketing",
        "Công ty TNHH Demo",
        "10-12 triệu",
        "TPHCM",
        "31/08/2026",
        "Google Ads",
        "Facebook Ads",
        "Content Marketing",
        "Nộp đơn",
    ]

    skills = infer_skills(
        lines,
        title="Nhân viên marketing",
        company="Công ty TNHH Demo",
        salary_raw="10-12 triệu",
        location_raw="TPHCM",
        deadline_raw="31/08/2026",
    )

    assert skills == ["Google Ads", "Facebook Ads", "Content Marketing"]
