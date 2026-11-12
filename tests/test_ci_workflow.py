"""Regression checks for required GitHub Actions CI gates."""

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_keeps_required_triggers_and_python_matrix():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "on:" in workflow
    assert "  push:" in workflow
    assert "  pull_request:" in workflow
    assert 'python-version: ["3.13"]' in workflow
    assert "cache: pip" in workflow
    assert "cache-dependency-path:" in workflow


def test_ci_workflow_uses_postgres_health_and_secret_placeholders():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "image: postgres:16-alpine" in workflow
    assert "POSTGRES_USER:" in workflow
    assert "POSTGRES_PASSWORD:" in workflow
    assert "POSTGRES_DB:" in workflow
    assert "DATABASE_URL:" in workflow
    assert "--health-cmd" in workflow
    assert "secrets.CI_POSTGRES_PASSWORD" in workflow
    assert "secrets.CI_SECRET_KEY" in workflow
    assert "POSTGRES_PASSWORD: postgres" not in workflow


def test_ci_workflow_runs_import_migration_and_quality_gates():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for required_step in (
        "Verify project imports",
        "python -m alembic upgrade head",
        "python -m alembic current",
        "ruff check .",
        "ruff format --check .",
        "pytest",
    ):
        assert required_step in workflow
