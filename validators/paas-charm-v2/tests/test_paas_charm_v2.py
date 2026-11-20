# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the paas-charm 2.0 compliance checker."""

import textwrap
from pathlib import Path

import pytest
from paas_charm_v2.check import (
    _pin_allows_only_v2,
    build_report,
    check_charm_base,
    check_rock_base,
    check_uv_plugin,
    main,
)
from paas_charm_v2.paas_config import check_paas_config
from paas_charm_v2.project import discover

COMPLIANT_CHARMCRAFT = """\
name: flask-k8s
type: charm
base: ubuntu@26.04
extensions:
  - flask-framework
platforms:
  amd64:
config:
  options:
    app-secret-key:
      type: secret
    log-level:
      type: string
containers:
  app:
    resource: app-image
peers:
  peers:
    interface: peers
requires:
  postgresql:
    interface: postgresql_client
    optional: true
resources:
  app-image:
    type: oci-image
parts:
  charm:
    source: .
    plugin: uv
    build-snaps:
      - astral-uv
"""

COMPLIANT_PYPROJECT = """\
[project]
name = "flask-k8s"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = ["paas-charm>=2.0b1,<3"]
"""

COMPLIANT_PAAS_CONFIG = """\
port: 8000
metrics-port: 9102
metrics-path: /metrics
"""

COMPLIANT_ROCKCRAFT = """\
name: flask-app
base: ubuntu@26.04
platforms:
  amd64:
extensions:
  - flask-framework
"""


def write_charm(root: Path, charmcraft: str = COMPLIANT_CHARMCRAFT, **files: str) -> Path:
    """Create a charm project directory and return it."""
    directory = root / "charm"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "charmcraft.yaml").write_text(charmcraft)
    (directory / "pyproject.toml").write_text(files.pop("pyproject", COMPLIANT_PYPROJECT))
    (directory / "uv.lock").write_text("")
    (directory / "paas-config.yaml").write_text(files.pop("paas_config", COMPLIANT_PAAS_CONFIG))
    write_upgrade_docs(root)
    for name, content in files.items():
        path = directory / name.replace("__", "/").replace("_py", ".py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return directory


def write_upgrade_docs(root: Path, guide: bool = True, changelog: bool = True) -> None:
    """Create the upgrade guide and changelog documenting Juju bug LP#1991955."""
    docs = root / "docs"
    (docs / "how-to").mkdir(parents=True, exist_ok=True)
    if guide:
        (docs / "how-to" / "upgrade.md").write_text(
            "Juju before 4.1, bug LP#1991955: run `juju remove-application` and redeploy.\n"
        )
    if changelog:
        (docs / "changelog.md").write_text("Redeploy needed, see LP#1991955.\n")


def write_rock(root: Path, rockcraft: str = COMPLIANT_ROCKCRAFT) -> Path:
    """Create a rock project directory and return it."""
    (root / "rockcraft.yaml").write_text(rockcraft)
    return root


def test_compliant_project_has_no_violations(tmp_path: Path) -> None:
    write_charm(tmp_path)
    write_rock(tmp_path)
    report = build_report(discover(tmp_path))
    assert report.violations == []
    assert report.framework == "flask"


def test_legacy_base_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path, COMPLIANT_CHARMCRAFT.replace("ubuntu@26.04", "ubuntu@24.04"))
    project = discover(tmp_path)
    violations = check_charm_base(project.charms[0], tmp_path)
    assert violations and "ubuntu@26.04" in violations[0]


def test_bases_key_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path, "name: flask-k8s\nbases:\n  - name: ubuntu\n    channel: '22.04'\n")
    project = discover(tmp_path)
    assert "legacy `bases` key" in check_charm_base(project.charms[0], tmp_path)[0]


@pytest.mark.parametrize(
    ("rockcraft", "expected"),
    [
        ("name: a\nbase: ubuntu@26.04\n", 0),
        ("name: a\nbase: bare\nbuild-base: ubuntu@26.04\n", 0),
        ("name: a\nbase: bare\nbuild-base: ubuntu@24.04\n", 1),
        ("name: a\nbase: ubuntu@22.04\n", 1),
    ],
)
def test_rock_base(tmp_path: Path, rockcraft: str, expected: int) -> None:
    write_rock(tmp_path, rockcraft)
    project = discover(tmp_path)
    assert len(check_rock_base(project.rocks[0], tmp_path)) == expected


