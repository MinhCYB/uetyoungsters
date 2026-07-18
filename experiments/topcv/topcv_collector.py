from __future__ import annotations

import hashlib
import json
import random
import re
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.yaml"


def load_source_config(source_id: str) -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    for source in config.get("sources", []):
        if source.get("source_id") == source_id:
            if not source.get("enabled", False):
                raise RuntimeError(f"Nguồn {source_id!r} đang bị tắt trong cấu hình.")
            return source

    raise KeyError(f"Không tìm thấy cấu hình nguồn {source_id!r}.")


SOURCE_CONFIG = load_source_config("topcv")
CRAWL_CONFIG = SOURCE_CONFIG.get("crawl", {})

BASE_URL = str(SOURCE_CONFIG["base_url"]).rstrip("/")
ROBOTS_URL = f"{BASE_URL}/robots.txt"
LISTING_URL = str(
    SOURCE_CONFIG.get("listing_url", f"{BASE_URL}/viec-lam-tot-nhat")
)

MAX_JOBS = int(CRAWL_CONFIG.get("max_jobs", 30))
MAX_LISTING_PAGES = int(CRAWL_CONFIG.get("max_listing_pages", 3))
MIN_DELAY_SECONDS = float(CRAWL_CONFIG.get("delay_seconds_min", 4))
MAX_DELAY_SECONDS = float(CRAWL_CONFIG.get("delay_seconds_max", 7))
TIMEOUT_SECONDS = float(CRAWL_CONFIG.get("timeout_seconds", 30))
RETRIES = int(CRAWL_CONFIG.get("retries", 2))
USER_AGENT = str(SOURCE_CONFIG["user_agent"])

# Chỉ dùng product token để đối chiếu robots.txt.
ROBOTS_USER_AGENT = "UETCareerResearchBot"

RAW_ROOT = PROJECT_ROOT / "data" / "raw" / str(SOURCE_CONFIG["source_id"])
INTERIM_ROOT = PROJECT_ROOT / "data" / "interim"

JOB_PATH_PATTERN = re.compile(
    r"^/viec-lam/[^/]+/\d+\.html$",
    flags=re.IGNORECASE,
)


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7",
        }
    )

    # Chỉ retry lỗi máy chủ; không retry 403 hoặc 429.
    retry = Retry(
        total=RETRIES,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods={"GET"},
        raise_on_status=False,
    )

    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def load_robots_parser(
    session: requests.Session,
) -> urllib.robotparser.RobotFileParser:
    """
    Tải robots.txt một lần và chuẩn hóa các directive.

    TopCV có thể trả nhiều directive trên cùng một dòng,
    khiến urllib.robotparser hiểu sai cấu trúc file.
    """
    try:
        response = session.get(ROBOTS_URL, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Không tải được robots.txt, dừng crawl: {exc}"
        ) from exc

    robots_text = response.text.replace("\r\n", "\n").replace("\r", "\n")

    # Tách các directive nếu chúng đang nằm chung trên một dòng.
    directive_pattern = (
        r"\s+(?="
        r"(?:User-agent|Allow|Disallow|Sitemap|Crawl-delay)"
        r"\s*:)"
    )

    normalized_text = re.sub(
        directive_pattern,
        "\n",
        robots_text,
        flags=re.IGNORECASE,
    ).strip()

    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(ROBOTS_URL)
    parser.parse(normalized_text.splitlines())

    print("Robots.txt sau khi chuẩn hóa:")
    for line in normalized_text.splitlines():
        print(f"  {line}")

    return parser


def normalize_job_url(href: str | None) -> str | None:
    """Chuyển href thành URL tuyệt đối và bỏ query tracking."""
    if not href:
        return None

    absolute_url = urljoin(BASE_URL, href.strip())
    parsed = urlsplit(absolute_url)
    hostname = (parsed.hostname or "").lower()

    if hostname not in {"topcv.vn", "www.topcv.vn"}:
        return None

    if not JOB_PATH_PATTERN.match(parsed.path):
        return None

    return urlunsplit(
        (
            "https",
            "www.topcv.vn",
            parsed.path,
            "",
            "",
        )
    )


