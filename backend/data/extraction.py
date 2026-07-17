from __future__ import annotations

import json
import re
from pathlib import Path
from rapidfuzz import fuzz

from .models import SkillMention
from .normalization import match_text


NEGATION_MARKERS = ["không bắt buộc", "không yêu cầu", "không cần", "not required"]
PREFERRED_MARKERS = ["là lợi thế", "ưu tiên", "preferred", "nice to have"]


def load_taxonomy(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize_career(title_raw: str, taxonomy: dict) -> tuple[str | None, str | None, float]:
    title = match_text(title_raw)

    for career in taxonomy.get("careers", []):
        for alias in career.get("aliases", []):
            if match_text(alias) == title:
                return career["career_id"], career["canonical_name"], 1.0

    best = None
    for career in taxonomy.get("careers", []):
        for alias in career.get("aliases", []):
            score = fuzz.token_set_ratio(title, match_text(alias)) / 100
            if best is None or score > best[0]:
                best = (score, career)

    if best and best[0] >= 0.82:
        return best[1]["career_id"], best[1]["canonical_name"], round(best[0], 3)

    return None, None, 0.0


def _sentence_context(text: str, start: int, end: int) -> str:
    """Lấy đúng câu chứa skill để marker của câu sau không làm nhiễu câu trước."""
    left_candidates = [
        text.rfind(".", 0, start),
        text.rfind(";", 0, start),
        text.rfind("\n", 0, start),
    ]
    left = max(left_candidates) + 1

    right_candidates = [
        pos for pos in (
            text.find(".", end),
            text.find(";", end),
            text.find("\n", end),
        )
        if pos != -1
    ]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left:right].strip()


def extract_skills(description: str, taxonomy: dict) -> list[SkillMention]:
    text = match_text(description)
    extracted: dict[str, SkillMention] = {}

    for skill in taxonomy.get("skills", []):
        for alias in skill.get("aliases", []):
            pattern = r"(?<!\w)" + re.escape(match_text(alias)) + r"(?!\w)"
            for match in re.finditer(pattern, text):
                context = _sentence_context(text, match.start(), match.end())

                if any(marker in context for marker in NEGATION_MARKERS):
                    level = "not_required"
                    confidence = 0.98
                elif any(marker in context for marker in PREFERRED_MARKERS):
                    level = "preferred"
                    confidence = 0.95
                else:
                    level = "required"
                    confidence = 0.90

                candidate = SkillMention(
                    skill_id=skill["skill_id"],
                    skill_name=skill["canonical_name"],
                    raw_mention=match.group(0),
                    requirement_level=level,
                    confidence=confidence,
                    extraction_method="taxonomy",
                )

                priority = {"not_required": 0, "mentioned": 1, "preferred": 2, "required": 3}
                previous = extracted.get(skill["skill_id"])
                if previous is None or priority[level] > priority[previous.requirement_level]:
                    extracted[skill["skill_id"]] = candidate

    return sorted(extracted.values(), key=lambda item: item.skill_id)


def extract_experience_years(description: str | None) -> float | None:
    """Extract the minimum explicitly requested number of years."""
    text = match_text(description)
    patterns = [
        r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b",
        r"(?:at least|minimum|min)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b",
        r"(\d+(?:\.\d+)?)\s*\+?\s*năm\b",
    ]

    values = [
        float(match.group(1))
        for pattern in patterns
        for match in re.finditer(pattern, text)
    ]
    return min(values) if values else None
