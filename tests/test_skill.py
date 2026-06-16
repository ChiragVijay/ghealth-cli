from pathlib import Path

SKILL_PATH = Path("skills/google-health/SKILL.md")


def test_google_health_skill_exists_with_required_frontmatter() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert text.startswith("---\n")
    assert "name: google-health" in text
    assert "description:" in text
    assert "Use `ghealth`" in text


def test_google_health_skill_contains_agent_safety_workflow() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")

    for required in (
        "ghealth --format json doctor",
        "ghealth --format json auth status",
        "ghealth --format json data-types list",
        "ghealth --format json steps daily",
        "ghealth --format json calories daily --last-days 5",
        "Use `--help`",
        "active-energy daily",
        "ghealth --format json exercise list",
        "ghealth --format json nutrition list",
        "total-calories",
        "active-energy-burned",
        "hydration-log",
        "nutrition-log",
        "uv run",
        "ghealth --format json sleep list",
        "--limit",
        "Do not create, update, delete",
        "confirmation_required",
        "missing_scope_or_forbidden",
    ):
        assert required in text


def test_google_health_skill_does_not_contain_real_secret_values() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8").lower()

    assert "access-secret-token" not in text
    assert "refresh-secret-token" not in text
    assert "client-secret-value" not in text
