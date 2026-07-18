from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tomllib
from unittest.mock import patch

import pytest
import yaml

import crawl_service
from core.shared.contracts.market import JobPostingRecord, ExtractedSkill
from core.shared.schemas import StudentProfile
from crawl_service.handoff_validation import run_validation
from crawl_service.cli import cli as crawl_cli
from crawl_service.paths import (
    PROCESSED_DIR,
    PROJECT_ROOT,
    SOURCES_CONFIG_PATH,
    TAXONOMY_PATH,
)


def subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    src = str(PROJECT_ROOT / "crawl-service" / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        [src, str(PROJECT_ROOT), env.get("PYTHONPATH", "")]
    )
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("CAREER_COMPASS_ROOT", None)
    return env


def test_crawl_service_package_imports():
    assert crawl_service.__version__ == "0.1.0"


def test_pyproject_explicitly_discovers_src_layout():
    payload = tomllib.loads(
        (PROJECT_ROOT / "crawl-service/pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    setuptools = payload["tool"]["setuptools"]
    assert setuptools["package-dir"] == {"": "src"}
    assert setuptools["packages"]["find"]["where"] == ["src"]
    assert setuptools["packages"]["find"]["include"] == ["crawl_service*"]


@pytest.mark.parametrize(
    "wrapper",
    [
        "run_pipeline.py",
        "scripts/collect_greenhouse.py",
        "scripts/collect_viecoi.py",
        "scripts/run_data_pipeline.py",
        "scripts/update_job_lifecycle.py",
        "scripts/validate_data_handoff.py",
    ],
)
def test_compatibility_wrappers_bootstrap_src_layout(wrapper: str):
    text = (PROJECT_ROOT / wrapper).read_text(encoding="utf-8")
    assert 'PROJECT_ROOT / "crawl-service" / "src"' in text
    assert "sys.path.insert(0, str(CRAWL_SERVICE_SRC))" in text


def test_module_status_returns_zero():
    result = subprocess.run(
        [sys.executable, "-m", "crawl_service", "status"],
        cwd=PROJECT_ROOT,
        env=subprocess_env(),
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert "crawl-service is ready" in result.stdout
    assert "0.4.0" in result.stdout


def test_unknown_cli_command_returns_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "crawl_service", "unknown"],
        cwd=PROJECT_ROOT,
        env=subprocess_env(),
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr


@pytest.mark.parametrize(
    ("wrapper", "command"),
    [
        ("run_pipeline.py", "pipeline"),
        ("scripts/collect_greenhouse.py", "collect-greenhouse"),
        ("scripts/collect_viecoi.py", "collect-viecoi"),
    ],
)
def test_compatibility_wrapper_dispatches_expected_command(
    wrapper: str,
    command: str,
):
    with patch("crawl_service.cli.main", return_value=0) as dispatch:
        with pytest.raises(SystemExit) as exit_info:
            runpy.run_path(str(PROJECT_ROOT / wrapper), run_name="__main__")
    assert exit_info.value.code == 0
    dispatch.assert_called_once_with(command)


def test_validate_handoff_fixture_only_through_module_cli(capsys):
    assert crawl_cli(["validate-handoff", "--fixtures-only"]) == 0
    output = capsys.readouterr().out
    assert "DATA MODE: FIXTURE" in output
    assert "DATA HANDOFF READINESS: PASS" in output


def test_shared_paths_point_to_canonical_root_files():
    assert TAXONOMY_PATH == PROJECT_ROOT / "backend/shared/taxonomy.json"
    assert SOURCES_CONFIG_PATH == PROJECT_ROOT / "config/sources.yaml"
    assert TAXONOMY_PATH.is_file()
    assert SOURCES_CONFIG_PATH.is_file()


def test_path_resolution_does_not_depend_on_working_directory(tmp_path: Path):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from crawl_service.paths import PROJECT_ROOT; print(PROJECT_ROOT)",
        ],
        cwd=tmp_path,
        env=subprocess_env(),
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == PROJECT_ROOT


def test_no_duplicate_backend_data_implementation():
    assert not (PROJECT_ROOT / "backend/data").exists()
    assert (PROJECT_ROOT / "crawl-service/src/crawl_service/pipeline.py").is_file()


def test_downstream_shared_contract_still_imports():
    assert JobPostingRecord is not None
    assert ExtractedSkill is not None


def test_student_profile_fixture_still_validates():
    payload = json.loads(
        (PROJECT_ROOT / "tests/fixtures/integration/student_profile_sample.json")
        .read_text(encoding="utf-8")
    )
    assert StudentProfile.model_validate(payload).taxonomy_version == "0.4.0"


def test_pipeline_output_contract_paths_remain_root_level():
    from crawl_service import runner

    assert PROCESSED_DIR == PROJECT_ROOT / "data/processed"
    assert runner.PROCESSED_ROOT == PROCESSED_DIR
    assert runner.LIFECYCLE_PATH == PROCESSED_DIR / "job_lifecycle.parquet"


def test_existing_handoff_readiness_still_passes():
    assert run_validation(fixtures_only=True)["mode"] == "FIXTURE"


def test_docker_uses_module_entrypoint_and_no_data_copy():
    dockerfile = (PROJECT_ROOT / "crawl-service/Dockerfile").read_text(
        encoding="utf-8"
    )
    assert 'CMD ["python", "-m", "crawl_service", "status"]' in dockerfile
    assert "COPY data " not in dockerfile


def test_generated_data_is_not_tracked():
    from crawl_service.handoff_validation import validate_generated_file_guard

    validate_generated_file_guard(PROJECT_ROOT)


def test_source_registry_keeps_pilot_scope_and_topcv_disabled():
    payload = yaml.safe_load(SOURCES_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["platform"]: source for source in payload["sources"]}
    assert sources["viecoi"]["max_pages"] == 3
    assert sources["viecoi"]["max_jobs"] == 90
    assert sources["viecoi"]["detail_pages_enabled"] is False
    assert sources["topcv"]["enabled"] is False


def test_old_backend_data_import_namespace_is_not_retained():
    assert not (PROJECT_ROOT / "backend/data").exists()