def test_rock_part_separator_and_prime_entries(tmp_path: Path) -> None:
    write_rock(
        tmp_path,
        textwrap.dedent("""\
            name: a
            base: ubuntu@26.04
            extensions:
              - flask-framework
            parts:
              flask-framework/dependencies:
                plugin: nil
              install-app:
                prime:
                  - flask/app/app.py
            """),
    )
    report = build_report(discover(tmp_path))
    violations = "\n".join(report.violations)
    assert "flask-framework.dependencies" in violations
    assert "must start with 'app'" in violations


def test_charm_plugin_and_requirements_are_reported(tmp_path: Path) -> None:
    directory = write_charm(
        tmp_path,
        COMPLIANT_CHARMCRAFT.replace("plugin: uv", "plugin: charm"),
    )
    (directory / "requirements.txt").write_text("paas-charm==1.11.3\n")
    (directory / "uv.lock").unlink()
    violations = "\n".join(check_uv_plugin(discover(tmp_path).charms[0], tmp_path))
    assert "'charm' plugin" in violations
    assert "requirements.txt" in violations
    assert "uv.lock" in violations


@pytest.mark.parametrize(
    ("specifier", "valid"),
    [
        ("==2.0", True),
        ("==2.0.*", True),
        (">=2,<3", True),
        (">=2.0b1,<3", True),
        ("~=2.0", True),
        ("==1.11.3", False),
        (">=1,<3", False),
        (">=2", False),
        ("<3", False),
        (">=2,<4", False),
    ],
)
def test_pin_allows_only_v2(specifier: str, valid: bool) -> None:
    assert _pin_allows_only_v2(specifier) is valid


def test_unpinned_paas_charm_is_reported(tmp_path: Path) -> None:
    write_charm(
        tmp_path,
        pyproject=COMPLIANT_PYPROJECT.replace('"paas-charm>=2.0b1,<3"', '"paas-charm"'),
    )
    report = build_report(discover(tmp_path))
    assert any("unpinned" in violation for violation in report.violations)


def test_old_python_requirement_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path, pyproject=COMPLIANT_PYPROJECT.replace(">=3.14", ">=3.12"))
    report = build_report(discover(tmp_path))
    assert any("requires-python" in violation for violation in report.violations)


def test_flask_container_rename_is_reported(tmp_path: Path) -> None:
    write_charm(
        tmp_path,
        COMPLIANT_CHARMCRAFT.replace(
            "  app:\n    resource: app-image",
            "  flask-app:\n    resource: flask-app-image",
        ).replace(
            "  app-image:\n    type: oci-image",
            "  flask-app-image:\n    type: oci-image",
        ),
    )
    report = build_report(discover(tmp_path))
    violations = "\n".join(report.violations)
    assert "expected 'app'" in violations
    assert "flask-app-image" in violations


def test_retired_contract_is_reported(tmp_path: Path) -> None:
    charmcraft = COMPLIANT_CHARMCRAFT.replace(
        "peers:\n  peers:\n    interface: peers",
        "peers:\n  secret-storage:\n    interface: secret-storage",
    ).replace(
        "    log-level:\n      type: string",
        "    flask-secret-key:\n      type: string\n    webserver-port:\n      type: int",
    )
    write_charm(tmp_path, charmcraft)
    report = build_report(discover(tmp_path))
    violations = "\n".join(report.violations)
    assert "secret-storage" in violations
    assert "flask-secret-key" in violations
    assert "webserver-port" in violations


def test_hand_coded_relation_is_reported(tmp_path: Path) -> None:
    charmcraft = COMPLIANT_CHARMCRAFT.replace(
        "requires:\n",
        "requires:\n  temporal-host-info:\n    interface: temporal-host-info\n"
        "    optional: true\n",
    )
    write_charm(
        tmp_path,
        charmcraft,
        src__charm_py=textwrap.dedent("""\
            class FlaskCharm(paas_charm.flask.Charm):
                def __init__(self, *args):
                    super().__init__(*args)
                    self.framework.observe(
                        self.on["temporal-host-info"].relation_changed, self._on_changed
                    )
            """),
    )
    report = build_report(discover(tmp_path))
    violations = "\n".join(report.violations)
    assert "CustomRelation" in violations
    assert "temporal-host-info" in violations


