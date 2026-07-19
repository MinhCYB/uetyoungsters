"""Translate evidence-backed career profiles through ai-worker-service."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any

import pandas as pd
import requests

from .paths import INTERIM_DIR, PROCESSED_DIR

CACHE_PATH = INTERIM_DIR / "career_profile_vi.json"
PARTIAL_CACHE_PATH = INTERIM_DIR / "career_profile_vi.partial.json"


def _source_payload(row: dict[str, Any]) -> dict[str, Any]:
    tasks = row.get("typical_tasks")
    if tasks is None:
        tasks = []
    elif hasattr(tasks, "tolist"):
        tasks = tasks.tolist()
    return {
        "career_id": row["career_id"],
        "title": row["title"],
        "overview": row.get("overview") or "",
        "tasks": [{"id": str(index), "text": item.get("text", str(item))} for index, item in enumerate(tasks[:10])],
    }


def _source_hash(careers: list[dict[str, Any]]) -> str:
    encoded = json.dumps(careers, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _career_hash(career: dict[str, Any]) -> str:
    return _source_hash([career])


def enrich_career_profiles_vi(batch_size: int = 1) -> Path:
    profiles_path = PROCESSED_DIR / "career_profiles.parquet"
    if not profiles_path.is_file():
        raise FileNotFoundError("Run the crawl pipeline before Vietnamese enrichment")
    careers = [_source_payload(row) for row in pd.read_parquet(profiles_path).to_dict(orient="records")]
    digest = _source_hash(careers)
    source_hashes = {item["career_id"]: _career_hash(item) for item in careers}
    if CACHE_PATH.is_file():
        cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if cached.get("source_hash") == digest:
            print(f"Vietnamese career enrichment is current: {CACHE_PATH}")
            return CACHE_PATH

    worker_url = os.getenv("AI_WORKER_URL", "").rstrip("/")
    if not worker_url:
        raise RuntimeError("AI_WORKER_URL is required; API keys remain owned by ai-worker-service")
    partial = {}
    if PARTIAL_CACHE_PATH.is_file():
        candidate = json.loads(PARTIAL_CACHE_PATH.read_text(encoding="utf-8"))
        if candidate.get("source_hash") == digest:
            partial = candidate
    reusable = {item["career_id"]: item for item in partial.get("careers", [])}
    if CACHE_PATH.is_file():
        completed_cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        cached_hashes = completed_cache.get("source_hashes", {})
        for item in completed_cache.get("careers", []):
            career_id = item["career_id"]
            # Legacy caches have no per-career hashes. Reuse them for this
            # migration; all subsequent runs validate each career strictly.
            if not cached_hashes or cached_hashes.get(career_id) == source_hashes.get(career_id):
                reusable.setdefault(career_id, item)
    translated = [reusable[item["career_id"]] for item in careers if item["career_id"] in reusable]
    completed_ids = {item["career_id"] for item in translated}
    model = None
    for start in range(0, len(careers), batch_size):
        batch = [item for item in careers[start:start + batch_size] if item["career_id"] not in completed_ids]
        if not batch:
            continue
        request_payload = {
                "system_prompt": (
                    "Bạn là biên tập viên hướng nghiệp. Dịch overview và từng task sang tiếng Việt tự nhiên, "
                    "ngắn gọn, dễ hiểu với học sinh/sinh viên. Giữ nguyên ý nghĩa chuyên môn, tên công nghệ và ID; "
                    "không thêm dữ kiện. Trả JSON object có key careers; mỗi phần tử có career_id, overview_vi và "
                    "tasks, trong đó mỗi task chỉ có id và text_vi."
                ),
                "messages": [{"role": "user", "content": json.dumps({"careers": batch}, ensure_ascii=False)}],
                "response_format": "json",
                "max_tokens": 8192,
                "model": os.getenv("TRANSLATION_MODEL") or None,
            }
        response = None
        for attempt in range(4):
            try:
                response = requests.post(f"{worker_url}/infer", json=request_payload, timeout=240)
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
            except requests.RequestException:
                if attempt == 3:
                    raise
            if attempt < 3:
                time.sleep(2 ** attempt * 3)
        assert response is not None
        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise RuntimeError(
                f"Translation stopped after {len(translated)}/{len(careers)} careers; "
                f"ai-worker-service returned HTTP {response.status_code}: {detail}. "
                "Progress is checkpointed; rerun the same command to continue."
            )
        envelope = response.json()
        content = envelope.get("content")
        if not envelope.get("parsed") or not isinstance(content, dict) or not isinstance(content.get("careers"), list):
            raise RuntimeError("ai-worker-service returned invalid translation JSON")
        expected = {item["career_id"] for item in batch}
        received = {item.get("career_id") for item in content["careers"]}
        if expected != received:
            raise RuntimeError(f"Translation batch IDs do not match: expected={expected}, received={received}")
        translated.extend(content["careers"])
        completed_ids.update(expected)
        model = envelope.get("model")
        PARTIAL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PARTIAL_CACHE_PATH.write_text(json.dumps({
            "source_hash": digest, "source_hashes": source_hashes,
            "model": model, "careers": translated,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps({
        "source_hash": digest, "source_hashes": source_hashes, "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(), "careers": translated,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if PARTIAL_CACHE_PATH.is_file():
        PARTIAL_CACHE_PATH.unlink()
    print(f"Translated {len(translated)} career profiles: {CACHE_PATH}")
    return CACHE_PATH
