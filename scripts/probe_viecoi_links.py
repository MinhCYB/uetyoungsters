from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://viecoi.vn"
LISTING_URL = "https://viecoi.vn/tim-viec/all.html"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = PROJECT_ROOT / "data" / "debug" / "viecoi"

JOB_PATH_PATTERN = re.compile(
    r"^/viec-lam/.+-\d+\.html/?$",
    flags=re.IGNORECASE,
)


def normalize_job_url(href: str | None) -> str | None:
    if not href:
        return None

    absolute_url = urljoin(BASE_URL, href.strip())
    parsed = urlsplit(absolute_url)

    hostname = (parsed.hostname or "").lower()

    if hostname not in {
        "viecoi.vn",
        "www.viecoi.vn",
    }:
        return None

    path = parsed.path.rstrip("/")

    if not JOB_PATH_PATTERN.match(path):
        return None

    # Bỏ query tracking và fragment.
    return urlunsplit(
        (
            "https",
            "viecoi.vn",
            path,
            "",
            "",
        )
    )


def find_card_text(anchor) -> str | None:
    """
    Tìm ancestor gần nhất có kích thước giống một job card.
    Chỉ dùng để debug cấu trúc HTML.
    """
    anchor_text = anchor.get_text(
        " ",
        strip=True,
    )

    for parent in anchor.parents:
        if parent.name in {
            "body",
            "html",
        }:
            break

        text = parent.get_text(
            " ",
            strip=True,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        if (
            anchor_text
            and anchor_text in text
            and 80 <= len(text) <= 1500
        ):
            return text

    return None


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "UETCareerResearch/0.1 "
                "(academic project)"
            ),
            "Accept-Language": (
                "vi-VN,vi;q=0.9,en;q=0.7"
            ),
        }
    )

    response = session.get(
        LISTING_URL,
        timeout=30,
    )

    response.raise_for_status()

    DEBUG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    html_path = DEBUG_DIR / "listing_page_1.html"

    html_path.write_text(
        response.text,
        encoding="utf-8",
    )

    soup = BeautifulSoup(
        response.text,
        "lxml",
    )

    jobs: dict[str, dict[str, str | None]] = {}

    for anchor in soup.select("a[href]"):
        url = normalize_job_url(
            anchor.get("href")
        )

        if not url or url in jobs:
            continue

        title = anchor.get_text(
            " ",
            strip=True,
        )

        title = re.sub(
            r"\s+",
            " ",
            title,
        ).strip()

        if not title:
            continue

        jobs[url] = {
            "title": title,
            "card_text": find_card_text(anchor),
        }

    pagination_links: list[str] = []

    for anchor in soup.select("a[href]"):
        href = anchor.get("href") or ""

        if any(
            keyword in href.casefold()
            for keyword in [
                "page=",
                "trang-",
                "/page/",
            ]
        ):
            absolute = urljoin(
                LISTING_URL,
                href,
            )

            if absolute not in pagination_links:
                pagination_links.append(absolute)

    print(f"HTTP: {response.status_code}")
    print(f"HTML length: {len(response.text):,}")
    print(f"Unique job URLs: {len(jobs)}")
    print(f"Debug HTML: {html_path}")

    print("\nFIRST 10 JOBS")

    for index, (url, item) in enumerate(
        list(jobs.items())[:10],
        start=1,
    ):
        print(f"\n[{index}] {item['title']}")
        print(url)

        card_text = item["card_text"]

        if card_text:
            print(
                "CARD:",
                card_text[:500],
            )
        else:
            print("CARD: <not found>")

    print("\nPAGINATION CANDIDATES")

    for url in pagination_links[:20]:
        print(url)


if __name__ == "__main__":
    main()
