from __future__ import annotations

import hashlib
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_URL = "https://viecoi.vn"
DEFAULT_LISTING_URL = "https://viecoi.vn/tim-viec/all.html"

JOB_PATH_PATTERN = re.compile(
    r"^/viec-lam/.+-(?P<job_id>\d+)\.html/?$",
    flags=re.IGNORECASE,
)

SALARY_PATTERNS = [
    re.compile(
        r"(?P<salary>\d+(?:[.,]\d+)?\s*[-–—]\s*"
        r"\d+(?:[.,]\d+)?\s*(?:triệu|tr)\b)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?P<salary>(?:từ|đến|upto|up\s*to)\s*"
        r"\d+(?:[.,]\d+)?\s*(?:triệu|tr)\b)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?P<salary>(?:thỏa|thoả)\s*thuận)",
        flags=re.IGNORECASE,
    ),
]

DATE_PATTERN = re.compile(
    r"\b\d{1,2}/\d{1,2}/\d{4}\b"
)

COMPANY_PATTERN = re.compile(
    r"\b("
    r"công ty|cty|tnhh|cổ phần|tập đoàn|"
    r"company|corporation|ltd|jsc|group|"
    r"doanh nghiệp|xí nghiệp"
    r")\b",
    flags=re.IGNORECASE,
)

CARD_NOISE = {
    "gấp",
    "hot",
    "mới",
    "tin mới",
    "ưu tiên",
    "nổi bật",
    "ứng tuyển",
    "xem chi tiết",
    "lưu việc làm",
    "nộp đơn",
}

LOCATION_HINTS = [
    "TPHCM",
    "TP.HCM",
    "Hồ Chí Minh",
    "Hà Nội",
    "Đà Nẵng",
    "Bình Dương",
    "Đồng Nai",
    "Bắc Ninh",
    "Hải Phòng",
    "Cần Thơ",
    "Long An",
    "Bà Rịa - Vũng Tàu",
    "Vũng Tàu",
    "Toàn quốc",
]


