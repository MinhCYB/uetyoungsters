from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime, timedelta
from dateutil import parser
from bs4 import BeautifulSoup


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = BeautifulSoup(text, "html.parser").get_text(" ")
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u200b", " ")
    return re.sub(r"\s+", " ", text).strip()


def match_text(value: str | None) -> str:
    return clean_text(value).casefold()


def normalize_company(value: str | None) -> str:
    text = match_text(value)
    text = re.sub(r"\b(công ty|cty|tnhh|cổ phần|cp|jsc|ltd|limited)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_location(raw: str | None, taxonomy: dict) -> str | None:
    text = match_text(raw)
    for item in taxonomy.get("locations", []):
        for alias in item.get("aliases", []):
            if match_text(alias) in text:
                return item["province"]
    return None


def parse_salary(raw: str | None) -> tuple[int | None, int | None, float | None, bool]:
    text = match_text(raw).replace(",", ".")
    if not text or any(token in text for token in ["thỏa thuận", "thoả thuận", "negotiable"]):
        return None, None, None, False

    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:triệu|tr|m)?\s*[-–—]\s*(\d+(?:\.\d+)?)\s*(triệu|tr|m)",
        text,
    )
    if range_match:
        low = int(float(range_match.group(1)) * 1_000_000)
        high = int(float(range_match.group(2)) * 1_000_000)
        return low, high, (low + high) / 2, True

    min_match = re.search(r"(?:từ|>=|trên)\s*(\d+(?:\.\d+)?)\s*(triệu|tr|m)", text)
    if min_match:
        low = int(float(min_match.group(1)) * 1_000_000)
        return low, None, None, True

    max_match = re.search(r"(?:up to|upto|tới|đến|<=)\s*(\d+(?:\.\d+)?)\s*(triệu|tr|m)", text)
    if max_match:
        high = int(float(max_match.group(1)) * 1_000_000)
        return None, high, None, True

    single_match = re.search(r"(\d+(?:\.\d+)?)\s*(triệu|tr|m)", text)
    if single_match:
        value = int(float(single_match.group(1)) * 1_000_000)
        return value, value, float(value), True

    return None, None, None, False


def normalize_seniority(raw: str | None) -> str:
    text = match_text(raw)
    if any(token in text for token in ["không yêu cầu", "mới tốt nghiệp", "fresher"]):
        return "fresher"
    if any(token in text for token in ["intern", "thực tập"]):
        return "intern"
    if "dưới 1 năm" in text:
        return "junior"

    years = [int(x) for x in re.findall(r"\d+", text)]
    if not years:
        return "unknown"
    maximum = max(years)
    if maximum <= 2:
        return "junior"
    if maximum <= 5:
        return "mid"
    return "senior"


def normalize_education(raw: str | None) -> str:
    text = match_text(raw)
    if not text or "không yêu cầu" in text:
        return "no_formal_requirement"
    if "trung cấp" in text:
        return "vocational_or_above"
    if "cao đẳng" in text:
        return "college_or_above"
    if "đại học" in text:
        return "university_or_above"
    return "unknown"


def parse_posted_date(raw: str | None, collected_at: datetime):
    text = match_text(raw)
    base = collected_at.date()
    if not text:
        return None
    if "hôm nay" in text:
        return base
    if "hôm qua" in text:
        return base - timedelta(days=1)
    match = re.search(r"(\d+)\s*ngày trước", text)
    if match:
        return base - timedelta(days=int(match.group(1)))
    try:
        return parser.parse(raw, dayfirst=True, fuzzy=True).date()
    except (ValueError, TypeError, OverflowError):
        return None
