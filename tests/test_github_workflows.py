from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def test_all_github_workflows_are_valid_yaml() -> None:
    workflow_paths = sorted(WORKFLOWS_DIR.glob("*.yml"))
    assert workflow_paths, "Expected GitHub workflow files to exist"

    for workflow_path in workflow_paths:
        parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict), f"{workflow_path.name} must parse into a mapping"


def test_ci_build_job_uses_env_for_build_flags() -> None:
    workflow_path = WORKFLOWS_DIR / "ci.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    jobs = parsed["jobs"]
    build_job = jobs["build"]

    assert "env" in build_job, "Build job should declare build flags via env"
    assert "environment" not in build_job, "Build job should not misuse environment for env vars"