def create_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7",
        }
    )

    retry = Retry(
        total=2,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods={"GET"},
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def clean_text(value: Any) -> str | None:
    if value is None:
        return None

    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def build_page_url(base_url: str, page_number: int) -> str:
    if page_number <= 1:
        return base_url

    parsed = urlsplit(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["page"] = str(page_number)

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


def normalize_job_url(href: str | None) -> str | None:
    if not href:
        return None

    absolute_url = urljoin(BASE_URL, href.strip())
    parsed = urlsplit(absolute_url)
    hostname = (parsed.hostname or "").lower()

    if hostname not in {"viecoi.vn", "www.viecoi.vn"}:
        return None

    path = parsed.path.rstrip("/")

    # Các trang danh mục có URL giống job nhưng không phải tin tuyển dụng.
    if path.casefold().startswith("/viec-lam/danh-muc-"):
        return None

    if not JOB_PATH_PATTERN.match(path):
        return None

    return urlunsplit(("https", "viecoi.vn", path, "", ""))


def extract_job_id(url: str) -> str | None:
    match = JOB_PATH_PATTERN.match(urlsplit(url).path.rstrip("/"))
    return match.group("job_id") if match else None


def job_links_in_node(node: Tag) -> set[str]:
    urls: set[str] = set()

    for anchor in node.select("a[href]"):
        url = normalize_job_url(anchor.get("href"))
        if url:
            urls.add(url)

    return urls


def find_job_card(
    anchor: Tag,
    job_url: str,
) -> Tag | None:
    """
    Chọn ancestor có đầy đủ nội dung card nhất.

    Không chọn ancestor đầu tiên vì nó có thể chỉ chứa
    tiêu đề và tên công ty.
    """
    best_parent: Tag | None = None
    best_score = -1
    best_length = -1

    for parent in anchor.parents:
        if not isinstance(parent, Tag):
            continue

        if parent.name in {"body", "html"}:
            break

        text = clean_text(parent.get_text("\n", strip=True)) or ""

        if not 40 <= len(text) <= 3000:
            continue

        urls = job_links_in_node(parent)

        if urls != {job_url}:
            continue

        score = 0

        if any(pattern.search(text) for pattern in SALARY_PATTERNS):
            score += 5

        if DATE_PATTERN.search(text):
            score += 4

        if any(
            hint.casefold() in text.casefold()
            for hint in LOCATION_HINTS
        ):
            score += 3

        if COMPANY_PATTERN.search(text):
            score += 2

        if "," in text:
            score += 1

        if score > best_score or (
            score == best_score and len(text) > best_length
        ):
            best_parent = parent
            best_score = score
            best_length = len(text)

    return best_parent


def extract_lines(card: Tag) -> list[str]:
    raw_text = card.get_text("\n", strip=True)
    lines: list[str] = []
    seen: set[str] = set()

    for raw_line in raw_text.splitlines():
        line = clean_text(raw_line)

        if not line:
            continue

        key = line.casefold()

        if key in seen:
            continue

        seen.add(key)
        lines.append(line)

    return lines


def extract_salary(
    lines: list[str],
    title: str,
) -> str | None:
    """
    Chỉ nhận lương từ dòng riêng của card.

    Không lấy chuỗi lương xuất hiện bên trong tiêu đề.
    """
    title_key = title.casefold()

    for line in lines:
        if line.casefold() == title_key:
            continue

        for pattern in SALARY_PATTERNS:
            match = pattern.search(line)

            if match:
                return clean_text(match.group("salary"))

    return None


def extract_deadline(lines: list[str]) -> str | None:
    for line in lines:
        match = DATE_PATTERN.search(line)

        if match:
            return match.group(0)

    return None


def extract_location(
    lines: list[str],
    title: str,
) -> str | None:
    title_key = title.casefold()

    # Cách 1: nhận diện trực tiếp bằng alias địa điểm.
    for line in lines:
        if line.casefold() == title_key:
            continue

        normalized = line.casefold()

        for hint in LOCATION_HINTS:
            if hint.casefold() in normalized:
                return line

    # Cách 2: theo cấu trúc: salary → location → deadline.
    salary_index: int | None = None
    deadline_index: int | None = None

    for index, line in enumerate(lines):
        if line.casefold() == title_key:
            continue

        if salary_index is None and any(
            pattern.search(line) for pattern in SALARY_PATTERNS
        ):
            salary_index = index

        if deadline_index is None and DATE_PATTERN.search(line):
            deadline_index = index

    if (
        salary_index is not None
        and deadline_index is not None
        and deadline_index > salary_index + 1
    ):
        candidates = lines[salary_index + 1 : deadline_index]

        for candidate in candidates:
            normalized = candidate.casefold()

            if normalized in CARD_NOISE:
                continue

            if COMPANY_PATTERN.search(candidate):
                continue

            if 2 <= len(candidate) <= 100:
                return candidate

    return None


def infer_company(
    lines: list[str],
    title: str,
    salary_raw: str | None,
    location_raw: str | None,
    deadline_raw: str | None,
) -> str | None:
    excluded = {
        value.casefold()
        for value in [
            title,
            salary_raw,
            location_raw,
            deadline_raw,
        ]
        if value
    }

    candidates: list[str] = []

    for line in lines:
        normalized = line.casefold()

        if normalized in excluded:
            continue

        if normalized in CARD_NOISE:
            continue

        if DATE_PATTERN.search(line):
            continue

        if any(pattern.search(line) for pattern in SALARY_PATTERNS):
            continue

        if len(line) < 3 or len(line) > 240:
            continue

        candidates.append(line)

    for candidate in candidates:
        if COMPANY_PATTERN.search(candidate):
            return candidate

    return candidates[0] if candidates else None


def infer_skills(
    lines: list[str],
    *,
    title: str,
    company: str | None,
    salary_raw: str | None,
    location_raw: str | None,
    deadline_raw: str | None,
) -> list[str]:
    excluded = {
        value.casefold()
        for value in [
            title,
            company,
            salary_raw,
            location_raw,
            deadline_raw,
        ]
        if value
    }

    deadline_index: int | None = None

    for index, line in enumerate(lines):
        if DATE_PATTERN.search(line):
            deadline_index = index
            break

    candidate_lines = (
        lines[deadline_index + 1 :]
        if deadline_index is not None
        else lines
    )

    skills: list[str] = []
    seen: set[str] = set()

    for line in candidate_lines:
        if line.casefold() in excluded:
            continue

        raw_skills = (
            line.replace("...", "").split(",")
            if "," in line
            else [line]
        )

        for raw_skill in raw_skills:
            skill = clean_text(raw_skill)

            if not skill:
                continue

            if not 2 <= len(skill) <= 80:
                continue

            key = skill.casefold()

            if key in seen or key in CARD_NOISE:
                continue

            seen.add(key)
            skills.append(skill)

    return skills


def parse_listing_html(
    html: str,
    *,
    listing_url: str,
    page_number: int,
    fetched_at: str,
    raw_content_path: str,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    records: list[dict[str, Any]] = []
    seen_job_ids: set[str] = set()

    for anchor in soup.select("a[href]"):
        job_url = normalize_job_url(anchor.get("href"))

        if not job_url:
            continue

        job_id = extract_job_id(job_url)

        if not job_id or job_id in seen_job_ids:
            continue

        title = clean_text(anchor.get_text(" ", strip=True))

        if not title:
            continue

        card = find_job_card(anchor, job_url)

        if card is None:
            continue

        lines = extract_lines(card)
        card_text = "\n".join(lines)

        salary_raw = extract_salary(
            lines,
            title,
        )
        deadline_raw = extract_deadline(lines)
        location_raw = extract_location(
            lines,
            title,
        )
        company_name_raw = infer_company(
            lines,
            title,
            salary_raw,
            location_raw,
            deadline_raw,
        )
        skills = infer_skills(
            lines,
            title=title,
            company=company_name_raw,
            salary_raw=salary_raw,
            location_raw=location_raw,
            deadline_raw=deadline_raw,
        )

        content_hash = hashlib.sha256(
            card_text.encode("utf-8")
        ).hexdigest()

        records.append(
            {
                "source": "viecoi",
                "source_id": "viecoi_listing",
                "source_job_id": job_id,
                "source_url": job_url,
                "title_raw": title,
                "job_title_raw": title,
                "company_name_raw": company_name_raw,
                "location_raw": location_raw,
                "salary_raw": salary_raw,
                "skills_raw": json.dumps(
                    skills,
                    ensure_ascii=False,
                ),
                "application_deadline_raw": deadline_raw,
                "description_raw": "",
                "experience_raw": None,
                "education_raw": None,
                "posted_at_raw": None,
                "source_updated_at": None,
                "fetched_at": fetched_at,
                "collected_at": fetched_at,
                "card_text_raw": card_text,
                "content_hash_sha256": content_hash,
                "raw_content_path": raw_content_path,
                "listing_url": listing_url,
                "listing_page": page_number,
                "collector_version": "0.1.0",
                "parser_version": "listing-card-0.1.0",
                "collection_scope": "public_listing_fields_only",
            }
        )
        seen_job_ids.add(job_id)

    return records


def collect_viecoi(
    *,
    project_root: str | Path,
    listing_url: str = DEFAULT_LISTING_URL,
    max_pages: int = 1,
    max_jobs: int = 50,
    min_delay_seconds: float = 6.0,
    max_delay_seconds: float = 10.0,
    timeout_seconds: int = 30,
    user_agent: str = "UETCareerResearch/0.1 (academic project)",
) -> pd.DataFrame:
    root = Path(project_root)
    now = datetime.now(timezone.utc)
    run_stamp = now.strftime("%Y%m%dT%H%M%SZ")
    run_date = now.date().isoformat()

    raw_dir = root / "data" / "raw" / "viecoi" / run_date / run_stamp
    interim_dir = root / "data" / "interim"
    raw_dir.mkdir(parents=True, exist_ok=True)
    interim_dir.mkdir(parents=True, exist_ok=True)

    session = create_session(user_agent)
    records: list[dict[str, Any]] = []
    seen_job_ids: set[str] = set()

    for page_number in range(1, max_pages + 1):
        page_url = build_page_url(listing_url, page_number)

        print(f"[LIST {page_number}] {page_url}")

        try:
            response = session.get(page_url, timeout=timeout_seconds)
        except requests.RequestException as exc:
            print(f"[STOP] Request thất bại: {exc}")
            break

        print(f"  HTTP status: {response.status_code}")
        print(f"  HTML length: {len(response.text):,}")

        if response.status_code in {403, 429}:
            print(
                f"[STOP] Nguồn trả HTTP {response.status_code}; "
                "không tiếp tục."
            )
            break

        if response.status_code != 200:
            print(f"[STOP] HTTP {response.status_code}.")
            break

        lowered = response.text.casefold()

        if (
            "just a moment" in lowered
            or "verify you are human" in lowered
            or "captcha" in lowered
        ):
            print("[STOP] Phát hiện trang challenge/CAPTCHA.")
            break

        raw_path = raw_dir / f"listing_page_{page_number}.html"
        raw_path.write_text(response.text, encoding="utf-8")
        raw_relative_path = str(raw_path.relative_to(root))

        fetched_at = datetime.now(timezone.utc).isoformat()

        page_records = parse_listing_html(
            response.text,
            listing_url=page_url,
            page_number=page_number,
            fetched_at=fetched_at,
            raw_content_path=raw_relative_path,
        )

        new_count = 0

        for record in page_records:
            job_id = str(record["source_job_id"])

            if job_id in seen_job_ids:
                continue

            seen_job_ids.add(job_id)
            records.append(record)
            new_count += 1

            if len(records) >= max_jobs:
                break

        print(f"  Parsed jobs: {len(page_records)}")
        print(f"  New jobs: {new_count}")

        if len(records) >= max_jobs:
            break

        if new_count == 0:
            print("[STOP] Không có job mới.")
            break

        if page_number < max_pages:
            time.sleep(
                random.uniform(
                    min_delay_seconds,
                    max_delay_seconds,
                )
            )

    dataframe = pd.DataFrame(records)

    if dataframe.empty:
        print("Không thu được dữ liệu; không ghi đè file cũ.")
        return dataframe

    dataframe = (
        dataframe.drop_duplicates(
            subset=["source_id", "source_job_id"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    parquet_path = interim_dir / "viecoi_jobs_latest.parquet"
    csv_path = interim_dir / "viecoi_jobs_latest.csv"

    dataframe.to_parquet(parquet_path, index=False)
    dataframe.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\nĐã lưu {len(dataframe)} jobs:")
    print(parquet_path)
    print(csv_path)

    return dataframe