def extract_job_urls_from_listing(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    seen: set[str] = set()

    for link in soup.select("a[href]"):
        normalized_url = normalize_job_url(link.get("href"))

        if not normalized_url or normalized_url in seen:
            continue

        seen.add(normalized_url)
        urls.append(normalized_url)

    return urls


def discover_job_urls_from_listing(
    session: requests.Session,
    robots_parser: urllib.robotparser.RobotFileParser,
    max_jobs: int = MAX_JOBS,
    max_pages: int = MAX_LISTING_PAGES,
) -> list[str]:
    """
    Lấy URL việc làm từ các trang danh sách công khai.

    Không dùng sitemap vì sitemap đang trả HTTP 403.
    """
    collected_urls: list[str] = []
    seen_urls: set[str] = set()

    for page in range(1, max_pages + 1):
        listing_url = LISTING_URL if page == 1 else f"{LISTING_URL}?page={page}"

        if not robots_parser.can_fetch(ROBOTS_USER_AGENT, listing_url):
            print(
                f"[SKIP] robots.txt không cho phép trang danh sách: "
                f"{listing_url}"
            )
            break

        print(f"[LIST PAGE {page}] {listing_url}")

        try:
            response = session.get(listing_url, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            print(f"[WARN] Không tải được trang danh sách: {exc}")
            break

        if response.status_code in {403, 429}:
            print(
                f"[STOP] Trang danh sách trả HTTP "
                f"{response.status_code}. Dừng thu thập."
            )
            break

        if response.status_code != 200:
            print(f"[WARN] Trang danh sách trả HTTP {response.status_code}")
            break

        page_urls = extract_job_urls_from_listing(response.text)
        print(f"  Tìm thấy {len(page_urls)} URL việc làm trên trang {page}.")

        new_url_count = 0

        for url in page_urls:
            if url in seen_urls:
                continue

            seen_urls.add(url)
            collected_urls.append(url)
            new_url_count += 1

            if len(collected_urls) >= max_jobs:
                return collected_urls

        if new_url_count == 0:
            print("[STOP] Không có URL mới.")
            break

        if page < max_pages:
            delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
            time.sleep(delay)

    return collected_urls


def find_jobposting(value: Any) -> dict[str, Any] | None:
    """
    Tìm object có @type = JobPosting trong JSON-LD,
    kể cả khi nằm trong @graph hoặc danh sách.
    """
    if isinstance(value, list):
        for item in value:
            found = find_jobposting(item)
            if found:
                return found

    if isinstance(value, dict):
        item_type = value.get("@type")

        if item_type == "JobPosting":
            return value

        if isinstance(item_type, list) and "JobPosting" in item_type:
            return value

        for child in value.values():
            found = find_jobposting(child)
            if found:
                return found

    return None


def extract_json_ld(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.select('script[type="application/ld+json"]'):
        raw_json = script.string or script.get_text(strip=True)

        if not raw_json:
            continue

        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        jobposting = find_jobposting(parsed)
        if jobposting:
            return jobposting

    return None


def clean_html_text(value: Any) -> str | None:
    if value is None:
        return None

    text = BeautifulSoup(str(value), "html.parser").get_text(
        " ",
        strip=True,
    )

    return re.sub(r"\s+", " ", text).strip() or None


def get_nested(data: Any, *keys: str) -> Any:
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def normalize_job_locations(job: dict[str, Any]) -> str | None:
    locations = job.get("jobLocation")

    if not locations:
        return None

    if isinstance(locations, dict):
        locations = [locations]

    results: list[str] = []

    for location in locations:
        address = location.get("address", {}) if isinstance(location, dict) else {}

        if isinstance(address, str):
            results.append(address)
            continue

        parts = [
            address.get("streetAddress"),
            address.get("addressLocality"),
            address.get("addressRegion"),
            address.get("addressCountry"),
        ]

        text = ", ".join(str(part) for part in parts if part)

        if text and text not in results:
            results.append(text)

    return " | ".join(results) or None


def parse_salary(job: dict[str, Any]) -> dict[str, Any]:
    salary = job.get("baseSalary") or {}

    if not isinstance(salary, dict):
        return {
            "salary_currency_raw": None,
            "salary_min_raw": None,
            "salary_max_raw": None,
            "salary_unit_raw": None,
        }

    value = salary.get("value") or {}

    if not isinstance(value, dict):
        value = {}

    return {
        "salary_currency_raw": salary.get("currency"),
        "salary_min_raw": value.get("minValue"),
        "salary_max_raw": value.get("maxValue"),
        "salary_unit_raw": value.get("unitText"),
    }


def extract_job_id(url: str) -> str:
    normal_match = re.search(r"/(\d+)\.html$", url)

    if normal_match:
        return normal_match.group(1)

    brand_match = re.search(r"-j(\d+)\.html$", url)

    if brand_match:
        return brand_match.group(1)

    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def fallback_parse_html(
    soup: BeautifulSoup,
    url: str,
) -> dict[str, Any]:
    """
    Fallback tối thiểu khi trang không có JSON-LD.

    Không cố lấy mọi trường bằng selector dễ vỡ.
    Các trường chi tiết hơn sẽ được bổ sung sau khi
    kiểm tra HTML thực tế của nhiều trang.
    """
    title_element = soup.select_one("h1")
    canonical_element = soup.select_one('link[rel="canonical"]')

    title = (
        clean_html_text(title_element.get_text(" ", strip=True))
        if title_element
        else None
    )

    return {
        "source": "topcv",
        "source_job_id": extract_job_id(url),
        "source_url": url,
        "canonical_url": canonical_element.get("href") if canonical_element else url,
        "job_title_raw": title,
        "company_name_raw": None,
        "location_raw": None,
        "description_raw": None,
        "date_posted_raw": None,
        "valid_through_raw": None,
        "employment_type_raw": None,
        "salary_currency_raw": None,
        "salary_min_raw": None,
        "salary_max_raw": None,
        "salary_unit_raw": None,
        "parser_method": "html_fallback",
    }


def parse_job_page(
    html: str,
    url: str,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    job = extract_json_ld(soup)

    if not job:
        return fallback_parse_html(soup, url)

    organization = job.get("hiringOrganization") or {}

    if not isinstance(organization, dict):
        organization = {}

    identifier = job.get("identifier") or {}

    if not isinstance(identifier, dict):
        identifier = {}

    salary_fields = parse_salary(job)

    record = {
        "source": "topcv",
        "source_job_id": (
            str(identifier.get("value"))
            if identifier.get("value")
            else extract_job_id(url)
        ),
        "source_url": url,
        "canonical_url": job.get("url") or url,
        "job_title_raw": clean_html_text(job.get("title")),
        "company_name_raw": clean_html_text(organization.get("name")),
        "location_raw": normalize_job_locations(job),
        "description_raw": clean_html_text(job.get("description")),
        "date_posted_raw": job.get("datePosted"),
        "valid_through_raw": job.get("validThrough"),
        "employment_type_raw": job.get("employmentType"),
        "experience_raw": clean_html_text(job.get("experienceRequirements")),
        "skills_raw": job.get("skills"),
        "parser_method": "json_ld",
        **salary_fields,
    }

    return record


def crawl_topcv(max_jobs: int = MAX_JOBS) -> pd.DataFrame:
    session = create_session()
    robots_parser = load_robots_parser(session)

    listing_url = LISTING_URL

    if not robots_parser.can_fetch(
        ROBOTS_USER_AGENT,
        listing_url,
    ):
        raise PermissionError(
            f"robots.txt không cho phép crawl: {listing_url}"
        )

    print(f"[ROBOTS OK] Có thể truy cập: {listing_url}")
    print("Đang tìm URL việc làm từ trang danh sách...")
    urls = discover_job_urls_from_listing(
        session=session,
        robots_parser=robots_parser,
        max_jobs=max_jobs,
        max_pages=MAX_LISTING_PAGES,
    )

    print(f"Tìm thấy {len(urls)} URL phù hợp.")

    if not urls:
        raise RuntimeError(
            "Không tìm thấy URL việc làm. "
            "Không tạo file parquet rỗng; hãy kiểm tra log HTTP phía trên."
        )

    crawl_date = datetime.now().strftime("%Y-%m-%d")
    raw_dir = RAW_ROOT / crawl_date
    raw_dir.mkdir(parents=True, exist_ok=True)
    INTERIM_ROOT.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []

    for index, url in enumerate(urls, start=1):
        if not robots_parser.can_fetch(
            ROBOTS_USER_AGENT,
            url,
        ):
            print(f"[SKIP] robots.txt không cho phép: {url}")
            continue

        print(f"[{index}/{len(urls)}] {url}")

        try:
            response = session.get(url, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            print(f"[ERROR] Request thất bại: {exc}")
            continue

        # Không tìm cách vượt qua giới hạn.
        if response.status_code in {403, 429}:
            print(
                f"[STOP] Nhận HTTP {response.status_code}. "
                "Dừng crawl để tránh gây tải hoặc vi phạm giới hạn."
            )
            break

        if response.status_code != 200:
            print(f"[SKIP] HTTP {response.status_code}")
            continue

        html_bytes = response.content
        content_hash = hashlib.sha256(html_bytes).hexdigest()
        job_id = extract_job_id(url)

        raw_path = raw_dir / f"{job_id}.html"
        raw_path.write_bytes(html_bytes)

        try:
            record = parse_job_page(response.text, url)
        except Exception as exc:
            print(f"[ERROR] Parse thất bại: {exc}")
            continue

        record.update(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "http_status": response.status_code,
                "content_hash_sha256": content_hash,
                "raw_content_path": str(raw_path.relative_to(PROJECT_ROOT)),
                "collector_version": "0.1.0",
                "parser_version": "0.1.0",
            }
        )

        records.append(record)

        # Delay ngẫu nhiên, chỉ một request tại một thời điểm.
        delay = random.uniform(
            MIN_DELAY_SECONDS,
            MAX_DELAY_SECONDS,
        )
        time.sleep(delay)

    dataframe = pd.DataFrame(records)

    output_path = INTERIM_ROOT / "topcv_jobs_raw.parquet"
    dataframe.to_parquet(output_path, index=False)

    print(f"Đã lưu {len(dataframe)} bản ghi vào:")
    print(output_path)

    return dataframe


if __name__ == "__main__":
    df = crawl_topcv(max_jobs=MAX_JOBS)

    if not df.empty:
        columns = [
            "source_job_id",
            "job_title_raw",
            "company_name_raw",
            "location_raw",
            "parser_method",
        ]

        existing_columns = [
            column for column in columns if column in df.columns
        ]

        print(df[existing_columns].head(10).to_string(index=False))
