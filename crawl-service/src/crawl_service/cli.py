"""Command-line interface for the Career Compass crawl service."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .paths import SOURCES_CONFIG_PATH, TAXONOMY_PATH


COMMANDS = (
    "status",
    "collect-greenhouse",
    "collect-viecoi",
    "collect-all",
    "pipeline",
    "publish-db",
    "validate-handoff",
)


def main(action: str, arguments: Sequence[str] | None = None) -> int:
    """Dispatch one service action without embedding Data Layer logic."""
    args = list(arguments or [])

    if action == "status":
        from .shared_contracts.taxonomy import load_taxonomy

        taxonomy = load_taxonomy(TAXONOMY_PATH)
        if not SOURCES_CONFIG_PATH.is_file():
            raise FileNotFoundError(
                f"Source registry not found: {SOURCES_CONFIG_PATH}"
            )
        print("Career Compass crawl-service is ready.")
        print(f"Taxonomy version: {taxonomy['taxonomy_version']}")
        print(f"Source config: {SOURCES_CONFIG_PATH}")
        return 0

    if action == "collect-greenhouse":
        from .collectors.greenhouse import run_collection

        run_collection()
        return 0

    if action == "collect-viecoi":
        from .collectors.viecoi import run_collection

        run_collection()
        return 0

    if action == "collect-all":
        from .collectors.greenhouse import run_collection as greenhouse
        from .collectors.viecoi import run_collection as viecoi

        greenhouse()
        viecoi()
        return 0

    if action == "pipeline":
        from .runner import run_pipeline

        run_pipeline()
        return 0

    if action == "publish-db":
        from .database import publish_processed_outputs

        manifest = publish_processed_outputs()
        print(manifest.to_string(index=False))
        return 0

    if action == "validate-handoff":
        from .handoff_validation import cli as validate_cli

        return validate_cli(args)

    raise ValueError(
        f"Unknown crawl-service command: {json.dumps(action)}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m crawl_service",
        description="Career Compass Data Layer service",
    )
    parser.add_argument("command", choices=COMMANDS)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fixtures-only", action="store_true")
    mode.add_argument("--production-only", action="store_true")
    return parser


def cli(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    namespace = parser.parse_args(argv)
    validation_args: list[str] = []
    if namespace.fixtures_only:
        validation_args.append("--fixtures-only")
    if namespace.production_only:
        validation_args.append("--production-only")
    if validation_args and namespace.command != "validate-handoff":
        parser.error(
            "--fixtures-only/--production-only require validate-handoff"
        )
    return main(namespace.command, validation_args)