def test_registered_custom_relation_passes(tmp_path: Path) -> None:
    charmcraft = COMPLIANT_CHARMCRAFT.replace(
        "requires:\n",
        "requires:\n  temporal-host-info:\n    interface: temporal-host-info\n"
        "    optional: true\n",
    )
    write_charm(
        tmp_path,
        charmcraft,
        src__charm_py=textwrap.dedent("""\
            class TemporalRelation(CustomRelation):
                relation_name = "temporal-host-info"


            class FlaskCharm(paas_charm.flask.Charm):
                custom_relations = [TemporalRelation]
            """),
    )
    report = build_report(discover(tmp_path))
    assert report.violations == []


def test_undeclared_custom_relation_is_reported(tmp_path: Path) -> None:
    write_charm(
        tmp_path,
        src__charm_py=(
            'class R(CustomRelation):\n    relation_name = "temporal"\n\ncustom_relations = [R]\n'
        ),
    )
    report = build_report(discover(tmp_path))
    assert any("not declared under requires" in violation for violation in report.violations)


def test_paas_app_charmer_import_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path, src__charm_py="import paas_app_charmer.flask\n")
    report = build_report(discover(tmp_path))
    assert any("paas_app_charmer" in violation for violation in report.violations)


def test_valid_paas_config_passes() -> None:
    config = {
        "port": 8080,
        "metrics-port": 9102,
        "metrics-path": "/metrics",
        "framework_logging_format": "json",
        "prometheus": {
            "scrape_configs": [{"job_name": "extra", "static_configs": [{"targets": ["*:8081"]}]}]
        },
        "config": {"options": {"log-level": {"env-var": "LOG_LEVEL"}}},
    }
    assert check_paas_config(config, "flask", {"log-level": "string"}) == []


@pytest.mark.parametrize(
    ("config", "framework", "expected"),
    [
        ({"ports": 80}, "flask", "unknown top-level field"),
        ({"port": 0}, "flask", "between 1 and 65535"),
        ({"metrics-path": "metrics"}, "flask", "slash-prefixed"),
        ({"framework_logging_format": "text"}, "flask", "must be json"),
        ({"framework_logging_format": "json"}, "go", "not supported"),
        ({"prometheus": {"scrape_configs": [{}]}}, "flask", "job_name is required"),
    ],
)
def test_invalid_paas_config(config: dict, framework: str, expected: str) -> None:
    assert any(expected in violation for violation in check_paas_config(config, framework))


def test_paas_config_mapping_rules() -> None:
    config = {
        "config": {
            "options": {
                "a": {"env-var": "X", "secret-env-vars": {"k": "Y"}},
                "b": {"env-var": "Z"},
                "c": {"env-var": "Z"},
            }
        }
    }
    violations = "\n".join(
        check_paas_config(config, "flask", dict.fromkeys(("a", "b", "c"), "string"))
    )
    assert "exactly one of env-var or secret-env-vars" in violations
    assert "duplicate environment variable destination" in violations


def test_paas_config_unknown_source_option() -> None:
    config = {"config": {"options": {"missing": {"env-var": "X"}}}}
    violations = check_paas_config(config, "flask", {"log-level": "string"})
    assert any("does not match a config option" in violation for violation in violations)


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path, "name: [unclosed\n")
    report = build_report(discover(tmp_path))
    assert any("invalid YAML" in violation for violation in report.violations)


def test_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    assert main(["--list-checks"]) == 0
    assert main([]) == 2
    write_charm(tmp_path)
    write_rock(tmp_path)
    assert main([str(tmp_path), "--verbose"]) == 0
    write_charm(tmp_path, COMPLIANT_CHARMCRAFT.replace("ubuntu@26.04", "ubuntu@22.04"))
    assert main([str(tmp_path)]) == 1
    assert "charm-base" in capsys.readouterr().out


def test_requirements_txt_pin_is_reported(tmp_path: Path) -> None:
    directory = write_charm(tmp_path)
    (directory / "pyproject.toml").unlink()
    (directory / "requirements.txt").write_text("paas-charm==1.11.3\n")
    report = build_report(discover(tmp_path))
    assert any("pinned in requirements.txt" in violation for violation in report.violations)


