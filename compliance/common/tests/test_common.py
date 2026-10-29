import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pfe_validators_common import Finding, Severity, create_app, iter_files, render

runner = CliRunner()


def test_render_text() -> None:
    finding = Finding("PFE-X-001", Path("a.py"), "bad", line=3, column=5)
    assert render([finding], "text") == "a.py:3:5: error: [PFE-X-001] bad"


def test_render_github_escapes() -> None:
    finding = Finding("PFE-X-001", Path("a,b.py"), "50%\nmore", line=1, severity=Severity.WARNING)
    assert (
        render([finding], "github")
        == "::warning file=a%2Cb.py,line=1,title=PFE-X-001::50%25%0Amore"
    )


def test_render_json() -> None:
    finding = Finding("PFE-X-001", Path("a.py"), "bad")
    assert json.loads(render([finding], "json")) == [
        {
            "practice": "PFE-X-001",
            "path": "a.py",
            "message": "bad",
            "line": None,
            "column": None,
            "severity": "error",
        }
    ]


def test_iter_files_filters_suffix_and_skips_venv(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.txt").write_text("")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "c.py").write_text("")
    files = list(iter_files([tmp_path], suffixes={".py"}, use_git=False))
    assert files == [tmp_path / "a.py"]


@pytest.mark.parametrize(("findings", "code"), [([], 0), ([Finding("P", Path("x"), "m")], 1)])
def test_cli_exit_codes(tmp_path: Path, findings: list[Finding], code: int) -> None:
    app = create_app("t", "d", lambda _paths: findings)
    result = runner.invoke(app, [str(tmp_path), "--format", "text"])
    assert result.exit_code == code


def test_cli_passes_paths_and_prints_findings(tmp_path: Path) -> None:
    seen: list[Path] = []

    def check(paths: object) -> list[Finding]:
        seen.extend(paths)  # type: ignore[call-overload]
        return [Finding("PFE-X-001", Path("a.py"), "bad", line=1)]

    result = runner.invoke(create_app("t", "d", check), [str(tmp_path), "--format", "text"])
    assert seen == [tmp_path]
    assert "a.py:1: error: [PFE-X-001] bad" in result.output


def test_cli_defaults_to_current_directory() -> None:
    seen: list[Path] = []

    def check(paths: object) -> list[Finding]:
        seen.extend(paths)  # type: ignore[call-overload]
        return []

    assert runner.invoke(create_app("t", "d", check), []).exit_code == 0
    assert seen == [Path(".")]


def test_cli_github_format_default_on_actions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    app = create_app("t", "d", lambda _paths: [Finding("PFE-X-001", Path("a.py"), "bad")])
    result = runner.invoke(app, [str(tmp_path)])
    assert "::error file=a.py,title=PFE-X-001::bad" in result.output


def test_cli_missing_path(tmp_path: Path) -> None:
    result = runner.invoke(create_app("t", "d", lambda _paths: []), [str(tmp_path / "nope")])
    assert result.exit_code == 2


def test_cli_invalid_format(tmp_path: Path) -> None:
    result = runner.invoke(
        create_app("t", "d", lambda _paths: []), [str(tmp_path), "--format", "x"]
    )
    assert result.exit_code == 2


def test_cli_check_error(tmp_path: Path) -> None:
    def boom(_paths: object) -> list[Finding]:
        raise RuntimeError("boom")

    result = runner.invoke(create_app("t", "d", boom), [str(tmp_path)])
    assert result.exit_code == 2


def test_pathless_finding_renders() -> None:
    finding = Finding("PFE-X-001", None, "no file")
    assert render([finding], "text") == "<environment>: error: [PFE-X-001] no file"
    assert render([finding], "github") == "::error title=PFE-X-001::no file"
    assert json.loads(render([finding], "json"))[0]["path"] is None
