"""Loader for the single canonical Career Compass taxonomy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CANONICAL_TAXONOMY_PATH = (
    PROJECT_ROOT
    / "backend"
    / "shared"
    / "taxonomy.json"
)


def load_taxonomy(
    path: str | Path = CANONICAL_TAXONOMY_PATH,
) -> dict[str, Any]:
    """Load the canonical shared taxonomy."""

    taxonomy_path = Path(path)

    if not taxonomy_path.exists():
        raise FileNotFoundError(
            f"Canonical taxonomy not found: {taxonomy_path}"
        )

    with taxonomy_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError(
            "Canonical taxonomy root must be a JSON object."
        )

    return payload


def load_canonical_taxonomy(
    path: str | Path = CANONICAL_TAXONOMY_PATH,
) -> dict[str, Any]:
    """
    Compatibility alias with an explicit name.

    New consumers may use load_taxonomy().
    """

    return load_taxonomy(path)


__all__ = [
    "CANONICAL_TAXONOMY_PATH",
    "load_taxonomy",
    "load_canonical_taxonomy",
]
