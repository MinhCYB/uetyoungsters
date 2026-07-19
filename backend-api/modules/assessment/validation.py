"""Pure validation helpers shared by assessment services."""
from typing import Any


def is_visible(question: dict, responses: dict[str, Any]) -> bool:
    condition = question.get("display_if")
    if not condition:
        return True
    answer = responses.get(condition["question_id"])
    operator, expected = condition["operator"], condition["value"]
    if operator == "equals":
        return answer == expected
    if operator == "not_equals":
        return answer not in (None, "") and answer != expected
    if operator == "in":
        return answer in expected
    return False


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def option_values(question: dict) -> list[Any]:
    return [option.get("value") if isinstance(option, dict) else option for option in question.get("options") or []]


def validate_answer(question: dict, value: Any) -> str | None:
    question_type = question["type"]
    if question_type in ("single_choice", "value_item"):
        if value not in option_values(question):
            return "Lựa chọn không thuộc danh sách cho phép"
    elif question_type == "multi_choice":
        if not isinstance(value, list) or len(value) != len(set(map(str, value))):
            return "Câu trả lời phải là danh sách lựa chọn không trùng"
        if any(item not in option_values(question) for item in value):
            return "Danh sách chứa lựa chọn không hợp lệ"
        if question.get("min_selections") and len(value) < question["min_selections"]:
            return f"Cần chọn ít nhất {question['min_selections']} mục"
        if question.get("max_selections") and len(value) > question["max_selections"]:
            return f"Chỉ được chọn tối đa {question['max_selections']} mục"
    elif question_type in ("likert_5", "number"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "Giá trị phải là một số"
        scale = question.get("scale") or {}
        minimum = question.get("min", scale.get("min"))
        maximum = question.get("max", scale.get("max"))
        if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
            return f"Giá trị phải nằm trong khoảng {minimum}–{maximum}"
    elif question_type == "ranking":
        allowed = set(question.get("item_ids") or [])
        if not isinstance(value, list) or len(value) != question.get("required_count", 5):
            return f"Phải xếp hạng đúng {question.get('required_count', 5)} mục"
        if len(value) != len(set(value)) or any(item not in allowed for item in value):
            return "Danh sách xếp hạng chứa mục trùng hoặc không hợp lệ"
    elif question_type == "point_allocation":
        if not isinstance(value, dict) or set(value) != set(option_values(question)):
            return "Phải phân bổ điểm cho đúng tất cả nhóm giá trị"
        if any(isinstance(points, bool) or not isinstance(points, (int, float)) or points < 0 for points in value.values()):
            return "Điểm phân bổ phải là số không âm"
        if abs(sum(value.values()) - question.get("total_points", 100)) > 0.001:
            return f"Tổng điểm phải bằng {question.get('total_points', 100)}"
    elif question_type == "tradeoff_group":
        required_ids = set(question.get("item_ids") or [])
        if not isinstance(value, dict) or set(value) != required_ids or any(not str(answer).strip() for answer in value.values()):
            return "Phải trả lời đầy đủ tất cả tình huống đánh đổi"
        min_words = question.get("min_words_per_item", 1)
        min_chars = question.get("min_chars_per_item", 1)
        if any(len(str(answer).split()) < min_words or len(str(answer).strip()) < min_chars for answer in value.values()):
            return f"Mỗi tình huống cần ít nhất {min_words} từ và {min_chars} ký tự"
    elif question_type in ("open_text", "performance_task"):
        if not isinstance(value, str):
            return "Câu trả lời phải là văn bản"
        text = value.strip()
        word_count = len(text.split())
        if word_count < question.get("min_words", 1) or len(text) < question.get("min_chars", 1):
            return f"Câu trả lời cần ít nhất {question.get('min_words', 1)} từ và {question.get('min_chars', 1)} ký tự"
        if question.get("max_words") and word_count > question["max_words"]:
            return f"Câu trả lời không được vượt quá {question['max_words']} từ"
    return None
