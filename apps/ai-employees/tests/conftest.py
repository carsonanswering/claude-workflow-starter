from pathlib import Path

import pytest

from ai_employees import Journal, Manager, MockRunner, TaskQueue, load_company

EXAMPLE = Path(__file__).parent.parent / "examples" / "toyco.yaml"


@pytest.fixture
def toyco():
    return load_company(EXAMPLE)


@pytest.fixture
def manager(toyco, tmp_path):
    company, employees = toyco
    return Manager(
        company=company,
        employees=employees,
        queue=TaskQueue(),
        journal=Journal(tmp_path / "journal.jsonl"),
        runner=MockRunner(),
    )
