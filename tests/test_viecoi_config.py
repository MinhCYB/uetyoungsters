from pathlib import Path

import pytest

from scripts.collect_viecoi import (
    load_viecoi_source,
)


def test_load_enabled_viecoi_source(
    tmp_path: Path,
):
    config_path = tmp_path / "sources.yaml"

    config_path.write_text(
        """
sources:
  - source_id: viecoi_listing
    platform: viecoi
    enabled: true
    listing_url: https://viecoi.vn/tim-viec/all.html
    max_pages: 1
    max_jobs: 30
""".strip(),
        encoding="utf-8",
    )

    source = load_viecoi_source(
        config_path
    )

    assert source["source_id"] == (
        "viecoi_listing"
    )
    assert source["max_pages"] == 1
    assert source["max_jobs"] == 30


def test_disabled_viecoi_is_not_loaded(
    tmp_path: Path,
):
    config_path = tmp_path / "sources.yaml"

    config_path.write_text(
        """
sources:
  - source_id: viecoi_listing
    platform: viecoi
    enabled: false
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError):
        load_viecoi_source(config_path)
