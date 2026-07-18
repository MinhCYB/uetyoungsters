"""Safe presentation mapping from core responses to the frontend contract."""

from typing import Any


SKILL_LABELS = {
    "SKILL_TRIG_TRANSFORMATION": "Đọc hiểu dữ liệu",
    "SKILL_DATA_REASONING": "Tư duy dữ liệu",
    "SKILL_LOGICAL_THINKING": "Giải quyết vấn đề",
    "SKILL_COMMUNICATION": "Giao tiếp",
}
CAREER_LABELS = {
    "CAREER_GROUP_DATA_AI": "Data/AI",
    "CAREER_GROUP_ECONOMICS": "Kinh tế",
}


def _label(identifier: str | None) -> str:
    if identifier is None:
        return "Chưa xác định"
    if identifier.startswith("INTEREST_"):
        return f"Mức quan tâm {_label(identifier.removeprefix('INTEREST_'))}"
    return SKILL_LABELS.get(identifier, CAREER_LABELS.get(identifier, "Nội dung phát triển"))


def _level(value: float) -> str:
    if value < 0.35:
        return "emerging"
    if value < 0.60:
        return "developing"
    if value < 0.80:
        return "proficient"
    return "advanced"


def _warning(item: Any) -> dict:
    code = item.warning_code.lower()
    messages = {
        "optional_data_missing": "Hồ sơ hiện chưa có phần tự đánh giá của học sinh.",
        "small_market_sample": "Tín hiệu thị trường đang dùng mẫu dự phòng quy mô nhỏ.",
        "insufficient_evidence": "Ước lượng này hiện dựa trên số lượng bằng chứng còn hạn chế.",
        "low_confidence_estimate": "Cần thêm hoạt động trước khi đưa ra kết luận chắc chắn.",
    }
    return {
        "code": code,
        "severity": "caution" if "insufficient" in code or "small" in code else "info",
        "title": "Cần thêm dữ liệu" if "evidence" in code else "Lưu ý khi diễn giải",
        "message": messages.get(code, "Kết quả này cần được diễn giải cùng các dữ liệu bổ sung."),
        "suggested_action": "Hoàn thành bước tiếp theo để bổ sung bằng chứng." if "evidence" in code else None,
    }


def _common(*, response_type: str, response: Any, display_name: str) -> dict:
    return {
        "contract_version": "1.0.0",
        "response_type": response_type,
        "request_id": response.metadata.request_id,
        "student_id": response.student_id,
        "display_name": display_name,
        "generated_at": response.metadata.requested_at.isoformat(),
        "warnings": [_warning(item) for item in response.warnings],
        "next_steps": [],
    }


def present_analysis(response: Any, *, analysis_id: str, profile_version: int, display_name: str) -> dict:
    data = _common(response_type="initial_analysis", response=response, display_name=display_name)
    market_is_fallback = any(item.data_mode == "fallback_demo" for item in response.market_context)
    gaps = []
    for gap in response.gaps:
        subject_id = gap.skill_id or gap.career_group_ids[0]
        gaps.append({
            "gap_id": gap.gap_id,
            "gap_type": gap.gap_type.value,
            "gap_dimension": "knowledge" if gap.gap_type.value == "academic" else ("experience" if gap.gap_type.value == "exploration" else None),
            "subject_id": subject_id,
            "display_name": _label(subject_id) if gap.gap_type.value != "decision" else "So sánh hướng nghề nghiệp",
            "priority": gap.priority.value,
            "description": {"academic": "Mức hiện tại còn dưới ngưỡng nền tảng của lộ trình.", "exploration": "Chưa có micro-experience đạt chuẩn cho hướng này.", "decision": "Cần thêm trải nghiệm trước khi thu hẹp lựa chọn."}[gap.gap_type.value],
            "status": "open",
        })
    data.update({
        "analysis_id": analysis_id,
        "profile_version": profile_version,
        "title": "Hồ sơ năng lực ban đầu",
        "summary": "Kết quả được tổng hợp từ hồ sơ học tập, đánh giá và quan sát hiện có.",
        "market_message": "Dữ liệu dự phòng cho demo" if market_is_fallback else None,
        "ability_profile": [{
            "ability_id": item.skill_id,
            "display_name": _label(item.skill_id),
            "level": _level(item.estimated_level),
            "score": round(item.estimated_level * 100, 2),
            "max_score": 100,
            "confidence": item.confidence,
            "explanation": "Ước lượng từ các nguồn dữ liệu hợp lệ trong hồ sơ.",
            "trend": item.trend.value,
        } for item in response.ability_profile],
        "gaps": gaps,
    })
    data["next_steps"] = [{"step_id": "generate_plan", "title": "Tạo kế hoạch 45 phút", "description": "Kết hợp luyện tập học thuật và một micro-experience nghề nghiệp.", "priority": "high", "route": None}]
    return data


