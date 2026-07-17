from __future__ import annotations

import hashlib
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import (
    Browser,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


BASE_URL = "https://www.topcv.vn"
LISTING_URL = (
    f"{BASE_URL}/tim-viec-lam-moi-nhat-tai-ha-noi-l1"
)

MAX_JOBS = 1
MAX_LISTING_PAGES = 1

MIN_DELAY_SECONDS = 5
MAX_DELAY_SECONDS = 8

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = PROJECT_ROOT / "data" / "raw" / "topcv"
INTERIM_ROOT = PROJECT_ROOT / "data" / "interim"

JOB_URL_PATTERN = re.compile(
    r"^/viec-lam/[^/?]+/\d+\.html/?$",
    flags=re.IGNORECASE,
)


def random_delay() -> None:
    time.sleep(
        random.uniform(
            MIN_DELAY_SECONDS,
            MAX_DELAY_SECONDS,
        )
    )


def normalize_job_url(
    href: str | None,
) -> str | None:
    if not href:
        return None

    absolute_url = urljoin(
        BASE_URL,
        str(href).strip(),
    )
    parsed = urlsplit(absolute_url)
    hostname = (parsed.hostname or "").lower()

    if hostname not in {
        "topcv.vn",
        "www.topcv.vn",
    }:
        return None

    path = parsed.path.rstrip("/")

    if not JOB_URL_PATTERN.match(path):
        return None

    return urlunsplit(
        (
            "https",
            "www.topcv.vn",
            path,
            "",
            "",
        )
    )


def extract_job_id(url: str) -> str:
    match = re.search(r"/(\d+)\.html$", url)

    if match:
        return match.group(1)

    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()[:16]


def detect_block_page(page: Page) -> bool:
    """
    Phát hiện các dấu hiệu trang chặn/challenge phổ biến.

    Chỉ phát hiện để dừng, không vượt challenge.
    """
    try:
        title = page.title().lower()
        body_text = page.locator("body").inner_text(
            timeout=5_000
        ).lower()
    except Exception:
        return False

    suspicious_terms = [
        "captcha",
        "access denied",
        "verify you are human",
        "xác minh bạn là con người",
        "unusual traffic",
        "security check",
        "checking your browser",
    ]

    content = f"{title}\n{body_text}"

    return any(
        term in content
        for term in suspicious_terms
    )


def save_debug_artifacts(
    page: Page,
    page_number: int,
) -> None:
    debug_dir = PROJECT_ROOT / "data" / "debug" / "topcv"
    debug_dir.mkdir(parents=True, exist_ok=True)

    screenshot_path = debug_dir / f"listing_page_{page_number}.png"
    html_path = debug_dir / f"listing_page_{page_number}.html"

    try:
        page.screenshot(
            path=str(screenshot_path),
            full_page=True,
        )
    except Exception as exc:
        print(f"[DEBUG] Không chụp được screenshot: {exc}")

    try:
        html_path.write_text(
            page.content(),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[DEBUG] Không lưu được HTML: {exc}")

    print(f"[DEBUG] Screenshot: {screenshot_path}")
    print(f"[DEBUG] HTML: {html_path}")


def scroll_listing_page(page: Page) -> None:
    """Cuộn từ từ để nội dung lazy-load xuất hiện."""
    previous_height = 0

    for _ in range(8):
        current_height = page.evaluate("document.body.scrollHeight")

        if current_height == previous_height:
            break

        previous_height = current_height
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1_200)


def collect_links_from_current_page(
    page: Page,
) -> list[str]:
    """
    Đọc toàn bộ href đã gắn vào DOM.

    Không yêu cầu link phải visible.
    """
    link_locator = page.locator("a[href]")
    link_count = link_locator.count()
    print(f"  Tổng thẻ a[href] trong DOM: {link_count}")

    hrefs = link_locator.evaluate_all(
        """
        elements => elements.map(element => {
            return element.href || element.getAttribute("href");
        })
        """
    )

    urls: list[str] = []
    seen: set[str] = set()

    for href in hrefs:
        normalized = normalize_job_url(href)

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        urls.append(normalized)

    return urls


def discover_job_urls(
    page: Page,
    max_jobs: int = MAX_JOBS,
    max_pages: int = MAX_LISTING_PAGES,
) -> list[str]:
    collected: list[str] = []
    seen: set[str] = set()

    for page_number in range(1, max_pages + 1):
        listing_url = (
            LISTING_URL
            if page_number == 1
            else f"{LISTING_URL}?page={page_number}"
        )

        print(f"[LIST {page_number}] {listing_url}")

        try:
            response = page.goto(
                listing_url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )
        except PlaywrightTimeoutError:
            print("[WARN] Trang danh sách tải quá thời gian.")
            save_debug_artifacts(page, page_number)
            break

        status = response.status if response else None

        print(f"  HTTP status: {status}")
        print(f"  Final URL: {page.url}")
        print(f"  Title: {page.title()}")

        if status in {403, 429}:
            print(f"[STOP] HTTP {status}.")
            save_debug_artifacts(page, page_number)
            break

        # Đợi DOM có phần tử anchor, không cần visible.
        try:
            page.locator("a[href]").first.wait_for(
                state="attached",
                timeout=30_000,
            )
        except PlaywrightTimeoutError:
            print("[WARN] Sau 30 giây DOM vẫn không có a[href].")
            save_debug_artifacts(page, page_number)
            break

        cookie_buttons = [
            page.get_by_text("Chấp nhận tất cả", exact=True),
            page.get_by_text("Xác nhận lựa chọn", exact=True),
        ]

        for button in cookie_buttons:
            try:
                if button.first.is_visible(timeout=1_000):
                    button.first.click(timeout=3_000)
                    page.wait_for_timeout(1_000)
                    break
            except Exception:
                pass

        scroll_listing_page(page)

        if detect_block_page(page):
            print(
                "[STOP] Phát hiện CAPTCHA hoặc trang xác minh."
            )
            save_debug_artifacts(page, page_number)
            break

        page_urls = collect_links_from_current_page(page)

        print(
            f"  Tìm thấy {len(page_urls)} URL chi tiết hợp lệ."
        )

        if not page_urls:
            candidate_hrefs = page.locator(
                'a[href*="/viec-lam/"]'
            ).evaluate_all(
                """
                elements => elements
                    .map(element => element.href)
                    .slice(0, 30)
                """
            )

            print(f"  Link chứa /viec-lam/: {len(candidate_hrefs)}")

            for href in candidate_hrefs:
                print(f"    {href}")

            save_debug_artifacts(page, page_number)
            break

        new_count = 0

        for job_url in page_urls:
            if job_url in seen:
                continue

            seen.add(job_url)
            collected.append(job_url)
            new_count += 1

            if len(collected) >= max_jobs:
                return collected

        print(f"  URL mới trên trang: {new_count}")

        if new_count == 0:
            print("[STOP] Không có URL mới.")
            break

        random_delay()

    return collected


def find_jobposting(value):
    if isinstance(value, list):
        for item in value:
            found = find_jobposting(item)

            if found:
                return found

    elif isinstance(value, dict):
        item_type = value.get("@type")

        if item_type == "JobPosting":
            return value

        if (
            isinstance(item_type, list)
            and "JobPosting" in item_type
        ):
            return value

        for child in value.values():
            found = find_jobposting(child)

            if found:
                return found

    return None


def extract_json_ld(
    soup: BeautifulSoup,
) -> dict | None:
    scripts = soup.select(
        'script[type="application/ld+json"]'
    )

    for script in scripts:
        raw = script.string or script.get_text(
            strip=True
        )

        if not raw:
            continue

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue

        job = find_jobposting(parsed)

        if job:
            return job

    return None


def clean_text(value) -> str | None:
    if value is None:
        return None

    text = BeautifulSoup(
        str(value),
        "html.parser",
    ).get_text(" ", strip=True)

    text = re.sub(r"\s+", " ", text).strip()

    return text or None


def parse_locations(job: dict) -> str | None:
    locations = job.get("jobLocation")

    if not locations:
        return None

    if isinstance(locations, dict):
        locations = [locations]

    results: list[str] = []

    for location in locations:
        if not isinstance(location, dict):
            continue

        address = location.get("address", {})

        if isinstance(address, str):
            results.append(address)
            continue

        if not isinstance(address, dict):
            continue

        parts = [
            address.get("streetAddress"),
            address.get("addressLocality"),
            address.get("addressRegion"),
            address.get("addressCountry"),
        ]

        value = ", ".join(
            str(part)
            for part in parts
            if part
        )

        if value and value not in results:
            results.append(value)

    return " | ".join(results) or None


def parse_salary(job: dict) -> dict:
    salary = job.get("baseSalary") or {}

    if not isinstance(salary, dict):
        salary = {}

    value = salary.get("value") or {}

    if not isinstance(value, dict):
        value = {}

    return {
        "salary_currency_raw": salary.get("currency"),
        "salary_min_raw": value.get("minValue"),
        "salary_max_raw": value.get("maxValue"),
        "salary_unit_raw": value.get("unitText"),
    }


def parse_html_fallback(
    soup: BeautifulSoup,
    url: str,
) -> dict:
    title_element = soup.select_one("h1")

    title = (
        clean_text(
            title_element.get_text(
                " ",
                strip=True,
            )
        )
        if title_element
        else None
    )

    description_element = soup.select_one(
        "[class*='job-description'], "
        "[class*='job-detail'], "
        "[class*='description']"
    )

    return {
        "source": "topcv",
        "source_job_id": extract_job_id(url),
        "source_url": url,
        "job_title_raw": title,
        "company_name_raw": None,
        "location_raw": None,
        "description_raw": (
            clean_text(description_element)
            if description_element
            else None
        ),
        "date_posted_raw": None,
        "valid_through_raw": None,
        "employment_type_raw": None,
        "experience_raw": None,
        "skills_raw": None,
        "salary_currency_raw": None,
        "salary_min_raw": None,
        "salary_max_raw": None,
        "salary_unit_raw": None,
        "parser_method": "html_fallback",
    }


def parse_job_html(
    html: str,
    url: str,
) -> dict:
    soup = BeautifulSoup(html, "lxml")
    job = extract_json_ld(soup)

    if not job:
        return parse_html_fallback(soup, url)

    organization = (
        job.get("hiringOrganization") or {}
    )

    if not isinstance(organization, dict):
        organization = {}

    identifier = job.get("identifier") or {}

    if not isinstance(identifier, dict):
        identifier = {}

    source_job_id = (
        identifier.get("value")
        or extract_job_id(url)
    )

    return {
        "source": "topcv",
        "source_job_id": str(source_job_id),
        "source_url": url,
        "job_title_raw": clean_text(
            job.get("title")
        ),
        "company_name_raw": clean_text(
            organization.get("name")
        ),
        "location_raw": parse_locations(job),
        "description_raw": clean_text(
            job.get("description")
        ),
        "date_posted_raw": job.get("datePosted"),
        "valid_through_raw": job.get("validThrough"),
        "employment_type_raw": job.get(
            "employmentType"
        ),
        "experience_raw": clean_text(
            job.get("experienceRequirements")
        ),
        "skills_raw": job.get("skills"),
        "parser_method": "json_ld",
        **parse_salary(job),
    }


def ensure_listing_ready(page: Page) -> None:
    """
    Đảm bảo trang hiện tại là trang danh sách và các link job đã xuất hiện.
    """
    if not page.url.startswith(LISTING_URL):
        print("[BACK] Quay lại trang danh sách...")

        try:
            page.go_back(
                wait_until="domcontentloaded",
                timeout=60_000,
            )
        except PlaywrightTimeoutError:
            page.goto(
                LISTING_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

    page.locator("a[href]").first.wait_for(
        state="attached",
        timeout=30_000,
    )

    page.wait_for_timeout(2_000)


def find_job_link(
    page: Page,
    job_url: str,
):
    """
    Tìm link theo job ID thay vì so khớp toàn bộ URL,
    vì href trên TopCV có thể chứa query tracking.
    """
    job_id = extract_job_id(job_url)

    locator = page.locator(
        f'a[href*="/{job_id}.html"]'
    ).first

    if locator.count() == 0:
        scroll_listing_page(page)

    if locator.count() == 0:
        return None

    return locator


def open_job_by_click(
    page: Page,
    job_url: str,
):
    """
    Click link thật trên trang danh sách.

    Loại bỏ target="_blank" chỉ để giữ điều hướng trong cùng một tab,
    giúp việc quay lại trang danh sách ổn định hơn.
    """
    job_id = extract_job_id(job_url)
    link = find_job_link(page, job_url)

    if link is None:
        raise RuntimeError(
            f"Không tìm thấy link của job ID {job_id}"
        )

    link.scroll_into_view_if_needed(
        timeout=15_000,
    )

    # Đảm bảo link thực sự đang nhìn thấy được.
    link.wait_for(
        state="visible",
        timeout=15_000,
    )

    actual_href = link.get_attribute("href")
    print(f"  Link trên DOM: {actual_href}")

    # Giữ điều hướng trong cùng tab.
    link.evaluate(
        """
        element => {
            element.removeAttribute("target");
        }
        """
    )

    try:
        with page.expect_response(
            lambda response: (
                response.request.is_navigation_request()
                and f"/{job_id}.html" in response.url
            ),
            timeout=60_000,
        ) as response_info:
            link.click(
                timeout=20_000,
            )

        response = response_info.value

    except PlaywrightTimeoutError as exc:
        raise RuntimeError(
            f"Click job {job_id} nhưng không nhận được "
            "navigation response."
        ) from exc

    page.wait_for_url(
        re.compile(
            rf"/{job_id}\.html(?:[?#].*)?$",
            flags=re.IGNORECASE,
        ),
        timeout=60_000,
        wait_until="domcontentloaded",
    )

    page.wait_for_timeout(3_000)

    return response


def crawl_detail_pages_from_listing(
    listing_page: Page,
    urls: list[str],
) -> pd.DataFrame:
    crawl_date = datetime.now().strftime("%Y-%m-%d")
    raw_dir = RAW_ROOT / crawl_date

    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    INTERIM_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    records: list[dict] = []

    for index, url in enumerate(urls, start=1):
        print(f"[{index}/{len(urls)}] {url}")

        try:
            ensure_listing_ready(listing_page)
        except Exception as exc:
            print(
                f"[STOP] Không quay lại được trang danh sách: {exc}"
            )
            break

        job_id = extract_job_id(url)

        try:
            response = open_job_by_click(
                page=listing_page,
                job_url=url,
            )
        except Exception as exc:
            print(f"[SKIP] Không mở được job {job_id}: {exc}")
            continue

        status = response.status
        final_url = listing_page.url

        print(f"  HTTP status: {status}")
        print(f"  Final URL: {final_url}")
        print(f"  Title: {listing_page.title()}")

        if status in {403, 429}:
            print(
                f"[STOP] Trang chi tiết trả HTTP {status}."
            )

            save_debug_artifacts(
                listing_page,
                page_number=999,
            )
            break

        if status != 200:
            print(
                f"[SKIP] Trang chi tiết trả HTTP {status}."
            )
            continue

        if detect_block_page(listing_page):
            print(
                "[STOP] Phát hiện CAPTCHA hoặc trang xác minh."
            )

            save_debug_artifacts(
                listing_page,
                page_number=999,
            )
            break

        html = listing_page.content()
        html_bytes = html.encode("utf-8")

        content_hash = hashlib.sha256(
            html_bytes
        ).hexdigest()

        raw_path = raw_dir / f"{job_id}.html"
        raw_path.write_bytes(html_bytes)

        try:
            record = parse_job_html(
                html=html,
                url=final_url,
            )
        except Exception as exc:
            print(f"[SKIP] Lỗi parse job {job_id}: {exc}")
            continue

        record.update(
            {
                "fetched_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "http_status": status,
                "content_hash_sha256": content_hash,
                "raw_content_path": str(
                    raw_path.relative_to(
                        PROJECT_ROOT
                    )
                ),
                "collector_version": "0.3.0",
                "parser_version": "0.2.0",
                "navigation_method": "listing_link_click",
            }
        )

        records.append(record)

        print(
            f"  [OK] {record.get('job_title_raw')}"
        )

        # Quay lại listing trước khi sang job tiếp theo.
        try:
            listing_page.go_back(
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            listing_page.wait_for_timeout(2_000)

        except PlaywrightTimeoutError:
            print(
                "[WARN] go_back timeout, tải lại listing."
            )

            listing_page.goto(
                LISTING_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

        random_delay()

    return pd.DataFrame(records)

def crawl_topcv(
    max_jobs: int = MAX_JOBS,
) -> pd.DataFrame:
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(
            # Để False khi thử nghiệm để quan sát trang.
            headless=False,
            slow_mo=100,
        )

        context = browser.new_context(
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
            viewport={
                "width": 1366,
                "height": 768,
            },
        )

        listing_page = context.new_page()

        urls = discover_job_urls(
            page=listing_page,
            max_jobs=max_jobs,
            max_pages=MAX_LISTING_PAGES,
        )

        print(f"Tổng URL thu được: {len(urls)}")

        if not urls:
            listing_page.close()
            browser.close()

            raise RuntimeError(
                "Không tìm thấy URL việc làm. "
                "Kiểm tra cửa sổ Chromium và log."
            )

        # Không đóng listing_page. Dùng chính trang này để click từng job.
        dataframe = crawl_detail_pages_from_listing(
            listing_page=listing_page,
            urls=urls,
        )

        listing_page.close()
        browser.close()

    if dataframe.empty:
        print(
            "Không có bản ghi; không ghi đè "
            "file Parquet hiện có."
        )
        return dataframe

    output_path = (
        INTERIM_ROOT
        / "topcv_jobs_raw.parquet"
    )

    dataframe.to_parquet(
        output_path,
        index=False,
    )

    print(f"Đã lưu {len(dataframe)} bản ghi:")
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

        columns = [
            column
            for column in columns
            if column in df.columns
        ]

        print(
            df[columns]
            .head(10)
            .to_string(index=False)
        )
