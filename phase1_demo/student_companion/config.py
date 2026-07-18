"""Versioned, deterministic configuration for the Phase 1 demo."""

CONFIG_VERSION = "phase1-rules-1.0.0"
PIPELINE_VERSION = "phase1-pipeline-1.0.0"
EVIDENCE_VERSION = "evidence-1.0.0"
ESTIMATE_VERSION = "ability-1.0.0"
GAP_VERSION = "gap-1.0.0"
ACTIVITY_VERSION = "activity-catalog-1.0.0"

SOURCE_WEIGHTS = {
    "assessment": 1.0,
    "academic_record": 0.9,
    "teacher_observation": 0.8,
    "activity_result": 0.8,
    "self_report": 0.4,
}

ACADEMIC_THRESHOLDS = {
    "SKILL_TRIG_TRANSFORMATION": 0.65,
    "SKILL_DATA_REASONING": 0.65,
}

ACADEMIC_HIGH_PRIORITY_GAP = 0.20

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
        "skill_id": "SKILL_TRIG_TRANSFORMATION",
        "career_group_id": None,
        "estimated_minutes": 20,
    },
    "ACTIVITY_DATA_INSIGHTS": {
        "task_type": "career_micro_experience",
        "title": "Phân tích bảng khảo sát và tìm ba insight",
        "skill_id": None,
        "career_group_id": "CAREER_GROUP_DATA_AI",
        "estimated_minutes": 25,
        "rubric_skill_id": "SKILL_DATA_REASONING",
    },
    "ACTIVITY_ECONOMICS_CHOICE": {
        "task_type": "career_micro_experience",
        "title": "Phân tích một lựa chọn chi tiêu",
        "skill_id": None,
        "career_group_id": "CAREER_GROUP_ECONOMICS",
        "estimated_minutes": 25,
        "rubric_skill_id": "SKILL_DECISION_MAKING",
    },
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
