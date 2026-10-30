from pathlib import Path

from validators.check_structure import check_kb, check_skills, main


def test_valid(tmp_path: Path):
    skill = tmp_path / "skills" / "foo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: foo\ndescription: Does foo\n---\nBody\n")
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "a.md").write_text("---\ntitle: A\nowner: team\n---\n")
    assert main([str(tmp_path)]) == 0


def test_invalid_skill(tmp_path: Path):
    (tmp_path / "skills" / "bar").mkdir(parents=True)
    (tmp_path / "skills" / "foo").mkdir()
    (tmp_path / "skills" / "foo" / "SKILL.md").write_text("---\nname: other\n---\n")
    errors = check_skills(tmp_path)
    assert len(errors) == 3


def test_invalid_kb(tmp_path: Path):
    (tmp_path / "kb").mkdir()
    (tmp_path / "kb" / "a.md").write_text("no front matter")
    assert len(check_kb(tmp_path)) == 2
