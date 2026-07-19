"""Build the Career Compass AI question-bank dictionary from the source Markdown files."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # backend-api/
SOURCE_DIR = PROJECT_ROOT / "modules" / "assessment" / "data" / "question_bank_source"
BACKEND_API_DIR = Path(os.getenv("BACKEND_API_DIR", PROJECT_ROOT))

FILES = {
    "basic_information": "01_basic_information.md",
    "interests_and_values": "02_interests_and_values.md",
    "daily_habits": "03_daily_habits.md",
    "current_skills": "04_current_skills.md",
    "ability_tasks": "05_ability_tasks.md",
    "scoring_rubrics": "06_scoring_rubrics.md",
    "sources": "07_sources.md",
}

SECTION_PREFIX = {
    "basic_information": "BI",
    "interests_and_values": "IV",
    "daily_habits": "DH",
    "current_skills": "SK",
}

ABILITY_CODES = {
    "AS": "analysis_reasoning",
    "CT": "critical_thinking",
    "CR": "creativity_ideation",
    "LA": "learning_adaptability",
    "LG": "language_communication",
    "PL": "planning_execution",
    "DT": "attention_to_detail",
    "CO": "interaction_collaboration",
}

SCALES = {
    "interest_likert_5": {"min": 1, "max": 5, "labels": ["Hoàn toàn không thích", "Không thích", "Chưa chắc", "Khá thích", "Rất thích"]},
    "habit_frequency_5": {"min": 1, "max": 5, "labels": ["Không bao giờ", "Hiếm khi", "Thỉnh thoảng", "Thường xuyên", "Gần như luôn luôn"]},
    "skill_self_level_5": {"min": 0, "max": 4, "labels": ["Chưa bắt đầu", "Biết khái niệm, cần hướng dẫn nhiều", "Tự hoàn thành nhiệm vụ cơ bản", "Tự hoàn thành nhiệm vụ có độ phức tạp vừa", "Xử lý tình huống khó và hướng dẫn người khác"]},
    "rubric_0_3": {"min": 0, "max": 3, "labels": ["Không có bằng chứng", "Tín hiệu mơ hồ", "Tương đối rõ và hợp lý", "Rõ, có cấu trúc và kiểm tra được"]},
}


def read(name: str) -> str:
    return (SOURCE_DIR / FILES[name]).read_text(encoding="utf-8-sig")


def slug(text: str) -> str:
    table = str.maketrans("àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ", "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd")
    return re.sub(r"[^a-z0-9]+", "_", text.lower().translate(table)).strip("_")


def headings(text: str):
    current_h2 = "general"
    current_h3 = None
    for line in text.splitlines():
        if line.startswith("## "):
            current_h2 = line[3:].strip()
            current_h3 = None
        elif line.startswith("### "):
            current_h3 = line[4:].strip()
        yield line, current_h2, current_h3


def parse_numbered(section: str, text: str):
    prefix = SECTION_PREFIX[section]
    result, counters = {}, {}
    lines = text.splitlines()
    current_h2 = "general"
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            current_h2 = line[3:].strip()
        match = re.match(r"^(?:([A-Z]{1,2}\d{2})|(\d+))\.\s+(.+)$", line.strip())
        if match:
            explicit, _, prompt = match.groups()
            category = slug(current_h2)
            counters[category] = counters.get(category, 0) + 1
            qid = explicit or f"{prefix}_{category.upper()}_{counters[category]:02d}"
            options = []
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            while j < len(lines) and re.match(r"^\s{3,}[-*]\s+", lines[j]):
                options.append(re.sub(r"^[-*]\s+", "", lines[j].strip()).strip())
                j += 1
            qtype = "single_choice" if options else "open_text"
            if section == "interests_and_values" and explicit and explicit[0] in "RIAS ECV".replace(" ", ""):
                qtype = "likert_5" if explicit[0] in "RIASEC" else "value_item"
            if section == "daily_habits" and explicit and explicit.startswith("H"):
                qtype = "likert_5"
            result[qid] = {
                "id": qid,
                "section": section,
                "category": category,
                "prompt": prompt,
                "type": qtype,
                "options": options or None,
                "scale_id": "interest_likert_5" if qtype == "likert_5" and section == "interests_and_values" else "habit_frequency_5" if qtype == "likert_5" else None,
                "scored": section not in ("basic_information", "current_skills"),
                "source_file": FILES[section],
            }
            if qtype == "open_text" and section == "interests_and_values":
                result[qid].update({"min_words": 1, "min_chars": 2, "max_words": 250})
            elif qtype == "open_text" and section == "daily_habits":
                result[qid].update({"min_words": 1, "min_chars": 2, "max_words": 150})
            i = j - 1
        i += 1
    return result


def parse_ability_tasks(text: str):
    result = {}
    matches = list(re.finditer(r"^###\s+([A-Z]{2}\d{2})\s+[—-]\s+(.+)$", text, re.MULTILINE))
    for index, match in enumerate(matches):
        qid, title = match.groups()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end():end].strip()
        measure = re.search(r"^Đo:\s*(.+)$", block, re.MULTILINE)
        prompt = re.sub(r"^Đo:\s*.+$", "", block, flags=re.MULTILINE).strip()
        code = qid[:2]
        result[qid] = {
            "id": qid,
            "section": "ability_tasks",
            "category": ABILITY_CODES[code],
            "title": title.strip(),
            "prompt": re.sub(r"\n+", "\n", prompt),
            "type": "performance_task",
            "target_dimensions": [ABILITY_CODES[code]],
            "measure": measure.group(1).strip() if measure else None,
            "scale_id": "rubric_0_3",
            "scored": True,
            "requires_ai_scoring": True,
            "source_weight": 0.8,
            "source_file": FILES["ability_tasks"],
            "variants": ["thpt", "university", "graduated"],
            "min_words": 1,
            "min_chars": 2,
            "max_words": 400,
        }
    return result


def add_structured_value_activities(questions: dict):
    """Add the non-numbered career-value activities described in section H."""
    questions.update({
        "VALUE_RANK_TOP_5": {
            "id": "VALUE_RANK_TOP_5", "section": "interests_and_values", "category": "h_gia_tri_nghe_nghiep",
            "prompt": "Chọn năm giá trị nghề nghiệp quan trọng nhất và xếp hạng từ 1 đến 5.",
            "type": "ranking", "item_ids": [f"V{i:02d}" for i in range(1, 19)], "required_count": 5,
            "scored": True, "source_file": FILES["interests_and_values"],
        },
        "VALUE_ALLOCATE_100": {
            "id": "VALUE_ALLOCATE_100", "section": "interests_and_values", "category": "h_gia_tri_nghe_nghiep",
            "prompt": "Phân bổ 100 điểm cho năm nhóm giá trị nghề nghiệp.", "type": "point_allocation",
            "options": ["Thu nhập và ổn định", "Phát triển và thành tựu", "Quan hệ và tác động xã hội", "Tự chủ và sáng tạo", "Điều kiện sống và làm việc"],
            "total_points": 100, "scored": True, "source_file": FILES["interests_and_values"],
        },
        "VALUE_TRADEOFFS": {
            "id": "VALUE_TRADEOFFS", "section": "interests_and_values", "category": "h_gia_tri_nghe_nghiep",
            "prompt": "Chọn ưu tiên gần với bạn hơn trong từng tình huống đánh đổi nghề nghiệp.",
            "type": "tradeoff_group", "item_ids": [f"IV_H_GIA_TRI_NGHE_NGHIEP_{i:02d}" for i in range(1, 6)],
            "min_words_per_item": 1, "min_chars_per_item": 2,
            "scored": True, "source_file": FILES["interests_and_values"],
        },
    })
    return questions


def configure_basic_information_flow(questions: dict):
    """Configure survey-only basic questions; education stage comes from the user profile."""
    questions.update({
        "PROFILE_NAME": {
            "id": "PROFILE_NAME", "section": "basic_information", "category": "identity",
            "field": "display_name", "prompt": "Bạn muốn được gọi bằng tên nào?",
            "help_text": "Bạn có thể bỏ qua và tiếp tục sử dụng hồ sơ ẩn danh.",
            "type": "open_text", "required": False, "scored": False,
            "source_file": "product_requirement",
        },
        "PROFILE_AGE": {
            "id": "PROFILE_AGE", "section": "basic_information", "category": "identity",
            "field": "age", "prompt": "Bạn bao nhiêu tuổi?", "type": "number",
            "min": 13, "max": 80, "required": True, "scored": False,
            "source_file": "product_requirement",
        },
    })
    conditions = {
        "BI_B_MUC_TIEU_HUONG_NGHIEP_04": {"question_id": "BI_B_MUC_TIEU_HUONG_NGHIEP_03", "operator": "not_equals", "value": "none"},
    }
    ordered_ids = [
        "PROFILE_NAME", "PROFILE_AGE",
        "BI_B_MUC_TIEU_HUONG_NGHIEP_01", "BI_B_MUC_TIEU_HUONG_NGHIEP_02",
        "BI_B_MUC_TIEU_HUONG_NGHIEP_03", "BI_B_MUC_TIEU_HUONG_NGHIEP_04",
        "BI_C_KHU_VUC_VA_KHA_NANG_DI_CHUYEN_01", "BI_C_KHU_VUC_VA_KHA_NANG_DI_CHUYEN_02",
        "BI_C_KHU_VUC_VA_KHA_NANG_DI_CHUYEN_03", "BI_D_THOI_GIAN_VA_NGUON_LUC_01",
        "BI_D_THOI_GIAN_VA_NGUON_LUC_02", "BI_D_THOI_GIAN_VA_NGUON_LUC_03",
        "BI_D_THOI_GIAN_VA_NGUON_LUC_04", "BI_E_RANG_BUOC_TU_NGUYEN_01",
        "BI_E_RANG_BUOC_TU_NGUYEN_02",
    ]
    for order, question_id in enumerate(ordered_ids, 1):
        question = questions[question_id]
        question["order"] = order
        question["display_if"] = conditions.get(question_id)
        question["required"] = question.get("required", question_id != "BI_E_RANG_BUOC_TU_NGUYEN_02")
    for question_id in ("BI_D_THOI_GIAN_VA_NGUON_LUC_03", "BI_D_THOI_GIAN_VA_NGUON_LUC_04", "BI_E_RANG_BUOC_TU_NGUYEN_01"):
        questions[question_id]["type"] = "multi_choice"
    explicit_values = {
        "BI_B_MUC_TIEU_HUONG_NGHIEP_03": ["none", "some_ideas", "clear_choice"],
    }
    for question_id in ordered_ids:
        question = questions[question_id]
        if not question.get("options"):
            continue
        values = explicit_values.get(question_id)
        question["options"] = [
            {"value": values[index] if values else slug(label), "label": label}
            for index, label in enumerate(question["options"])
        ]
    return questions


def parse_rubrics(text: str):
    result = {}
    section = text.split("## 2. Rubric theo năng lực", 1)[-1].split("## 3.", 1)[0]
    parts = re.split(r"^###\s+", section, flags=re.MULTILINE)[1:]
    dimension_lookup = {
        "Phân tích và suy luận": "analysis_reasoning", "Tư duy phản biện": "critical_thinking",
        "Sáng tạo và tạo ý tưởng": "creativity_ideation", "Học hỏi và thích ứng": "learning_adaptability",
        "Ngôn ngữ và diễn đạt": "language_communication", "Lập kế hoạch và thực thi": "planning_execution",
        "Chú ý chi tiết": "attention_to_detail", "Tương tác và hợp tác": "interaction_collaboration",
    }
    for part in parts:
        lines = part.strip().splitlines()
        title = lines[0].strip()
        if title not in dimension_lookup:
            continue
        criteria = [re.sub(r"^-\s*", "", x).strip() for x in lines[1:] if x.startswith("-")]
        result[dimension_lookup[title]] = {"dimension": dimension_lookup[title], "label": title, "criteria": criteria, "scale_id": "rubric_0_3"}
    return result


def parse_sources(text: str):
    result = {}
    blocks = re.split(r"^###\s+", text, flags=re.MULTILINE)[1:]
    for block in blocks:
        lines = block.strip().splitlines()
        title = lines[0].strip()
        urls = re.findall(r"https?://[^\s)]+", block)
        result[slug(title)] = {"title": title, "urls": urls, "notes": [x[2:].strip() for x in lines[1:] if x.startswith("- ")]}
    return result


def build_bank():
    sections = {
        "basic_information": configure_basic_information_flow(parse_numbered("basic_information", read("basic_information"))),
        "interests_and_values": add_structured_value_activities(parse_numbered("interests_and_values", read("interests_and_values"))),
        "daily_habits": parse_numbered("daily_habits", read("daily_habits")),
        "current_skills": parse_numbered("current_skills", read("current_skills")),
        "ability_tasks": parse_ability_tasks(read("ability_tasks")),
    }
    bank = {
        "schema_version": "1.0.0",
        "language": "vi",
        "title": "Career Compass Question Bank",
        "disclaimer": "Bộ đánh giá nguyên mẫu dựa trên các khung năng lực quốc tế, chưa được chuẩn hóa tại Việt Nam.",
        "scales": SCALES,
        "sections": sections,
        "rubrics": parse_rubrics(read("scoring_rubrics")),
        "sources": parse_sources(read("sources")),
        "generation_blueprints": {
            "standard_25_35_min": {
                "basic_information": {"fixed_flow": True, "profile_fields": ["profile_type", "grade_level", "education_program"], "question_ids": ["PROFILE_NAME", "PROFILE_AGE", "BI_B_MUC_TIEU_HUONG_NGHIEP_01", "BI_B_MUC_TIEU_HUONG_NGHIEP_02", "BI_B_MUC_TIEU_HUONG_NGHIEP_03", "BI_B_MUC_TIEU_HUONG_NGHIEP_04", "BI_C_KHU_VUC_VA_KHA_NANG_DI_CHUYEN_01", "BI_C_KHU_VUC_VA_KHA_NANG_DI_CHUYEN_02", "BI_C_KHU_VUC_VA_KHA_NANG_DI_CHUYEN_03", "BI_D_THOI_GIAN_VA_NGUON_LUC_01", "BI_D_THOI_GIAN_VA_NGUON_LUC_02", "BI_D_THOI_GIAN_VA_NGUON_LUC_03", "BI_D_THOI_GIAN_VA_NGUON_LUC_04", "BI_E_RANG_BUOC_TU_NGUYEN_01", "BI_E_RANG_BUOC_TU_NGUYEN_02"]},
                "riasec": {"min": 18, "max": 24, "balance": {"R": 3, "I": 3, "A": 3, "S": 3, "E": 3, "C": 3}},
                "career_values": {"ranking_activities": 2},
                "daily_habits": {"min": 12, "max": 16, "cover_all_categories": True},
                "habit_context_questions": {"count": 4},
                "current_skills": {"min": 5, "max": 10, "dynamic": True},
                "ability_tasks": {"count": 8, "one_per_dimension": True},
                "deep_open_questions": {"count": 4, "adaptive": True},
            },
            "short_15_20_min": {
                "basic_information": {"fixed_flow": True, "profile_fields": ["profile_type", "grade_level", "education_program"], "question_ids": ["PROFILE_NAME", "PROFILE_AGE", "BI_B_MUC_TIEU_HUONG_NGHIEP_01", "BI_C_KHU_VUC_VA_KHA_NANG_DI_CHUYEN_01", "BI_D_THOI_GIAN_VA_NGUON_LUC_01"]},
                "riasec": {"count": 12, "balance": {"R": 2, "I": 2, "A": 2, "S": 2, "E": 2, "C": 2}},
                "daily_habits": {"count": 8, "cover_all_categories": True},
                "ability_tasks": {"count": 4, "adaptive": True, "max_one_per_dimension": True},
            },
        },
        "selection_rules": [
            "Do not use basic information to score ability.",
            "Keep self-report evidence separate from task-performance evidence.",
            "Require at least two different evidence sources per ability before drawing a conclusion.",
            "Cover all six RIASEC dimensions with equal item counts.",
            "Do not lower scores when the user lacked an opportunity to perform an activity.",
            "Every open-response score must include reasons and exact evidence quotes.",
            "Never infer gender, diagnosis, fixed personality, or guaranteed career outcome.",
            "Allow the user to confirm, adjust, or reject every AI inference.",
        ],
    }
    return bank


def main():
    global SOURCE_DIR
    parser = argparse.ArgumentParser(description="Parse Markdown sources and import a normalized question bank into PostgreSQL.")
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--version", default=os.getenv("QUESTION_BANK_VERSION"), help="Override schema version, for example 1.1.0")
    parser.add_argument("--status", choices=("draft", "published", "archived"), default="published")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    SOURCE_DIR = args.source_dir
    missing = [filename for filename in FILES.values() if not (SOURCE_DIR / filename).exists()]
    if missing:
        parser.error(f"Missing source files in {SOURCE_DIR}: {', '.join(missing)}")
    bank = build_bank()
    if args.version:
        bank["schema_version"] = args.version
    counts = {name: len(items) for name, items in bank["sections"].items()}
    if not args.validate_only:
        if not args.database_url:
            parser.error("--database-url or DATABASE_URL is required unless --validate-only is used")
        os.environ["DATABASE_URL"] = args.database_url
        sys.path.insert(0, str(BACKEND_API_DIR))
        from modules.assessment.repository import import_question_bank
        from database import SessionLocal, init_db
        init_db()
        with SessionLocal() as db:
            import_question_bank(db, bank, status=args.status)
    print(json.dumps({"database": bool(args.database_url and not args.validate_only), "version": bank["schema_version"], "status": args.status, "counts": counts, "total": sum(counts.values())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
