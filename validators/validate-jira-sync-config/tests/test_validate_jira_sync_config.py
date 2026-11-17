# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the gh-jira-sync-bot configuration validator."""

from pathlib import Path

from typer.testing import CliRunner
from validate_jira_sync_config.cli import app
from validate_jira_sync_config.config import validate_issue_templates, validate_settings


def _valid_config() -> dict[str, object]:
    return {
        "settings": {
            "jira_project_key": "ISD",
            "status_mapping": {
                "opened": "Untriaged",
                "closed": "done",
                "not_planned": "rejected",
            },
            "add_gh_comment": True,
            "labels": ["bug", "enhancement"],
            "label_mapping": {"bug": "Bug", "enhancement": "Story"},
            "components": ["CharmCI"],
        }
    }


def _settings(config: dict[str, object]) -> dict[str, object]:
    settings = config["settings"]
    assert isinstance(settings, dict)
    return settings


def test_compliant_configuration_has_no_errors() -> None:
    assert validate_settings(_valid_config()) == []


def test_missing_settings_mapping_is_reported() -> None:
    assert validate_settings({}) == ["top-level `settings` mapping is mandatory"]
    assert validate_settings({"settings": []}) == ["top-level `settings` mapping is mandatory"]


def test_missing_jira_project_key_is_reported() -> None:
    config = _valid_config()
    del _settings(config)["jira_project_key"]
    assert "settings.jira_project_key is mandatory (non-empty string)" in validate_settings(config)


def test_status_mapping_must_be_a_mapping() -> None:
    config = _valid_config()
    _settings(config)["status_mapping"] = ["opened"]
    assert "settings.status_mapping is mandatory and must be a mapping" in (
        validate_settings(config)
    )


def test_missing_mandatory_status_keys_are_reported() -> None:
    config = _valid_config()
    _settings(config)["status_mapping"] = {"opened": "Untriaged"}
    errors = validate_settings(config)
    assert "settings.status_mapping.closed is mandatory (non-empty string)" in errors


def test_empty_not_planned_status_is_reported() -> None:
    config = _valid_config()
    status_mapping = _settings(config)["status_mapping"]
    assert isinstance(status_mapping, dict)
    status_mapping["not_planned"] = ""
    assert "settings.status_mapping.not_planned must be a non-empty string" in validate_settings(
        config
    )


def test_singular_component_is_rejected() -> None:
    config = _valid_config()
    settings = _settings(config)
    settings["component"] = ["CharmCI"]
    del settings["components"]
    errors = validate_settings(config)
    assert (
        "settings.component is not supported by the bot, use the list settings.components"
        in errors
    )
    assert "settings.components is mandatory and must be a non-empty list" in errors


def test_missing_or_empty_components_are_reported() -> None:
    config = _valid_config()
    _settings(config)["components"] = []
    assert "settings.components is mandatory and must be a non-empty list" in validate_settings(
        config
    )

    config = _valid_config()
    del _settings(config)["components"]
    assert "settings.components is mandatory and must be a non-empty list" in validate_settings(
        config
    )


def test_placeholder_component_is_reported() -> None:
    config = _valid_config()
    _settings(config)["components"] = ["<your-component>"]
    assert (
        "settings.components still contains the placeholder <your-component>"
        in validate_settings(config)
    )


def test_unknown_component_is_reported() -> None:
    config = _valid_config()
    _settings(config)["components"] = ["not-a-jira-component"]
    errors = validate_settings(config)
    assert len(errors) == 1
    assert "settings.components: 'not-a-jira-component' is not a valid Jira component" in errors[0]


def test_labels_must_be_a_list_and_include_required_values() -> None:
    config = _valid_config()
    _settings(config)["labels"] = "bug"
    assert "settings.labels is mandatory and must be a list of non-empty strings" in (
        validate_settings(config)
    )

    config = _valid_config()
    _settings(config)["labels"] = ["bug"]
    errors = validate_settings(config)
    assert len(errors) == 1
    assert "settings.labels must include bug, enhancement (missing: enhancement)" in errors[0]


def test_epic_key_is_rejected() -> None:
    config = _valid_config()
    _settings(config)["epic_key"] = "ISD-1"
    assert "settings.epic_key must not be defined" in validate_settings(config)


def test_label_mapping_values_must_be_strings() -> None:
    config = _valid_config()
    _settings(config)["label_mapping"] = {"bug": 1}
    assert "settings.label_mapping must map GitHub labels to Jira issue types (strings)" in (
        validate_settings(config)
    )


def test_add_gh_comment_must_be_a_boolean() -> None:
    config = _valid_config()
    _settings(config)["add_gh_comment"] = "yes"
    assert "settings.add_gh_comment must be a boolean" in validate_settings(config)


def test_issue_templates_must_carry_bug_or_enhancement(tmp_path: Path) -> None:
    issue_template_dir = tmp_path / "ISSUE_TEMPLATE"
    issue_template_dir.mkdir()
    (issue_template_dir / "bug_report.yml").write_text('labels: ["bug"]\n')
    (issue_template_dir / "enhancement_proposal.md").write_text(
        "---\nlabels: [enhancement]\n---\n\nBody\n"
    )
    (issue_template_dir / "string_labels.yml").write_text('labels: "bug, enhancement"\n')
    (issue_template_dir / "config.yml").write_text("blank_issues_enabled: false\n")

    assert validate_issue_templates(issue_template_dir) == []


def test_issue_template_without_required_label_is_reported(tmp_path: Path) -> None:
    issue_template_dir = tmp_path / "ISSUE_TEMPLATE"
    issue_template_dir.mkdir()
    template = issue_template_dir / "question.yml"
    template.write_text('labels: ["question"]\n')

    assert validate_issue_templates(issue_template_dir) == [
        f"{template}: `labels` must contain bug or enhancement"
    ]


def test_cli_prints_ok_for_a_compliant_configuration(tmp_path: Path) -> None:
    config_path = tmp_path / ".jira_sync_config.yaml"
    config_path.write_text(
        """\
settings:
  jira_project_key: ISD
  status_mapping:
    opened: Untriaged
    closed: done
  labels: [bug, enhancement]
  components: [CharmCI]
"""
    )

    result = CliRunner().invoke(app, [str(config_path)])

    assert result.exit_code == 0
    assert f"{config_path}: OK" in result.output


def test_cli_fails_for_an_invalid_configuration(tmp_path: Path) -> None:
    config_path = tmp_path / ".jira_sync_config.yaml"
    config_path.write_text("settings:\n  components: []\n")

    result = CliRunner().invoke(app, [str(config_path)])

    assert result.exit_code == 1
    assert "ERROR: settings.jira_project_key is mandatory (non-empty string)" in result.output


def test_cli_fails_when_the_file_cannot_be_read(tmp_path: Path) -> None:
    config_path = tmp_path / "missing.yaml"

    result = CliRunner().invoke(app, [str(config_path)])

    assert result.exit_code == 1
    assert f"ERROR: cannot read {config_path}" in result.output
