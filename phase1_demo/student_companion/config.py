"""Versioned, deterministic configuration for the Phase 1 demo."""

CONFIG_VERSION = "phase1-rules-1.0.0"
PIPELINE_VERSION = "phase1-pipeline-1.0.0"
EVIDENCE_VERSION = "evidence-1.0.0"
ESTIMATE_VERSION = "ability-1.0.0"
GAP_VERSION = "gap-1.0.0"
ACTIVITY_VERSION = "activity-catalog-1.0.0"
CONFIDENCE_CONFIG_VERSION = "confidence-1.0.0"
GAP_PRIORITY_CONFIG_VERSION = "gap-priority-1.0.0"

SOURCE_WEIGHTS = {
    "assessment": 1.0,
    "academic_record": 0.9,
    "teacher_observation": 0.8,
    "activity_result": 0.7,
    "self_report": 0.4,
}

CONFIDENCE_POLICY = {
    "minimum_evidence_count": 2,
    "agreement_threshold": 0.15,
    "conflict_threshold": 0.35,
    "single_source_diversity_factor": 0.85,
    "single_self_report_factor": 0.60,
    "low_confidence_threshold": 0.55,
}

ACADEMIC_THRESHOLDS = {
    "SKILL_TRIG_TRANSFORMATION": 0.65,
    "SKILL_DATA_REASONING": 0.65,
}

ACADEMIC_HIGH_PRIORITY_GAP = 0.20

GAP_PRIORITY_POLICY = {
    "medium_score": 0.10,
    "high_score": 0.25,
    "current_school_priority": 1.20,
    "exam_week_school_priority": 1.40,
    "feasible_activity_factor": 1.0,
    "missing_activity_factor": 0.75,
}

OUTCOME_THRESHOLDS = {
    "meaningful_improvement": 0.20,
    "partial_improvement": 0.05,
    "regression": -0.05,
}

ABILITY_TREND_THRESHOLD = 0.05

TEACHER_OBSERVATION_VALUES = {
    "strength": {"low": 0.65, "medium": 0.80, "high": 0.95},
    "neutral": {"low": 0.50, "medium": 0.50, "high": 0.50},
    "weakness": {"low": 0.40, "medium": 0.25, "high": 0.10},
}

CAREER_EXPLORATION_RULES = {
    "minimum_completed_activities": 1,
    "minimum_rubric_level": 0.60,
    "decision_minimum_distinct_careers": 2,
}

PREREQUISITE_IMPORTANCE = {
    "SKILL_LOGICAL_THINKING": 1.0,
    "SKILL_QUANTITATIVE_REASONING": 1.0,
    "SKILL_DATA_REASONING": 1.0,
    "SKILL_COMMUNICATION": 0.8,
    "SKILL_DECISION_MAKING": 0.8,
}

ALLOWED_FOUNDATION_SKILLS = tuple(PREREQUISITE_IMPORTANCE)

