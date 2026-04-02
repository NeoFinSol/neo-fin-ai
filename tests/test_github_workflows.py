from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"
COMPOSE_CI = Path(__file__).resolve().parents[1] / "docker-compose.ci.yml"
REQUIREMENTS_DEV = Path(__file__).resolve().parents[1] / "requirements-dev.txt"
REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_ci_compose_postgres_services_use_ci_password_env() -> None:
    parsed = yaml.safe_load(COMPOSE_CI.read_text(encoding="utf-8"))
    services = parsed["services"]

    assert services["db"]["environment"]["POSTGRES_PASSWORD"] == "${CI_DB_PASSWORD}"
    assert (
        services["db_test"]["environment"]["POSTGRES_PASSWORD"] == "${CI_DB_PASSWORD}"
    )


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


def test_ci_runner_job_exposes_postgres_service_ports_and_uses_localhost_urls() -> None:
    workflow_path = WORKFLOWS_DIR / "ci.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    test_job = parsed["jobs"]["test"]

    assert test_job["services"]["postgres-main"]["ports"] == [5432]
    assert test_job["services"]["postgres-test"]["ports"] == [5432]

    wait_step = next(
        step
        for step in test_job["steps"]
        if step.get("name") == "Wait for PostgreSQL services"
    )
    migration_step = next(
        step
        for step in test_job["steps"]
        if step.get("name") == "Run database migrations"
    )
    unit_step = next(
        step for step in test_job["steps"] if step.get("name") == "Run unit tests"
    )

    assert (
        "job.services.postgres-main.ports[5432]"
        in wait_step["env"]["POSTGRES_MAIN_PORT"]
    )
    assert (
        "job.services.postgres-test.ports[5432]"
        in wait_step["env"]["POSTGRES_TEST_PORT"]
    )
    assert (
        "127.0.0.1:${{ job.services.postgres-main.ports[5432] }}"
        in migration_step["env"]["DATABASE_URL"]
    )
    assert (
        "127.0.0.1:${{ job.services.postgres-test.ports[5432] }}"
        in migration_step["env"]["TEST_DATABASE_URL"]
    )
    assert (
        "127.0.0.1:${{ job.services.postgres-main.ports[5432] }}"
        in unit_step["env"]["DATABASE_URL"]
    )
    assert (
        "127.0.0.1:${{ job.services.postgres-test.ports[5432] }}"
        in unit_step["env"]["TEST_DATABASE_URL"]
    )


def test_ci_pipeline_generates_coverage_artifact_without_duplicating_fail_under_gate() -> (
    None
):
    workflow_path = WORKFLOWS_DIR / "ci.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    test_job = parsed["jobs"]["test"]
    coverage_step = next(
        step
        for step in test_job["steps"]
        if step.get("name") == "Generate coverage artifact"
    )

    command = coverage_step["run"]
    assert "--cov=src" in command
    assert "--cov-fail-under" not in command


def test_ci_build_job_uses_docker_compose_v2_commands() -> None:
    workflow_path = WORKFLOWS_DIR / "ci.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    build_job = parsed["jobs"]["build"]
    commands = "\n".join(
        step.get("run", "") for step in build_job["steps"] if isinstance(step, dict)
    )

    assert "docker-compose -f" not in commands
    assert "docker compose" in commands


def test_ci_build_job_does_not_depend_on_repository_secret_db_password() -> None:
    workflow_path = WORKFLOWS_DIR / "ci.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    build_job = parsed["jobs"]["build"]

    for step in build_job["steps"]:
        if step.get("name") in {
            "Build Docker image (CI configuration)",
            "Start containers with healthchecks",
        }:
            env = step["env"]
            assert "DB_PASSWORD" not in env
            assert "secrets.DB_PASSWORD" not in "\n".join(
                str(value) for value in env.values()
            )


def test_code_quality_runner_job_exposes_postgres_port_and_uses_localhost_url() -> None:
    workflow_path = WORKFLOWS_DIR / "code-quality.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    coverage_job = parsed["jobs"]["coverage"]

    assert coverage_job["services"]["postgres-test"]["ports"] == [5432]

    wait_step = next(
        step
        for step in coverage_job["steps"]
        if step.get("name") == "Wait for PostgreSQL service"
    )
    run_step = next(
        step
        for step in coverage_job["steps"]
        if step.get("name") == "Run tests with coverage"
    )

    assert (
        "job.services.postgres-test.ports[5432]"
        in wait_step["env"]["POSTGRES_TEST_PORT"]
    )
    assert (
        "127.0.0.1:${{ job.services.postgres-test.ports[5432] }}"
        in run_step["env"]["DATABASE_URL"]
    )
    assert (
        "127.0.0.1:${{ job.services.postgres-test.ports[5432] }}"
        in run_step["env"]["TEST_DATABASE_URL"]
    )


def test_requirements_dev_includes_hypothesis_for_property_based_tests() -> None:
    requirements = REQUIREMENTS_DEV.read_text(encoding="utf-8").lower()
    assert "hypothesis" in requirements


def test_ci_compose_backend_has_runtime_database_urls() -> None:
    parsed = yaml.safe_load(COMPOSE_CI.read_text(encoding="utf-8"))
    backend_env = parsed["services"]["backend"]["environment"]

    assert (
        backend_env["DATABASE_URL"]
        == "postgresql+asyncpg://postgres:${CI_DB_PASSWORD}@db:5432/neofin"
    )
    assert (
        backend_env["TEST_DATABASE_URL"]
        == "postgresql+asyncpg://postgres:${CI_DB_PASSWORD}@db_test:5432/neofin_test"
    )


def test_gitignore_does_not_hide_frontend_components_required_for_build() -> None:
    critical_paths = [
        "frontend/src/components/AppFooter.tsx",
        "frontend/src/components/ConfidenceBadge.tsx",
        "frontend/src/components/Layout.tsx",
        "frontend/src/components/ProtectedRoute.tsx",
        "frontend/src/components/TrendChart.tsx",
        "frontend/src/components/upload/AiProviderMenu.tsx",
    ]

    for relative_path in critical_paths:
        result = subprocess.run(
            ["git", "check-ignore", "-q", relative_path],
            cwd=REPO_ROOT,
            check=False,
        )
        assert result.returncode != 0, f"{relative_path} must not be ignored by git"
