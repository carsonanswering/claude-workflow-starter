import shutil
from pathlib import Path

import yaml

from ai_employees.cli import main
from ai_employees.config import load_company
from ai_employees.journal import Journal

EXAMPLE = Path(__file__).parent.parent / "examples" / "toyco.yaml"


def company_copy(tmp_path):
    dest = tmp_path / "toyco.yaml"
    shutil.copy(EXAMPLE, dest)
    return dest


def run_hire(argv_extra, answers, tmp_path=None):
    it = iter(answers)
    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        return next(it)

    code = main(["hire", *argv_extra], input_fn=fake_input)
    return code, prompts


def test_hire_list_shows_templates(capsys):
    code = main(["hire", "--list"])
    assert code == 0
    out = capsys.readouterr().out
    for name in ("engineer", "marketer", "support", "ops", "researcher"):
        assert name in out


def test_hire_preview_shown_before_prompt(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    company = company_copy(tmp_path)
    code, prompts = run_hire(["engineer", "--name", "Eng-2", "--company", str(company)], ["y"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Role: engineer" in out
    assert "Job description:" in out
    assert "Default tools:" in out
    assert "Default approval gates:" in out
    assert prompts and "Hire Eng-2 with these defaults?" in prompts[0]


def test_hire_accept_appends_and_round_trips(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    company = company_copy(tmp_path)
    original_employees = len(yaml.safe_load(company.read_text())["employees"])

    code, _ = run_hire(["engineer", "--name", "Eng-2", "--company", str(company)], ["y"])
    assert code == 0

    raw = yaml.safe_load(company.read_text())
    assert len(raw["employees"]) == original_employees + 1

    # existing content preserved, round-trips through load_company
    company_obj, employees = load_company(company)
    assert company_obj.name == "toyco"
    assert company_obj.goals  # untouched
    names = {e.name for e in employees}
    assert "Eng-2" in names
    assert "Eng-1" in names and "Mktr-1" in names  # existing employees preserved

    new_emp = next(e for e in employees if e.name == "Eng-2")
    assert new_emp.role == "engineer"
    assert "toyco" in new_emp.job_description
    assert new_emp.tools == ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
    assert new_emp.approval_gates == ["deploy_prod", "delete_data"]

    # journal entry recorded
    entries = Journal(tmp_path / "runs" / "toyco" / "journal.jsonl").read()
    hired = [e for e in entries if e.action == "hired"]
    assert len(hired) == 1
    assert hired[0].employee_id == "manager"
    assert hired[0].task_id is None
    assert "Eng-2" in hired[0].summary


def test_hire_decline_leaves_file_untouched(tmp_path):
    company = company_copy(tmp_path)
    before = company.read_text()

    code, _ = run_hire(["engineer", "--name", "Eng-2", "--company", str(company)], ["n"])
    assert code == 0
    assert company.read_text() == before


def test_hire_unknown_template_errors(tmp_path, capsys):
    company = company_copy(tmp_path)
    code, _ = run_hire(["bogus", "--name", "X", "--company", str(company)], [])
    assert code == 1
    err = capsys.readouterr().err
    assert "unknown template" in err
    assert "bogus" in err
    # file untouched
    raw = yaml.safe_load(company.read_text())
    assert not any(e.get("name") == "X" for e in raw["employees"])
