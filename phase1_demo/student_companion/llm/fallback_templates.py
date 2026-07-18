"""Deterministic safe content templates for all three V1 use cases."""

from __future__ import annotations

import hashlib


def stable_content_token(prefix: str, *parts: object) -> str:
    payload = "|".join(str(item) for item in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def allocate_minutes(total: int, count: int) -> list[int]:
    count = max(1, min(count, total))
    base, remainder = divmod(total, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


def build_plan_template(context: dict) -> dict:
    task = context["task"]
    academic = task["task_type"] == "academic_practice"
    desired_steps = 3 if academic else 4
    step_count = min(context["max_steps"], desired_steps, task["estimated_minutes"])
    minutes = allocate_minutes(task["estimated_minutes"], step_count)

    if academic:
        labels = [
            ("Ôn mục tiêu", "Đọc lại quy tắc chính và viết một ví dụ ngắn."),
            ("Thực hành", "Làm từng bài theo thứ tự, ghi rõ mỗi bước biến đổi."),
            ("Kiểm tra lỗi", "Đối chiếu kết quả và đánh dấu bước cần luyện thêm."),
        ]
        objective = f"Củng cố {task['title'].lower()} qua một chuỗi bài ngắn, có tự kiểm tra."
        criteria = [
            "Hoàn thành đủ các bước trong thời gian đã giao.",
            "Giải thích được ít nhất một lỗi đã phát hiện và cách sửa.",
        ]
        reflection = "Bước nào em làm chắc nhất và bước nào cần luyện thêm?"
    else:
        labels = [
            ("Đọc tình huống", "Đọc yêu cầu và ghi lại dữ kiện quan trọng."),
            ("Thực hiện nhiệm vụ", "Thực hiện nhiệm vụ theo dữ kiện, không cần công cụ chuyên ngành."),
            ("Tổng hợp", "Viết kết luận ngắn và chỉ ra dữ kiện hỗ trợ."),
            ("Phản hồi", "Tự đánh giá phần em thấy hứng thú và phần còn chưa rõ."),
        ]
        objective = f"Trải nghiệm cách tư duy của hoạt động “{task['title']}” ở mức nhập môn."
        criteria = [
            "Hoàn thành sản phẩm ngắn đúng yêu cầu của tình huống.",
            "Nêu được dữ kiện hỗ trợ và một điều học được từ hoạt động.",
        ]
        reflection = "Sau hoạt động, điều gì làm em muốn tìm hiểu thêm hoặc cân nhắc lại?"

    labels = labels[:step_count]
    return {
        "source_task_id": task["task_id"],
        "title": task["title"],
        "objective": objective,
        "skill_id": task["skill_id"],
        "career_group_id": task["career_group_id"],
        "total_minutes": task["estimated_minutes"],
        "steps": [
            {
                "step_number": index + 1,
                "title": labels[index][0],
                "instruction": labels[index][1],
                "estimated_minutes": minutes[index],
                "completion_check": "Đánh dấu hoàn thành và ghi lại một kết quả cụ thể.",
            }
            for index in range(step_count)
        ],
        "completion_criteria": criteria,
        "reflection_question": reflection,
    }


def _question_content(skill_id: str, index: int) -> tuple[str, list[str], str, str]:
    if skill_id == "SKILL_TRIG_TRANSFORMATION":
        variants = (
            ("Biểu thức nào bằng sin(x + π)?", ["-sin(x)", "sin(x)", "cos(x)", "-cos(x)"], "-sin(x)"),
            ("Khi rút gọn sin²(x) + cos²(x), kết quả là gì?", ["0", "1", "2", "sin(x)"], "1"),
            ("Bước đầu phù hợp để biến đổi 2sin(x)cos(x) là gì?", ["Dùng công thức sin(2x)", "Cộng hai vế", "Đổi sang số thập phân", "Bỏ cos(x)"], "Dùng công thức sin(2x)"),
        )
        prompt, options, answer = variants[index % len(variants)]
        return prompt, options, answer, "Áp dụng đúng công thức lượng giác tương ứng rồi kiểm tra dấu."
    if skill_id == "SKILL_DATA_REASONING":
        variants = (
            ("Một bảng có 10 giá trị, trong đó 6 giá trị tăng. Tỷ lệ giá trị tăng là bao nhiêu?", ["40%", "60%", "6%", "160%"], "60%"),
            ("Kết luận nào cần được kiểm tra bằng dữ liệu?", ["Một xu hướng quan sát được", "Tên của bảng", "Màu của tiêu đề", "Số trang tài liệu"], "Một xu hướng quan sát được"),
            ("Khi hai nhóm có quy mô khác nhau, cách so sánh phù hợp là gì?", ["So sánh tỷ lệ", "Chỉ nhìn tổng lớn hơn", "Bỏ nhóm nhỏ", "Đổi tên nhóm"], "So sánh tỷ lệ"),
        )
        prompt, options, answer = variants[index % len(variants)]
        return prompt, options, answer, "Dùng đúng dữ kiện và chọn phép so sánh phù hợp với quy mô nhóm."
    prompt = f"Hãy nêu một bước kiểm tra để bảo đảm câu trả lời số {index + 1} bám sát mục tiêu học tập."
    return prompt, [], "Nêu một bước kiểm tra hợp lý và giải thích ngắn.", "Đây là câu hỏi mẫu cấu trúc; cần giáo viên duyệt nội dung chuyên môn."


def build_reassessment_template(context: dict) -> dict:
    count = context["question_count"]
    allowed = context["allowed_question_types"]
    prior = set(context["prior_question_fingerprints"])
    scores = [round(context["max_score"] / count, 10) for _ in range(count)]
    scores[-1] = round(context["max_score"] - sum(scores[:-1]), 10)
    questions = []
    for index in range(count):
        prompt, options, answer, explanation = _question_content(
            context["target_skill_id"], index
        )
        question_type = allowed[index % len(allowed)]
        if question_type == "short_answer":
            options = []
        elif not options:
            options = [answer, "Một cách khác", "Chưa đủ dữ kiện"]
        variant = 0
        fingerprint = stable_content_token(
            "QFP", context["target_skill_id"], prompt, index, variant
        )
        while fingerprint in prior:
            variant += 1
            fingerprint = stable_content_token(
                "QFP", context["target_skill_id"], prompt, index, variant
            )
        prior.add(fingerprint)
        questions.append(
            {
                "question_id": stable_content_token(
                    "QUESTION", context["assessment_id"], index, fingerprint
                ),
                "skill_id": context["target_skill_id"],
                "question_type": question_type,
                "prompt": prompt,
                "options": options,
                "correct_answer": answer,
                "explanation": explanation,
                "score": scores[index],
                "difficulty": context["difficulty"],
                "fingerprint": fingerprint,
            }
        )
    payload = {
        "assessment_id": context["assessment_id"],
        "target_skill_id": context["target_skill_id"],
        "questions": questions,
        "total_score": context["max_score"],
        "estimated_minutes": context.get("estimated_minutes") or count * 2,
    }
    if context["target_skill_id"] not in {
        "SKILL_TRIG_TRANSFORMATION",
        "SKILL_DATA_REASONING",
    }:
        payload["_warnings"] = ["generic_question_template_requires_expert_review"]
    return payload


def build_feedback_template(context: dict) -> dict:
    correct = context["is_correct"]
    depth = context["feedback_depth"]
    if correct:
        summary = "Em đã trả lời đúng và sử dụng hướng tiếp cận phù hợp."
        hint = "Hãy thử giải thích lại quy tắc bằng một câu của riêng em."
        error_explanation = None
        encouragement = "Tiếp tục giữ thói quen kiểm tra từng bước như vậy."
    else:
        summary = "Em đã xác định được một phần của yêu cầu; bước tiếp theo là kiểm tra lại cách áp dụng quy tắc."
        hint = "Hãy đối chiếu dữ kiện với quy tắc chính trước khi thực hiện phép biến đổi tiếp theo."
        error_name = context.get("detected_error_type") or "cách áp dụng quy tắc"
        error_explanation = f"Điểm cần điều chỉnh nằm ở {error_name}; hãy kiểm tra lại bước này bằng một ví dụ ngắn."
        encouragement = "Một lỗi cụ thể là cơ hội tốt để em củng cố đúng bước còn thiếu."
    worked = []
    if depth == "worked_solution":
        worked = [
            "Xác định dữ kiện và quy tắc cần dùng.",
            "Áp dụng quy tắc theo từng bước, không bỏ qua phép biến đổi trung gian.",
            "Đối chiếu kết quả với yêu cầu ban đầu.",
        ]
    followup = None
    if context["max_followup_questions"] > 0:
        followup = "Em sẽ kiểm tra bước nào trước khi làm một câu tương tự?"
    return {
        "question_id": context["question_id"],
        "skill_id": context["skill_id"],
        "summary": summary,
        "hint": hint,
        "error_explanation": error_explanation,
        "worked_solution_steps": worked,
        "encouragement": encouragement,
        "followup_question": followup,
    }