def present_plan(response: Any, *, analysis_id: str, display_name: str) -> dict:
    data = _common(response_type="plan_generation", response=response, display_name=display_name)
    plan = response.plan
    activities = [{
        "activity_id": item.task_id,
        "title": "Luyện đọc hiểu dữ liệu" if item.skill_id == "SKILL_TRIG_TRANSFORMATION" else item.title,
        "status": "not_started",
        "task_type": item.task_type.value,
        "skill_id": item.skill_id,
        "career_group_id": item.career_group_id,
        "estimated_minutes": item.estimated_minutes,
    } for item in plan.tasks]
    data.update({
        "analysis_id": analysis_id,
        "plan_id": plan.plan_id,
        "duration_weeks": 1,
        "progress_percentage": 0,
        "title": "Kế hoạch tuần này",
        "summary": f"{plan.total_planned_minutes} phút trong ngân sách {plan.weekly_budget_minutes} phút.",
        "weekly_plan": [{"week_number": 1, "title": "Học và trải nghiệm", "objective": "Củng cố một nền tảng và thử một nhiệm vụ nghề nghiệp ngắn.", "estimated_minutes": plan.total_planned_minutes, "activities": activities}],
        "estimated_minutes": plan.total_planned_minutes,
        "activities": activities,
    })
    if activities:
        data["next_steps"] = [{"step_id": "expand_plan", "title": "Xem hướng dẫn chi tiết", "description": "Mở các bước thực hiện cho nhiệm vụ đã được engine chọn.", "priority": "high", "route": None}]
    return data


def present_followup(response: Any, *, baseline_analysis_id: str, profile_version: int, display_name: str) -> dict:
    data = _common(response_type="followup_evaluation", response=response, display_name=display_name)
    before_after = [{
        "subject_id": item.metric_type,
        "display_name": _label(item.metric_type),
        "before": round(item.before_value * 100, 2),
        "after": round(item.after_value * 100, 2),
        "max_value": 100,
        "delta": round(item.delta * 100, 2),
        "interpretation": item.status.value.replace("_", " "),
    } for item in response.outcomes]
    data.update({
        "baseline_analysis_id": baseline_analysis_id,
        "profile_version": profile_version,
        "progress_percentage": 100 if response.outcomes else 0,
        "title": "Tiến triển sau 3 tuần",
        "summary": "So sánh baseline với posttest và hoạt động đã hoàn thành.",
        "before_after": before_after,
        "outcomes": [{"subject_id": item.metric_type, "status": item.status.value, "delta": round(item.delta * 100, 2)} for item in response.outcomes],
        "updated_gaps": [{"gap_id": gap.gap_id, "gap_type": gap.gap_type.value, "gap_dimension": "knowledge" if gap.gap_type.value == "academic" else ("experience" if gap.gap_type.value == "exploration" else None), "display_name": "So sánh hướng nghề nghiệp" if gap.gap_type.value == "decision" else _label(gap.skill_id or (gap.career_group_ids[0] if gap.career_group_ids else None)), "priority": gap.priority.value, "status": "open"} for gap in response.updated_gaps],
    })
    if response.next_step is not None:
        data["next_steps"] = [{"step_id": response.next_step.task_id, "title": "Luyện đọc hiểu dữ liệu" if response.next_step.skill_id == "SKILL_TRIG_TRANSFORMATION" else response.next_step.title, "description": "Tiếp tục với hoạt động phù hợp nhất trong kế hoạch.", "priority": "medium", "route": None}]
    return data
