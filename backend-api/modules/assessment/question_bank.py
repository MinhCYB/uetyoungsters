"""Runtime access helpers for the Career Compass question bank."""
from __future__ import annotations

import random
import re
from typing import Any

def get_question(question_id: str, bank: dict[str, Any]) -> dict[str, Any] | None:
    """Return one question by its stable ID."""
    for questions in bank["sections"].values():
        if question_id in questions:
            return questions[question_id]
    return None


def questions_in(section: str, bank: dict[str, Any], category: str | None = None) -> list[dict[str, Any]]:
    """Return all questions in a section, optionally filtered by category."""
    questions = list(bank["sections"].get(section, {}).values())
    return [q for q in questions if category is None or q["category"] == category]


def sample_balanced(question_groups: dict[str, list[dict[str, Any]]], per_group: int, rng: random.Random) -> list[dict[str, Any]]:
    selected = []
    for group, questions in question_groups.items():
        if len(questions) < per_group:
            raise ValueError(f"Not enough questions in group {group}: need {per_group}, found {len(questions)}")
        selected.extend(rng.sample(questions, per_group))
    return selected


def generate_question_set(mode: str, seed: int | None, bank: dict[str, Any]) -> dict[str, Any]:
    """Generate a reproducible, coverage-aware question set for AI orchestration.

    This function selects only fixed-scale items. Dynamic skill follow-ups and
    adaptive open tasks remain explicitly marked for the AI orchestrator.
    """
    source = bank
    if mode not in source["generation_blueprints"]:
        raise ValueError(f"Unknown generation mode: {mode}")
    rng = random.Random(seed)
    blueprint = source["generation_blueprints"][mode]

    basic_pool = questions_in("basic_information", source)
    basic_spec = blueprint["basic_information"]
    if basic_spec.get("fixed_flow"):
        by_id = {question["id"]: question for question in basic_pool}
        basic = [by_id[question_id] for question_id in basic_spec["question_ids"]]
    else:
        basic_count = basic_spec.get("min", basic_spec.get("count", 8))
        basic = rng.sample(basic_pool, min(basic_count, len(basic_pool)))

    interest_pool = questions_in("interests_and_values", source)
    riasec_groups = {
        letter: [q for q in interest_pool if re.fullmatch(rf"{letter}\d+", q["id"])]
        for letter in "RIASEC"
    }
    riasec_spec = blueprint["riasec"]
    per_group = next(iter(riasec_spec["balance"].values()))
    interests = sample_balanced(riasec_groups, per_group, rng)

    career_values = []
    value_spec = blueprint.get("career_values")
    if value_spec:
        value_activities = [q for q in interest_pool if q["id"].startswith("VALUE_")]
        value_count = value_spec.get("ranking_activities", 2)
        career_values = rng.sample(value_activities, min(value_count, len(value_activities)))

    deep_open = []
    deep_spec = blueprint.get("deep_open_questions")
    if deep_spec:
        deep_pool = [q for q in interest_pool if q["category"] == "g_cau_hoi_mo_rong_co_hoi"]
        deep_open = rng.sample(deep_pool, min(deep_spec.get("count", 4), len(deep_pool)))

    habit_pool = [q for q in questions_in("daily_habits", source) if q["id"].startswith("H")]
    habit_count = blueprint["daily_habits"].get("min", blueprint["daily_habits"].get("count", 8))
    habits_by_category: dict[str, list[dict[str, Any]]] = {}
    for question in habit_pool:
        habits_by_category.setdefault(question["category"], []).append(question)
    habits = sample_balanced(habits_by_category, 1, rng)
    remaining = [q for q in habit_pool if q not in habits]
    habits.extend(rng.sample(remaining, max(0, habit_count - len(habits))))

    habit_context = []
    context_spec = blueprint.get("habit_context_questions")
    if context_spec:
        context_pool = [q for q in questions_in("daily_habits", source) if not q["id"].startswith("H")]
        habit_context = rng.sample(context_pool, min(context_spec.get("count", 4), len(context_pool)))

    current_skills = []
    skill_spec = blueprint.get("current_skills")
    if skill_spec:
        skill_pool = questions_in("current_skills", source)
        skill_count = skill_spec.get("min", skill_spec.get("count", 5))
        current_skills = rng.sample(skill_pool, min(skill_count, len(skill_pool)))

    task_pool = questions_in("ability_tasks", source)
    task_spec = blueprint["ability_tasks"]
    tasks_by_dimension: dict[str, list[dict[str, Any]]] = {}
    for task in task_pool:
        tasks_by_dimension.setdefault(task["category"], []).append(task)
    if task_spec.get("one_per_dimension"):
        tasks = sample_balanced(tasks_by_dimension, 1, rng)
    else:
        dimensions = rng.sample(list(tasks_by_dimension), task_spec["count"])
        tasks = [rng.choice(tasks_by_dimension[dimension]) for dimension in dimensions]

    selected = basic + interests + career_values + deep_open + habits + habit_context + current_skills + tasks
    seen_ids, seen_prompts, unique = set(), set(), []
    for question in selected:
        normalized_prompt = " ".join(question["prompt"].casefold().split())
        if question["id"] in seen_ids or normalized_prompt in seen_prompts:
            continue
        seen_ids.add(question["id"])
        seen_prompts.add(normalized_prompt)
        unique.append(question)
    selected = unique
    return {
        "mode": mode,
        "seed": seed,
        "question_ids": [q["id"] for q in selected],
        "questions": selected,
        "ai_instructions": {
            "dynamic_skill_items": blueprint.get("current_skills"),
            "adaptive_open_questions": blueprint.get("deep_open_questions"),
            "selection_rules": source["selection_rules"],
        },
    }


def validate_question_bank(bank: dict[str, Any]) -> list[str]:
    """Return validation errors; an empty list means the bank is structurally valid."""
    errors, seen = [], set()
    for section, questions in bank["sections"].items():
        for question_id, question in questions.items():
            if question_id in seen:
                errors.append(f"Duplicate ID: {question_id}")
            seen.add(question_id)
            if question.get("id") != question_id:
                errors.append(f"Dictionary key does not match id: {section}.{question_id}")
            if not question.get("prompt"):
                errors.append(f"Missing prompt: {question_id}")
    for dimension in bank["rubrics"]:
        count = len(questions_in("ability_tasks", bank, dimension))
        if count < 1:
            errors.append(f"No ability task for rubric dimension: {dimension}")
    return errors
