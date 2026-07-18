"""Download the versioned public O*NET occupation and task datasets."""
from __future__ import annotations

import json
from pathlib import Path
import requests

from ..paths import RAW_DIR

ONET_VERSION = "30.3"
BASE_URL = f"https://www.onetcenter.org/dl_files/database/db_{ONET_VERSION.replace('.', '_')}_json"
FILES = (
    "occupation_data.json",
    "task_statements.json",
    "career_interest_types.json",
    "essential_skills.json",
    "transferable_skills.json",
    "software_skills.json",
)


def run_collection(force: bool = False) -> list[Path]:
    destination = RAW_DIR / "onet" / ONET_VERSION
    destination.mkdir(parents=True, exist_ok=True)
    outputs = []
    for filename in FILES:
        target = destination / filename
        if force or not target.is_file():
            response = requests.get(f"{BASE_URL}/{filename}", timeout=120)
            response.raise_for_status()
            target.write_text(json.dumps(response.json(), ensure_ascii=False), encoding="utf-8")
        outputs.append(target)
    print(f"O*NET {ONET_VERSION}: {', '.join(path.name for path in outputs)}")
    return outputs
