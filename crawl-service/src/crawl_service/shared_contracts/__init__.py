"""Shared contracts internalised from core/shared/ for self-containment.

This package provides taxonomy loading, market data contracts, and the
student profile schema — everything that crawl-service previously imported
from core.shared via PYTHONPATH hacks.
"""

from .market import (
    ExtractionMethod,
    ExtractedSkill,
    JobPostingRecord,
    MarketJobRecord,
    MarketSkillRecord,
    RequirementLevel,
    WorkMode,
)
from .schemas import StudentProfile
from .taxonomy import (
    CANONICAL_TAXONOMY_PATH,
    load_canonical_taxonomy,
    load_taxonomy,
)

__all__ = [
    "CANONICAL_TAXONOMY_PATH",
    "ExtractionMethod",
    "ExtractedSkill",
    "JobPostingRecord",
    "MarketJobRecord",
    "MarketSkillRecord",
    "RequirementLevel",
    "StudentProfile",
    "WorkMode",
    "load_canonical_taxonomy",
    "load_taxonomy",
]
