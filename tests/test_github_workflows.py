from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def test_all_github_workflows_are_valid_yaml() -> None:
    workflow_paths = sorted(WORKFLOWS_DIR.glob("*.yml"))
    assert workflow_paths, "Expected GitHub workflow files to exist"

    for workflow_path in workflow_paths:
        parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        assert isinstance(
            parsed, dict
        ), f"{workflow_path.name} must parse into a mapping"


def test_ci_build_job_uses_env_for_build_flags() -> None:
    workflow_path = WORKFLOWS_DIR / "ci.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    jobs = parsed["jobs"]
    build_job = jobs["build"]

    assert "env" in build_job, "Build job should declare build flags via env"
    assert (
        "environment" not in build_job
    ), "Build job should not misuse environment for env vars"


def test_ci_service_containers_do_not_depend_on_repository_secret_passwords() -> None:
    workflow_path = WORKFLOWS_DIR / "ci.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    test_job = parsed["jobs"]["test"]

    for service_name, service_config in test_job["services"].items():
        password = service_config["env"]["POSTGRES_PASSWORD"]
        assert (
            "secrets.DB_PASSWORD" not in password
        ), f"{service_name} should not require repository secrets for ephemeral CI databases"


def test_code_quality_service_container_uses_secretless_ci_password() -> None:
    workflow_path = WORKFLOWS_DIR / "code-quality.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    coverage_job = parsed["jobs"]["coverage"]
    password = coverage_job["services"]["postgres-test"]["env"]["POSTGRES_PASSWORD"]

    assert "secrets.DB_PASSWORD" not in password


def test_code_quality_type_check_uses_explicit_package_bases_for_src_layout() -> None:
    workflow_path = WORKFLOWS_DIR / "code-quality.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    type_check_job = parsed["jobs"]["type-check"]
    run_step = next(
        step
        for step in type_check_job["steps"]
        if step.get("name") == "Run mypy type checking"
    )
    command = run_step["run"]

    assert "--explicit-package-bases" in command
    assert "MYPYPATH=." in command
    assert "--follow-imports=silent" in command
    assert "--ignore-missing-imports" in command


def test_ci_isort_check_uses_black_profile() -> None:
    workflow_path = WORKFLOWS_DIR / "ci.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    lint_job = parsed["jobs"]["lint"]
    run_step = next(
        step
        for step in lint_job["steps"]
        if step.get("name") == "Check imports with isort"
    )

    assert "--profile black" in run_step["run"]
