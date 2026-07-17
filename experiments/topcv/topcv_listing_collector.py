from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


BASE_URL = "https://www.topcv.vn"
DEFAULT_LISTING_URL = (
    "https://www.topcv.vn/tim-viec-lam-moi-nhat-tai-ha-noi-l1"
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = PROJECT_ROOT / "data" / "raw" / "topcv_listing"
INTERIM_ROOT = PROJECT_ROOT / "data" / "interim"
QUALITY_ROOT = PROJECT_ROOT / "data" / "quality"

JOB_URL_PATTERN = re.compile(
    r"^/viec-lam/[^/?]+/(\d+)\.html/?$",
    flags=re.IGNORECASE,
)

SALARY_PATTERN = re.compile(
    r"(?P<salary>"
    r"(?:"
    r"\d+(?:[.,]\d+)?\s*(?:-|–|—|đến)\s*\d+(?:[.,]\d+)?"
    r"|(?:từ|trên|dưới|upto|up\s*to)\s*\d+(?:[.,]\d+)?"
    r"|\d+(?:[.,]\d+)?\+?"
    r")\s*(?:triệu|tr|million)\b"
    r"|(?:thỏa|thoả)\s*thuận"
    r")",
    flags=re.IGNORECASE,
)

EXPERIENCE_PATTERN = re.compile(
    r"(?P<experience>"
    r"chưa\s+có\s+kinh\s+nghiệm"
    r"|không\s+yêu\s+cầu\s+kinh\s+nghiệm"
    r"|dưới\s+\d+(?:[.,]\d+)?\s+năm"
    r"|trên\s+\d+(?:[.,]\d+)?\s+năm"
    r"|\d+(?:[.,]\d+)?\s+năm"
    r")",
    flags=re.IGNORECASE,
)

POSTED_PATTERN = re.compile(
    r"(?P<posted>"
    r"đăng\s+(?:"
    r"hôm\s+nay"
    r"|\d+\s+(?:phút|giờ|ngày|tuần|tháng)\s+trước"
    r")"
    r")",
    flags=re.IGNORECASE,
)

NOISE_LINES = {
    "tin mới",
    "xem nhanh",
    "ứng tuyển",
    "hoàn tác",
    "pro",
    "hot",
    "gấp",
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def deduplicate_lines(text: str) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)

    return lines


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


def normalize_job_url(url: str) -> str | None:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()

    if hostname not in {"topcv.vn", "www.topcv.vn"}:
        return None

    path = parsed.path.rstrip("/")
    match = JOB_URL_PATTERN.match(path)
    if not match:
        return None

    return urlunsplit(("https", "www.topcv.vn", path, "", ""))


def extract_job_id(url: str) -> str | None:
    parsed = urlsplit(url)
    match = JOB_URL_PATTERN.match(parsed.path.rstrip("/"))
    return match.group(1) if match else None


def dismiss_cookie_popup(page: Page) -> None:
    for label in ["Chấp nhận tất cả", "Xác nhận lựa chọn"]:
        locator = page.get_by_text(label, exact=True).first
        try:
            if locator.is_visible(timeout=1_000):
                locator.click(timeout=3_000)
                page.wait_for_timeout(500)
                return
        except Exception:
            continue


def scroll_listing(page: Page, rounds: int = 7) -> None:
    previous_height = 0

    for _ in range(rounds):
        current_height = int(page.evaluate("document.body.scrollHeight"))
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(900)

        if current_height == previous_height:
            break
        previous_height = current_height


def detect_block_page(page: Page) -> bool:
    try:
        title = page.title().casefold()
        body = page.locator("body").inner_text(timeout=5_000).casefold()
    except Exception:
        return False

    indicators = [
        "captcha",
        "access denied",
        "verify you are human",
        "xác minh bạn là con người",
        "unusual traffic",
        "security check",
        "checking your browser",
    ]

    content = f"{title}\n{body}"
    return any(indicator in content for indicator in indicators)


def extract_card_candidates(page: Page) -> list[dict[str, Any]]:
    """Chỉ lấy dữ liệu có sẵn trên listing, không mở trang chi tiết."""
    return page.evaluate(
        r"""
        () => {
            const clean = value =>
                (value || "").replace(/\s+/g, " ").trim();

            const jobPath =
                /^\/viec-lam\/[^/?]+\/(\d+)\.html\/?$/i;

            const salarySignal =
                /(?:\d+(?:[.,]\d+)?\s*(?:-|–|—|đến)\s*\d+(?:[.,]\d+)?|(?:từ|trên|dưới|upto|up\s*to)\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\+?)\s*(?:triệu|tr|million)\b|(?:thỏa|thoả)\s*thuận/i;

            const experienceSignal =
                /chưa\s+có\s+kinh\s+nghiệm|không\s+yêu\s+cầu\s+kinh\s+nghiệm|(?:dưới|trên)?\s*\d+(?:[.,]\d+)?\s+năm/i;

            const postedSignal =
                /đăng\s+(?:hôm\s+nay|\d+\s+(?:phút|giờ|ngày|tuần|tháng)\s+trước)/i;

            const applySignal = /\bứng tuyển\b/i;
            const seen = new Set();
            const output = [];

            for (const anchor of document.querySelectorAll("a[href]")) {
                let absolute;
                try {
                    absolute = new URL(
                        anchor.getAttribute("href"),
                        window.location.href
                    );
                } catch {
                    continue;
                }

                const match = absolute.pathname.match(jobPath);
                if (!match) continue;

                const jobId = match[1];
                if (seen.has(jobId)) continue;

                const title = clean(anchor.innerText || anchor.textContent);
                if (!title || title.length < 3) continue;

                let node = anchor;
                let card = null;

                for (let depth = 0; depth < 10; depth += 1) {
                    node = node.parentElement;
                    if (!node) break;

                    const text = clean(node.innerText);
                    if (
                        !text ||
                        text.length < 35 ||
                        text.length > 1800 ||
                        !text.includes(title)
                    ) {
                        continue;
                    }

                    const signalCount = [
                        salarySignal.test(text),
                        experienceSignal.test(text),
                        postedSignal.test(text),
                        applySignal.test(text),
                    ].filter(Boolean).length;

                    if (signalCount >= 2) {
                        card = node;
                        break;
                    }
                }

                if (!card) continue;

                const cardText = (card.innerText || "").trim();
                const links = Array.from(card.querySelectorAll("a[href]")).map(item => {
                    let href = "";
                    try {
                        href = new URL(
                            item.getAttribute("href"),
                            window.location.href
                        ).href;
                    } catch {
                        href = "";
                    }

                    return {
                        href,
                        text: clean(item.innerText || item.textContent),
                    };
                });

                const isJobHref = href => {
                    try {
                        return jobPath.test(new URL(href).pathname);
                    } catch {
                        return false;
                    }
                };

                const companyLink =
                    links.find(item =>
                        item.text &&
                        !isJobHref(item.href) &&
                        /\/cong-ty\/|\/company\/|\/brand\//i.test(item.href)
                    ) ||
                    links.find(item =>
                        item.text &&
                        item.text !== title &&
                        !/^(ứng tuyển|xem nhanh|lưu|hoàn tác)$/i.test(item.text) &&
                        !isJobHref(item.href)
                    );

                seen.add(jobId);
                output.push({
                    source_job_id: jobId,
                    job_title_raw: title,
                    company_link_text: companyLink?.text || null,
                    source_url: absolute.href,
                    card_text_raw: cardText,
                });
            }

            return output;
        }
        """
    )


def first_match(
    pattern: re.Pattern[str],
    text: str,
    group_name: str,
) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    return clean_text(match.group(group_name))


def infer_company(
    lines: list[str],
    title: str,
    company_link_text: str | None,
) -> str | None:
    company = clean_text(company_link_text)
    if company and company.casefold() != title.casefold():
        return company

    title_key = title.casefold()

    for line in lines:
        key = line.casefold()
        if key == title_key or key in NOISE_LINES:
            continue
        if key.startswith("bạn sẽ không nhìn thấy"):
            continue
        if SALARY_PATTERN.search(line):
            continue
        if EXPERIENCE_PATTERN.fullmatch(line):
            continue
        if POSTED_PATTERN.search(line):
            continue
        if len(line) < 3 or len(line) > 220:
            continue
        return line

    return None


def infer_location(
    lines: list[str],
    card_text: str,
    location_hint: str | None,
    salary_raw: str | None,
    experience_raw: str | None,
) -> str | None:
    if not location_hint:
        return None

    hint_key = location_hint.casefold()

    for line in lines:
        if hint_key not in line.casefold():
            continue

        candidate = line
        if salary_raw:
            candidate = re.sub(
                re.escape(salary_raw),
                " ",
                candidate,
                flags=re.IGNORECASE,
            )
        if experience_raw:
            candidate = re.sub(
                re.escape(experience_raw),
                " ",
                candidate,
                flags=re.IGNORECASE,
            )

        candidate = clean_text(candidate)
        if candidate and len(candidate) <= 160:
            return candidate

    if hint_key in card_text.casefold():
        return location_hint

    return None


def parse_candidate(
    candidate: dict[str, Any],
    *,
    listing_url: str,
    page_number: int,
    fetched_at: str,
    snapshot_version: str,
    location_hint: str | None,
) -> dict[str, Any] | None:
    normalized_url = normalize_job_url(str(candidate.get("source_url", "")))
    if not normalized_url:
        return None

    job_id = extract_job_id(normalized_url)
    title = clean_text(candidate.get("job_title_raw"))
    card_text = str(candidate.get("card_text_raw") or "")

    if not job_id or not title:
        return None

    lines = deduplicate_lines(card_text)
    salary_raw = first_match(SALARY_PATTERN, card_text, "salary")
    experience_raw = first_match(EXPERIENCE_PATTERN, card_text, "experience")
    posted_time_raw = first_match(POSTED_PATTERN, card_text, "posted")

    company_name_raw = infer_company(
        lines,
        title,
        clean_text(candidate.get("company_link_text")),
    )

    location_raw = infer_location(
        lines,
        card_text,
        location_hint,
        salary_raw,
        experience_raw,
    )

    card_hash = hashlib.sha256(card_text.encode("utf-8")).hexdigest()

    return {
        "source": "topcv",
        "source_job_id": job_id,
        "source_url": normalized_url,
        "job_title_raw": title,
        "company_name_raw": company_name_raw,
        "salary_raw": salary_raw,
        "location_raw": location_raw,
        "experience_raw": experience_raw,
        "posted_time_raw": posted_time_raw,
        "card_text_raw": card_text,
        "listing_url": listing_url,
        "listing_page": page_number,
        "fetched_at": fetched_at,
        "snapshot_version": snapshot_version,
        "content_hash_sha256": card_hash,
        "collector_version": "0.4.0",
        "parser_version": "listing-card-0.1.0",
        "collection_scope": "public_listing_fields_only",
    }


def save_raw_listing(page: Page, run_dir: Path, page_number: int) -> None:
    html_path = run_dir / f"page_{page_number}.html"
    screenshot_path = run_dir / f"page_{page_number}.png"

    html_path.write_text(page.content(), encoding="utf-8")

    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception as exc:
        print(f"[WARN] Không chụp được screenshot: {exc}")


def build_quality_report(
    dataframe: pd.DataFrame,
    snapshot_version: str,
) -> pd.DataFrame:
    columns = [
        "job_title_raw",
        "company_name_raw",
        "salary_raw",
        "location_raw",
        "experience_raw",
        "posted_time_raw",
    ]

    row: dict[str, Any] = {
        "snapshot_version": snapshot_version,
        "record_count": len(dataframe),
        "duplicate_job_id_count": int(
            dataframe["source_job_id"].duplicated().sum()
        ),
    }

    for column in columns:
        row[f"missing_{column}_rate"] = float(
            dataframe[column].isna().mean()
        )

    return pd.DataFrame([row])


def crawl_topcv_listing(
    *,
    listing_url: str,
    max_pages: int,
    max_jobs: int,
    location_hint: str | None,
    headless: bool,
) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    run_stamp = now.strftime("%Y%m%dT%H%M%SZ")
    snapshot_version = f"{now.date().isoformat()}-topcv-{run_stamp}"

    run_dir = RAW_ROOT / run_stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    INTERIM_ROOT.mkdir(parents=True, exist_ok=True)
    QUALITY_ROOT.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    seen_job_ids: set[str] = set()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
            viewport={"width": 1366, "height": 900},
        )

        # Giảm tải mạng, không chặn script/XHR/CSS cần cho listing render.
        context.route(
            "**/*",
            lambda route: (
                route.abort()
                if route.request.resource_type in {"image", "media", "font"}
                else route.continue_()
            ),
        )

        page = context.new_page()

        for page_number in range(1, max_pages + 1):
            current_url = build_page_url(listing_url, page_number)
            print(f"[LIST {page_number}] {current_url}")

            try:
                response = page.goto(
                    current_url,
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
            except PlaywrightTimeoutError:
                print("[STOP] Trang listing tải quá thời gian.")
                break

            status = response.status if response else None
            print(f"  HTTP status: {status}")
            print(f"  Final URL: {page.url}")
            print(f"  Title: {page.title()}")

            if status in {403, 429}:
                print(f"[STOP] Listing trả HTTP {status}.")
                break
            if status != 200:
                print(f"[STOP] Listing trả HTTP {status}.")
                break

            try:
                page.locator("a[href]").first.wait_for(
                    state="attached",
                    timeout=30_000,
                )
            except PlaywrightTimeoutError:
                print("[STOP] DOM không có liên kết.")
                break

            dismiss_cookie_popup(page)
            scroll_listing(page)

            if detect_block_page(page):
                print("[STOP] Phát hiện CAPTCHA/challenge.")
                break

            save_raw_listing(page, run_dir, page_number)
            candidates = extract_card_candidates(page)
            print(f"  Tìm thấy {len(candidates)} card job.")

            new_count = 0
            fetched_at = datetime.now(timezone.utc).isoformat()

            for candidate in candidates:
                record = parse_candidate(
                    candidate,
                    listing_url=current_url,
                    page_number=page_number,
                    fetched_at=fetched_at,
                    snapshot_version=snapshot_version,
                    location_hint=location_hint,
                )

                if not record:
                    continue

                job_id = record["source_job_id"]
                if job_id in seen_job_ids:
                    continue

                seen_job_ids.add(job_id)
                records.append(record)
                new_count += 1

                if len(records) >= max_jobs:
                    break

            print(f"  Job mới: {new_count}")

            if len(records) >= max_jobs:
                break
            if new_count == 0:
                print("[STOP] Không có job mới ở trang này.")
                break

            # Một request listing mỗi khoảng thời gian, không mở detail.
            page.wait_for_timeout(8_000)

        context.close()
        browser.close()

    dataframe = pd.DataFrame(records)

    if dataframe.empty:
        print("Không có bản ghi; không ghi đè file dữ liệu hiện có.")
        return dataframe

    dataframe = dataframe.drop_duplicates(
        subset=["source", "source_job_id"],
        keep="first",
    ).reset_index(drop=True)

    parquet_path = INTERIM_ROOT / f"topcv_listing_jobs_{run_stamp}.parquet"
    csv_path = INTERIM_ROOT / f"topcv_listing_jobs_{run_stamp}.csv"
    latest_path = INTERIM_ROOT / "topcv_listing_jobs_latest.parquet"

    dataframe.to_parquet(parquet_path, index=False)
    dataframe.to_csv(csv_path, index=False, encoding="utf-8-sig")
    dataframe.to_parquet(latest_path, index=False)

    quality = build_quality_report(dataframe, snapshot_version)
    quality_path = QUALITY_ROOT / f"topcv_listing_quality_{run_stamp}.csv"
    quality.to_csv(quality_path, index=False, encoding="utf-8-sig")

    metadata_path = run_dir / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "source": "topcv",
                "listing_url": listing_url,
                "snapshot_version": snapshot_version,
                "record_count": len(dataframe),
                "max_pages": max_pages,
                "max_jobs": max_jobs,
                "location_hint": location_hint,
                "collection_scope": "public_listing_fields_only",
                "detail_pages_opened": False,
                "created_at": now.isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nĐã lưu {len(dataframe)} bản ghi:")
    print(f"  Parquet: {parquet_path}")
    print(f"  CSV:     {csv_path}")
    print(f"  Latest:  {latest_path}")
    print(f"  QA:      {quality_path}")
    print(f"  Raw:     {run_dir}")

    print("\nTỷ lệ thiếu dữ liệu:")
    for column in [
        "job_title_raw",
        "company_name_raw",
        "salary_raw",
        "location_raw",
        "experience_raw",
        "posted_time_raw",
    ]:
        print(f"  {column}: {dataframe[column].isna().mean():.1%}")

    return dataframe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Thu thập trường công khai trên listing TopCV; "
            "không mở trang chi tiết."
        )
    )

    parser.add_argument("--url", default=DEFAULT_LISTING_URL)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--max-jobs", type=int, default=50)
    parser.add_argument("--location-hint", default="Hà Nội")
    parser.add_argument("--headless", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    df = crawl_topcv_listing(
        listing_url=args.url,
        max_pages=max(1, args.max_pages),
        max_jobs=max(1, args.max_jobs),
        location_hint=(
            clean_text(args.location_hint)
            if args.location_hint
            else None
        ),
        headless=args.headless,
    )

    if not df.empty:
        preview_columns = [
            "source_job_id",
            "job_title_raw",
            "company_name_raw",
            "salary_raw",
            "location_raw",
            "experience_raw",
            "posted_time_raw",
        ]

        print("\n" + df[preview_columns].head(10).to_string(index=False))
