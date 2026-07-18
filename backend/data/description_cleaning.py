from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "interim"
    / "greenhouse_jobs_latest.parquet"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "greenhouse_jobs_description_clean.parquet"
)

# Các phần tử thường đại diện cho một khối nội dung có nghĩa.
BLOCK_TAGS = "h1,h2,h3,h4,h5,h6,p,li"


def normalize_whitespace(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def normalize_block_key(text: str) -> str:
    """
    Chuẩn hóa dùng để so sánh hai block.

    Không dùng kết quả này làm nội dung đầu ra.
    """
    normalized = text.casefold()

    # Chuẩn hóa dấu ngoặc kép và gạch nối.
    normalized = (
        normalized
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("–", "-")
        .replace("—", "-")
    )

    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def extract_html_blocks(html: Any) -> list[str]:
    """
    Tách HTML thành các đoạn văn, tiêu đề và bullet riêng biệt.

    Không chia bằng dấu chấm vì cách đó dễ làm hỏng câu,
    URL và cấu trúc danh sách.
    """
    if html is None or pd.isna(html):
        return []

    soup = BeautifulSoup(str(html), "html.parser")

    blocks: list[str] = []
    previous_key: str | None = None

    for element in soup.select(BLOCK_TAGS):
        text = normalize_whitespace(
            element.get_text(" ", strip=True)
        )

        if not text:
            continue

        key = normalize_block_key(text)

        # Bỏ block trùng liên tiếp do HTML lồng nhau hoặc template lỗi.
        if key == previous_key:
            continue

        previous_key = key
        blocks.append(text)

    # Trường hợp nội dung không có các tag dự kiến.
    if not blocks:
        text = normalize_whitespace(
            soup.get_text(" ", strip=True)
        )

        if text:
            blocks.append(text)

    return blocks


def calculate_boilerplate_keys(
    group: pd.DataFrame,
    frequency_threshold: float = 0.80,
) -> set[str]:
    """
    Một block được coi là boilerplate khi xuất hiện trong ít nhất
    80% JD của cùng một doanh nghiệp/source.

    Tính theo số document chứa block, không tính số lần block
    lặp bên trong cùng một document.
    """
    document_count = len(group)

    if document_count < 3:
        return set()

    minimum_documents = math.ceil(
        document_count * frequency_threshold
    )

    document_frequency: Counter[str] = Counter()

    for blocks in group["_description_blocks"]:
        unique_keys = {
            normalize_block_key(block)
            for block in blocks
            if block
        }

        document_frequency.update(unique_keys)

    return {
        key
        for key, count in document_frequency.items()
        if count >= minimum_documents
    }


def split_description(
    blocks: list[str],
    boilerplate_keys: set[str],
) -> tuple[list[str], list[str]]:
    role_specific: list[str] = []
    boilerplate: list[str] = []

    for block in blocks:
        key = normalize_block_key(block)

        if key in boilerplate_keys:
            boilerplate.append(block)
        else:
            role_specific.append(block)

    return role_specific, boilerplate


def process_group(
    group: pd.DataFrame,
    frequency_threshold: float = 0.80,
) -> pd.DataFrame:
    group = group.copy()

    boilerplate_keys = calculate_boilerplate_keys(
        group,
        frequency_threshold=frequency_threshold,
    )

    role_specific_values: list[str | None] = []
    boilerplate_values: list[str | None] = []
    boilerplate_ratios: list[float] = []
    role_specific_counts: list[int] = []
    boilerplate_counts: list[int] = []

    for blocks in group["_description_blocks"]:
        role_specific, boilerplate = split_description(
            blocks,
            boilerplate_keys,
        )

        total_blocks = len(blocks)

        role_specific_values.append(
            "\n".join(role_specific)
            if role_specific
            else None
        )

        boilerplate_values.append(
            "\n".join(boilerplate)
            if boilerplate
            else None
        )

        boilerplate_ratios.append(
            len(boilerplate) / total_blocks
            if total_blocks
            else 0.0
        )

        role_specific_counts.append(
            len(role_specific)
        )
        boilerplate_counts.append(
            len(boilerplate)
        )

    group["description_role_specific"] = (
        role_specific_values
    )
    group["boilerplate_text"] = boilerplate_values
    group["boilerplate_ratio"] = boilerplate_ratios
    group["role_specific_block_count"] = (
        role_specific_counts
    )
    group["boilerplate_block_count"] = (
        boilerplate_counts
    )

    return group


def clean_job_descriptions(
    dataframe: pd.DataFrame,
    group_column: str = "source_id",
    frequency_threshold: float = 0.80,
) -> pd.DataFrame:
    """Separate role-specific text from repeated source/company boilerplate."""
    required_columns = {group_column, "description_raw"}
    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise KeyError(f"Thiếu các cột bắt buộc: {sorted(missing_columns)}")

    result = dataframe.copy()
    result["_description_blocks"] = result["description_raw"].map(
        extract_html_blocks
    )
    result["description_text"] = result["_description_blocks"].map(
        lambda blocks: "\n".join(blocks) if blocks else None
    )

    groups = [
        process_group(group, frequency_threshold=frequency_threshold)
        for _, group in result.groupby(group_column, dropna=False, sort=False)
    ]
    result = pd.concat(groups, ignore_index=True) if groups else result
    result["description_cleaning_version"] = "frequency-block-0.1.0"
    return result.drop(columns=["_description_blocks"])


def main() -> None:
    dataframe = pd.read_parquet(INPUT_PATH)
    dataframe = clean_job_descriptions(
        dataframe,
        group_column="source_id",
        frequency_threshold=0.80,
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_parquet(
        OUTPUT_PATH,
        index=False,
    )

    print(f"Saved {len(dataframe)} records:")
    print(OUTPUT_PATH)

    print("\nBoilerplate statistics:")
    print(
        dataframe[
            [
                "job_title_raw",
                "role_specific_block_count",
                "boilerplate_block_count",
                "boilerplate_ratio",
            ]
        ]
        .sort_values(
            "boilerplate_ratio",
            ascending=False,
        )
        .to_string(index=False)
    )

    print("\nDescription lengths:")
    print(
        dataframe[
            [
                "description_text",
                "description_role_specific",
            ]
        ]
        .apply(lambda column: column.str.len())
        .describe()
    )


if __name__ == "__main__":
    main()
