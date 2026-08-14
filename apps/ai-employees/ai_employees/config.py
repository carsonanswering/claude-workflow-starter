"""YAML company config -> Company + Employee dataclasses. IDs assigned at load."""

from pathlib import Path

import yaml

from .models import Company, Employee, Task


class ConfigError(Exception):
    pass


_REQUIRED_COMPANY = ("name", "owner")
_REQUIRED_EMPLOYEE = ("name", "role", "job_description")
_REQUIRED_TASK = ("title", "description", "assignee_role")


def load_company(path: str | Path) -> tuple[Company, list[Employee]]:
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: not valid YAML: {e}")

    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a mapping, got {type(raw).__name__}")

    for key in _REQUIRED_COMPANY:
        if not raw.get(key):
            raise ConfigError(f"{path}: company is missing required field '{key}'")

    employees_raw = raw.get("employees") or []
    if not isinstance(employees_raw, list):
        raise ConfigError(f"{path}: 'employees' must be a list")

    employees: list[Employee] = []
    for i, e in enumerate(employees_raw):
        if not isinstance(e, dict):
            raise ConfigError(f"{path}: employees[{i}] must be a mapping")
        for key in _REQUIRED_EMPLOYEE:
            if not e.get(key):
                raise ConfigError(
                    f"{path}: employee '{e.get('name', f'#{i}')}' is missing required field '{key}'"
                )
        employees.append(
            Employee(
                name=e["name"],
                role=e["role"],
                job_description=str(e["job_description"]).strip(),
                tools=list(e.get("tools") or []),
                approval_gates=list(e.get("approval_gates") or []),
                max_concurrent_tasks=int(e.get("max_concurrent_tasks", 1)),
            )
        )

    tasks_raw = raw.get("tasks") or []
    if not isinstance(tasks_raw, list):
        raise ConfigError(f"{path}: 'tasks' must be a list")
    for i, t in enumerate(tasks_raw):
        if not isinstance(t, dict):
            raise ConfigError(f"{path}: tasks[{i}] must be a mapping")
        for key in _REQUIRED_TASK:
            if not t.get(key):
                raise ConfigError(
                    f"{path}: task '{t.get('title', f'#{i}')}' is missing required field '{key}'"
                )

    company = Company(
        name=raw["name"],
        owner=raw["owner"],
        goals=list(raw.get("goals") or []),
        constraints=list(raw.get("constraints") or []),
        resources={k: str(v) for k, v in (raw.get("resources") or {}).items()},
        employees=[e.id for e in employees],
    )
    return company, employees


def load_tasks(path: str | Path) -> list[Task]:
    """Optional 'tasks' section of the same company YAML -> Task list.
    Validation happens in load_company; call that first."""
    path = Path(path)
    raw = yaml.safe_load(path.read_text())
    tasks = []
    for t in (raw.get("tasks") or []):
        tasks.append(
            Task(
                title=t["title"],
                description=str(t["description"]).strip(),
                assignee_role=t["assignee_role"],
                priority=int(t.get("priority", 2)),
                gate_tags=list(t.get("gate_tags") or []),
            )
        )
    return tasks
