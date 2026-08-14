import pytest

from ai_employees import ConfigError, load_company
from tests.conftest import EXAMPLE


def test_load_toyco():
    company, employees = load_company(EXAMPLE)
    assert company.name == "toyco"
    assert company.owner == "schmidtcarson016@gmail.com"
    assert len(company.goals) == 2
    assert len(company.constraints) == 3
    assert company.resources["email_api_key"] == "TOYCO_RESEND_KEY"
    assert len(employees) == 2
    assert company.employees == [e.id for e in employees]
    eng = next(e for e in employees if e.role == "engineer")
    mktr = next(e for e in employees if e.role == "marketer")
    assert eng.name == "Eng-1"
    assert eng.approval_gates == ["deploy_prod", "delete_data"]
    assert mktr.approval_gates == ["send_external", "spend_money"]
    assert mktr.tools == ["Read", "Write", "WebSearch", "WebFetch"]
    assert eng.status == "active"
    assert len(eng.id) == 26


def test_ids_unique_per_load():
    _, a = load_company(EXAMPLE)
    _, b = load_company(EXAMPLE)
    assert a[0].id != b[0].id


def test_missing_file():
    with pytest.raises(ConfigError, match="not found"):
        load_company("/nonexistent/company.yaml")


def test_missing_owner(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("name: x\n")
    with pytest.raises(ConfigError, match="'owner'"):
        load_company(p)


def test_employee_missing_role(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("name: x\nowner: o@x.com\nemployees:\n  - name: E\n    job_description: d\n")
    with pytest.raises(ConfigError, match="'E' is missing required field 'role'"):
        load_company(p)


def test_invalid_yaml(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("name: [unclosed\n")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_company(p)