ACTIVITY_CATALOG = {
    "ACTIVITY_TRIG_PRACTICE": {
        "task_type": "academic_practice",
        "title": "Luyện biến đổi lượng giác",
        "description": "Luyện các bước biến đổi lượng giác nền tảng theo ví dụ ngắn.",
        "skill_id": "SKILL_TRIG_TRANSFORMATION",
        "skill_ids": ("SKILL_TRIG_TRANSFORMATION",),
        "career_group_id": None,
        "estimated_minutes": 20,
        "difficulty": "foundation",
        "prerequisite_skill_ids": (),
        "rubric_dimensions": ("accuracy", "reasoning"),
        "reflection_questions": ("Bước biến đổi nào em cần kiểm tra lại?",),
        "activity_version": ACTIVITY_VERSION,
    },
    "ACTIVITY_DATA_INSIGHTS": {
        "task_type": "career_micro_experience",
        "title": "Phân tích bảng khảo sát và tìm ba insight",
        "description": "Đọc bảng khảo sát, tìm ba insight và trình bày kết luận ngắn.",
        "skill_id": None,
        "skill_ids": ("SKILL_DATA_REASONING", "SKILL_COMMUNICATION"),
        "career_group_id": "CAREER_GROUP_DATA_AI",
        "estimated_minutes": 25,
        "rubric_skill_id": "SKILL_DATA_REASONING",
        "difficulty": "introductory",
        "prerequisite_skill_ids": (),
        "rubric_dimensions": ("evidence_use", "insight_quality", "communication"),
        "reflection_questions": ("Insight nào được dữ liệu hỗ trợ rõ nhất?",),
        "activity_version": ACTIVITY_VERSION,
    },
    "ACTIVITY_ECONOMICS_CHOICE": {
        "task_type": "career_micro_experience",
        "title": "Phân tích một lựa chọn chi tiêu",
        "description": "So sánh chi phí, lợi ích và giải thích một lựa chọn chi tiêu.",
        "skill_id": None,
        "skill_ids": ("SKILL_DECISION_MAKING", "SKILL_QUANTITATIVE_REASONING"),
        "career_group_id": "CAREER_GROUP_ECONOMICS",
        "estimated_minutes": 25,
        "rubric_skill_id": "SKILL_DECISION_MAKING",
        "difficulty": "introductory",
        "prerequisite_skill_ids": (),
        "rubric_dimensions": ("cost_benefit", "reasoning"),
        "reflection_questions": ("Yếu tố nào ảnh hưởng nhiều nhất đến lựa chọn?",),
        "activity_version": ACTIVITY_VERSION,
    },
    "ACTIVITY_MARKETING_MESSAGE": {
        "task_type": "career_micro_experience",
        "title": "Xác định khách hàng và viết thông điệp ngắn",
        "description": "Chọn một nhóm khách hàng mục tiêu và viết thông điệp phù hợp.",
        "skill_id": None,
        "skill_ids": ("SKILL_COMMUNICATION", "SKILL_DECISION_MAKING"),
        "career_group_id": "CAREER_GROUP_MARKETING_COMMUNICATION",
        "estimated_minutes": 25,
        "rubric_skill_id": "SKILL_COMMUNICATION",
        "difficulty": "introductory",
        "prerequisite_skill_ids": (),
        "rubric_dimensions": ("audience_fit", "message_clarity"),
        "reflection_questions": ("Thông điệp đã phù hợp với khách hàng mục tiêu chưa?",),
        "activity_version": ACTIVITY_VERSION,
    },
    "ACTIVITY_DESIGN_UX_REVIEW": {
        "task_type": "career_micro_experience",
        "title": "Phân tích một màn hình ứng dụng",
        "description": "Quan sát một màn hình và đề xuất cải thiện trải nghiệm sử dụng.",
        "skill_id": None,
        "skill_ids": ("SKILL_LOGICAL_THINKING", "SKILL_COMMUNICATION"),
        "career_group_id": "CAREER_GROUP_DESIGN_UX",
        "estimated_minutes": 25,
        "rubric_skill_id": "SKILL_LOGICAL_THINKING",
        "difficulty": "introductory",
        "prerequisite_skill_ids": (),
        "rubric_dimensions": ("user_observation", "improvement_rationale"),
        "reflection_questions": ("Đề xuất nào giúp người dùng rõ ràng hơn?",),
        "activity_version": ACTIVITY_VERSION,
    },
    "ACTIVITY_ENGINEERING_SOLUTION": {
        "task_type": "career_micro_experience",
        "title": "Đề xuất giải pháp kỹ thuật cho vấn đề đời sống",
        "description": "Mô tả vấn đề, ràng buộc và một giải pháp kỹ thuật khả thi.",
        "skill_id": None,
        "skill_ids": ("SKILL_LOGICAL_THINKING", "SKILL_QUANTITATIVE_REASONING"),
        "career_group_id": "CAREER_GROUP_ENGINEERING",
        "estimated_minutes": 25,
        "rubric_skill_id": "SKILL_LOGICAL_THINKING",
        "difficulty": "introductory",
        "prerequisite_skill_ids": (),
        "rubric_dimensions": ("problem_definition", "feasibility"),
        "reflection_questions": ("Ràng buộc nào có thể làm giải pháp thay đổi?",),
        "activity_version": ACTIVITY_VERSION,
    },
    "ACTIVITY_LAW_PERSPECTIVES": {
        "task_type": "career_micro_experience",
        "title": "Phân tích tình huống có nhiều quan điểm",
        "description": "Nêu lập luận, bằng chứng và phản biện cho một tình huống xã hội.",
        "skill_id": None,
        "skill_ids": ("SKILL_LOGICAL_THINKING", "SKILL_COMMUNICATION"),
        "career_group_id": "CAREER_GROUP_LAW_SOCIAL_SCIENCES",
        "estimated_minutes": 25,
        "rubric_skill_id": "SKILL_LOGICAL_THINKING",
        "difficulty": "introductory",
        "prerequisite_skill_ids": (),
        "rubric_dimensions": ("argument", "counterargument", "evidence_use"),
        "reflection_questions": ("Phản biện nào làm lập luận của em mạnh hơn?",),
        "activity_version": ACTIVITY_VERSION,
    },
    "ACTIVITY_HEALTH_INFORMATION": {
        "task_type": "career_micro_experience",
        "title": "Tổng hợp tình huống sức khỏe cộng đồng",
        "description": "Đọc tình huống đơn giản và tổng hợp thông tin, không chẩn đoán.",
        "skill_id": None,
        "skill_ids": ("SKILL_DATA_REASONING", "SKILL_COMMUNICATION"),
        "career_group_id": "CAREER_GROUP_HEALTH_LIFE_SCIENCES",
        "estimated_minutes": 25,
        "rubric_skill_id": "SKILL_DATA_REASONING",
        "difficulty": "introductory",
        "prerequisite_skill_ids": (),
        "rubric_dimensions": ("information_quality", "scope_safety"),
        "reflection_questions": ("Thông tin nào cần được kiểm chứng thêm?",),
        "activity_version": ACTIVITY_VERSION,
    },
}

ACTIVITY_CATALOG = {
    activity_id: {"activity_id": activity_id, **item}
    for activity_id, item in ACTIVITY_CATALOG.items()
}

CAREER_ACTIVITY_BY_GROUP = {
    item["career_group_id"]: activity_id
    for activity_id, item in ACTIVITY_CATALOG.items()
    if item["career_group_id"] is not None
}

MARKET_GROUP_MAPPING_VERSION = "market-groups-1.0.0"
MARKET_GROUPS = {
    "CAREER_GROUP_DATA_AI": {
        "display_name": "Data/AI",
        "source_career_ids": (
            "CAREER_BI_ANALYST",
            "CAREER_BUSINESS_ANALYST",
        ),
    },
    "CAREER_GROUP_ECONOMICS": {
        "display_name": "Kinh tế",
        "source_career_ids": (
            "CAREER_ACCOUNTANT",
            "CAREER_CREDIT_RISK_ANALYST",
            "CAREER_BUSINESS_DEVELOPMENT_EXECUTIVE",
        ),
    },
}

MARKET_SKILL_TO_FOUNDATION = {
    "SKILL_DATA_ANALYSIS": "SKILL_DATA_REASONING",
    "SKILL_COMMUNICATION": "SKILL_COMMUNICATION",
    "SKILL_NEGOTIATION": "SKILL_DECISION_MAKING",
}