def test_multiline_relation_observe_is_reported(tmp_path: Path) -> None:
    write_charm(
        tmp_path,
        src__charm_py=textwrap.dedent("""\
            class Charm(paas_charm.flask.Charm):
                def __init__(self, *args):
                    super().__init__(*args)
                    self.framework.observe(
                        self.on["temporal-host-info"].relation_changed,
                        self._on_changed,
                    )
            """),
    )
    report = build_report(discover(tmp_path))
    assert any("relation event observed directly" in v for v in report.violations)


def test_removed_base_hook_override_is_reported(tmp_path: Path) -> None:
    write_charm(
        tmp_path,
        src__charm_py=textwrap.dedent("""\
            class FlaskCharm(paas_charm.flask.Charm):
                def _on_config_changed(self, event):
                    super()._on_config_changed(event)
            """),
    )
    write_rock(tmp_path)
    violations = "\n".join(build_report(discover(tmp_path)).violations)
    assert "_reconcile" in violations
    assert "_on_config_changed" in violations


def test_reconcile_override_passes(tmp_path: Path) -> None:
    write_charm(
        tmp_path,
        src__charm_py=textwrap.dedent("""\
            class FlaskCharm(paas_charm.flask.Charm):
                def _reconcile(self, rerun_migrations=False):
                    super()._reconcile(rerun_migrations)
            """),
    )
    write_rock(tmp_path)
    assert build_report(discover(tmp_path)).violations == []


def test_uv_lock_must_be_ignored_by_license_check(tmp_path: Path) -> None:
    write_charm(tmp_path)
    write_rock(tmp_path)
    (tmp_path / ".licenserc.yaml").write_text("header:\n  paths-ignore:\n    - 'LICENSE'\n")
    assert "charm/uv.lock" in "\n".join(build_report(discover(tmp_path)).violations)
    (tmp_path / ".licenserc.yaml").write_text(
        "header:\n  paths-ignore:\n    - 'LICENSE'\n    - 'charm/uv.lock'\n"
    )
    assert build_report(discover(tmp_path)).violations == []


def test_removed_requirements_txt_reference_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path)
    write_rock(tmp_path)
    (tmp_path / "tox.ini").write_text(
        "[testenv]\ndeps =\n    -r{toxinidir}/charm/requirements.txt\n"
    )
    violations = "\n".join(build_report(discover(tmp_path)).violations)
    assert "tox.ini" in violations


def test_gunicorn_constraints_override_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path)
    rock = COMPLIANT_ROCKCRAFT + (
        "parts:\n  flask-framework.dependencies:\n    override-build: |\n      craftctl default\n"
    )
    write_rock(tmp_path, rock)
    assert ".gunicorn-constraints.txt" in "\n".join(build_report(discover(tmp_path)).violations)
    write_rock(tmp_path, rock.replace("craftctl default", "echo x > .gunicorn-constraints.txt"))
    assert build_report(discover(tmp_path)).violations == []


def _license_violations(tmp_path: Path) -> str:
    return "\n".join(build_report(discover(tmp_path)).violations)


@pytest.mark.parametrize(
    "ignore",
    ["charm/uv.lock", "**/uv.lock", "uv.lock", "charm/*.lock", "charm", "charm/**"],
)
def test_charm_dir_uv_lock_ignore_patterns(tmp_path: Path, ignore: str) -> None:
    write_charm(tmp_path)
    write_rock(tmp_path)
    (tmp_path / ".licenserc.yaml").write_text(f"header:\n  paths-ignore:\n    - '{ignore}'\n")
    assert _license_violations(tmp_path) == ""


def test_charm_in_repo_root_uses_root_uv_lock(tmp_path: Path) -> None:
    (tmp_path / "charmcraft.yaml").write_text(COMPLIANT_CHARMCRAFT)
    (tmp_path / "pyproject.toml").write_text(COMPLIANT_PYPROJECT)
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "paas-config.yaml").write_text(COMPLIANT_PAAS_CONFIG)
    write_upgrade_docs(tmp_path)
    write_rock(tmp_path)
    (tmp_path / ".licenserc.yaml").write_text("header:\n  paths-ignore:\n    - 'LICENSE'\n")
    assert "'uv.lock'" in _license_violations(tmp_path)
    (tmp_path / ".licenserc.yaml").write_text("header:\n  paths-ignore:\n    - 'uv.lock'\n")
    assert _license_violations(tmp_path) == ""


