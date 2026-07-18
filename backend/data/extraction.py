from __future__ import annotations

import json
import html
import re
import unicodedata
from pathlib import Path
from rapidfuzz import fuzz
from bs4 import BeautifulSoup

from .models import SkillMention
from .normalization import match_text


NEGATION_MARKERS = ["không bắt buộc", "không yêu cầu", "không cần", "not required"]
PREFERRED_MARKERS = ["là lợi thế", "ưu tiên", "preferred", "nice to have"]


def clean_extraction_text(value: str | None) -> str:
    """Clean text while retaining line boundaries used for skill context."""
    if not value:
        return ""

    text = html.unescape(str(value))
    text = BeautifulSoup(text, "html.parser").get_text("\n")
    text = unicodedata.normalize("NFC", text).replace("\u200b", " ")
    text = re.sub(r"[^\S\r\n]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def normalize_title_for_matching(title_raw: str) -> str:
    """Remove recruitment metadata while preserving the actual role title."""
    title = match_text(title_raw)
    title = re.sub(r"^\s*\[[^]]+\]\s*", "", title)
    title = re.sub(
        r"^(?:(?:gấp|tuyển dụng|tuyển|cần)\s+)+",
        "",
        title,
    )
    title = re.sub(r"^\d+\s+bạn\s+", "", title)
    title = re.sub(
        r"\([^)]*(?:lương|salary|gross)[^)]*\)",
        " ",
        title,
    )
    title = re.sub(
        r"(?:[-–—~]\s*)?\d+(?:[.,]\d+)?\s*"
        r"(?:-|–|—)\s*\d+(?:[.,]\d+)?\s*"
        r"(?:m|triệu)(?:\s+gross)?(?:\s*-.*)?$",
        " ",
        title,
    )
    return re.sub(r"\s+", " ", title).strip(" -–—")


def load_taxonomy(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize_career(title_raw: str, taxonomy: dict) -> tuple[str | None, str | None, float]:
    title = normalize_title_for_matching(title_raw)

    aliases = [
        (match_text(alias), career)
        for career in taxonomy.get("careers", [])
        for alias in career.get("aliases", [])
        if match_text(alias)
    ]

    for alias, career in aliases:
        if alias == title:
            return career["career_id"], career["canonical_name"], 1.0

    # Prefer a specific multi-word alias contained in a noisy title before
    # fuzzy matching. Short/generic aliases are intentionally excluded.
    for alias, career in sorted(
        aliases,
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if len(alias) >= 8 and len(alias.split()) >= 2:
            pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
            if re.search(pattern, title):
                return career["career_id"], career["canonical_name"], 0.96

    best = None
    for alias, career in aliases:
        score = fuzz.token_set_ratio(title, alias) / 100
        specificity = len(alias)
        if best is None or (score, specificity) > (best[0], best[1]):
            best = (score, specificity, career)

    if best and best[0] >= 0.90:
        return best[2]["career_id"], best[2]["canonical_name"], round(best[0], 3)

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


def extract_skills(
    description: str,
    taxonomy: dict,
    *,
    default_requirement_level: str = "required",
) -> list[SkillMention]:
    if default_requirement_level not in {
        "required",
        "preferred",
        "mentioned",
    }:
        raise ValueError("default_requirement_level không hợp lệ.")

    original_text = clean_extraction_text(description)
    text = original_text.casefold()
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
                    level = default_requirement_level
                    confidence = 0.85 if level == "mentioned" else 0.90

                candidate = SkillMention(
                    skill_id=skill["skill_id"],
                    skill_name=skill["canonical_name"],
                    raw_mention=original_text[match.start():match.end()],
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