def test_uv_lock_elsewhere_is_not_the_charm_lock(tmp_path: Path) -> None:
    directory = write_charm(tmp_path)
    (directory / "uv.lock").unlink()
    (tmp_path / "uv.lock").write_text("")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "uv.lock").write_text("")
    write_rock(tmp_path)
    (tmp_path / ".licenserc.yaml").write_text("header:\n  paths-ignore:\n    - 'LICENSE'\n")
    violations = _license_violations(tmp_path)
    assert "missing uv.lock" in violations
    assert ".licenserc.yaml" not in violations


def test_missing_uv_lock_everywhere_is_reported(tmp_path: Path) -> None:
    directory = write_charm(tmp_path)
    (directory / "uv.lock").unlink()
    write_rock(tmp_path)
    assert "missing uv.lock" in _license_violations(tmp_path)


def test_flask_without_upgrade_docs_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path)
    for doc in (tmp_path / "docs").rglob("*.md"):
        doc.unlink()
    violations = "\n".join(build_report(discover(tmp_path)).violations)
    assert "upgrade guide" in violations
    assert "changelog" in violations
    assert "1991955" in violations


def test_missing_changelog_entry_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path)
    (tmp_path / "docs" / "changelog.md").write_text("nothing here\n")
    violations = build_report(discover(tmp_path)).violations
    assert len(violations) == 1 and violations[0].startswith("changelog")


def test_guide_without_remove_instruction_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path)
    (tmp_path / "docs" / "how-to" / "upgrade.md").write_text("Juju before 4.1, see LP#1991955.\n")
    violations = build_report(discover(tmp_path)).violations
    assert len(violations) == 1 and violations[0].startswith("upgrade guide")


def test_django_requires_upgrade_docs(tmp_path: Path) -> None:
    write_charm(tmp_path, COMPLIANT_CHARMCRAFT.replace("flask-framework", "django-framework"))
    (tmp_path / "docs" / "changelog.md").unlink()
    report = build_report(discover(tmp_path))
    assert any(v.startswith("changelog") for v in report.violations)


def test_other_frameworks_skip_upgrade_docs(tmp_path: Path) -> None:
    write_charm(tmp_path, COMPLIANT_CHARMCRAFT.replace("flask-framework", "fastapi-framework"))
    for doc in (tmp_path / "docs").rglob("*.md"):
        doc.unlink()
    report = build_report(discover(tmp_path))
    result = next(c for c in report.checks if c.slug == "upgrade-docs")
    assert result.skip_reason and not result.violations


def test_guide_without_juju_version_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path)
    (tmp_path / "docs" / "how-to" / "upgrade.md").write_text(
        "LP#1991955: run `juju remove-application`.\n"
    )
    violations = build_report(discover(tmp_path)).violations
    assert len(violations) == 1 and "earlier than 4.1" in violations[0]


def test_missing_paas_config_is_reported(tmp_path: Path) -> None:
    directory = write_charm(tmp_path)
    (directory / "paas-config.yaml").unlink()
    report = build_report(discover(tmp_path))
    result = next(c for c in report.checks if c.slug == "paas-config")
    assert result.skip_reason is None
    assert any("missing; add it" in v for v in result.violations)


def test_paas_config_requires_port_and_metrics_keys(tmp_path: Path) -> None:
    write_charm(tmp_path, paas_config="port: 8000\n")
    report = build_report(discover(tmp_path))
    result = next(c for c in report.checks if c.slug == "paas-config")
    assert len(result.violations) == 2
    assert all("metrics-" in v for v in result.violations)


def test_missing_charm_plugin_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path, COMPLIANT_CHARMCRAFT.replace("    plugin: uv\n", ""))
    violations = "\n".join(build_report(discover(tmp_path)).violations)
    assert "expected 'uv'" in violations


def test_missing_requires_python_is_reported(tmp_path: Path) -> None:
    write_charm(
        tmp_path, pyproject=COMPLIANT_PYPROJECT.replace('requires-python = ">=3.14"\n', "")
    )
    violations = "\n".join(build_report(discover(tmp_path)).violations)
    assert "requires-python is missing" in violations


def test_locked_paas_charm_1x_is_reported(tmp_path: Path) -> None:
    directory = write_charm(tmp_path)
    (directory / "uv.lock").write_text(
        'version = 1\n\n[[package]]\nname = "paas-charm"\nversion = "1.9.0"\n'
    )
    violations = "\n".join(build_report(discover(tmp_path)).violations)
    assert "locked to '1.9.0'" in violations


def test_locked_paas_charm_2x_passes(tmp_path: Path) -> None:
    directory = write_charm(tmp_path)
    (directory / "uv.lock").write_text(
        'version = 1\n\n[[package]]\nname = "paas-charm"\nversion = "2.0.0"\n'
    )
    assert build_report(discover(tmp_path)).violations == []


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("containers:\n  app:\n    resource: app-image\n", "", "expected 'app'"),
        ("    resource: app-image\n", "", "expected 'app-image'"),
        ("peers:\n  peers:\n    interface: peers\n", "", "missing the 'peers'"),
        ("    app-secret-key:\n      type: secret\n", "", "missing the 'app-secret-key'"),
    ],
)
def test_missing_contract_entries_are_reported(
    tmp_path: Path, old: str, new: str, expected: str
) -> None:
    write_charm(tmp_path, COMPLIANT_CHARMCRAFT.replace(old, new))
    violations = "\n".join(build_report(discover(tmp_path)).violations)
    assert expected in violations


def test_framework_working_dir_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path)
    write_rock(
        tmp_path,
        COMPLIANT_ROCKCRAFT + "services:\n  worker:\n    command: run\n    working-dir: /flask\n",
    )
    violations = "\n".join(build_report(discover(tmp_path)).violations)
    assert "references '/flask'" in violations


def test_relation_observer_next_to_custom_relations_is_reported(tmp_path: Path) -> None:
    charmcraft = COMPLIANT_CHARMCRAFT.replace(
        "requires:\n",
        "requires:\n  temporal:\n    interface: temporal\n    optional: true\n",
    )
    write_charm(
        tmp_path,
        charmcraft,
        src__charm_py=textwrap.dedent("""\
            class TemporalRelation(CustomRelation):
                relation_name = "temporal"


            class FlaskCharm(paas_charm.flask.Charm):
                custom_relations = [TemporalRelation]

                def __init__(self, *args):
                    super().__init__(*args)
                    self.framework.observe(self.on["db"].relation_changed, self._on_changed)
            """),
    )
    violations = "\n".join(build_report(discover(tmp_path)).violations)
    assert "relation event observed directly" in violations


def test_workflow_requirements_reference_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path)
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "test.yaml").write_text("run: pip install -r charm/requirements.txt\n")
    violations = "\n".join(build_report(discover(tmp_path)).violations)
    assert ".github/workflows/test.yaml: references the removed" in violations


def test_licenserc_yml_is_named_in_message(tmp_path: Path) -> None:
    write_charm(tmp_path)
    (tmp_path / ".licenserc.yml").write_text("header:\n  paths-ignore:\n    - LICENSE\n")
    violations = "\n".join(build_report(discover(tmp_path)).violations)
    assert ".licenserc.yml: add" in violations


def test_changelog_with_bare_bug_reference_is_reported(tmp_path: Path) -> None:
    write_charm(tmp_path)
    (tmp_path / "docs" / "changelog.md").write_text("See LP#1991955.\n")
    violations = build_report(discover(tmp_path)).violations
    assert len(violations) == 1 and violations[0].startswith("changelog")


def test_paas_config_with_no_declared_options() -> None:
    config = {"config": {"options": {"missing": {"env-var": "X"}}}}
    violations = check_paas_config(config, "flask", {})
    assert any("does not match a config option" in violation for violation in violations)


def test_paas_config_mapping_must_match_option_type() -> None:
    config = {
        "config": {
            "options": {
                "token": {"env-var": "TOKEN"},
                "level": {"secret-env-vars": {"value": "LEVEL"}},
            }
        }
    }
    violations = "\n".join(
        check_paas_config(config, "flask", {"token": "secret", "level": "string"})
    )
    assert "token is a secret option" in violations
    assert "level is a string option" in violations
