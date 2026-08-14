"""Append-only JSONL journal. Source of truth; task state is derivable from it."""

import json
import os
import warnings
from pathlib import Path

from .models import JournalEntry


class Journal:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: JournalEntry) -> JournalEntry:
        with self.path.open("a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return entry

    def read(self) -> list[JournalEntry]:
        if not self.path.exists():
            return []
        entries = []
        with self.path.open() as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(JournalEntry.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError, TypeError):
                    # Torn write from a crash: skip the line, keep the rest of the journal readable.
                    warnings.warn(f"{self.path}:{lineno}: skipping malformed journal line")
        return entries

    def for_task(self, task_id: str) -> list[JournalEntry]:
        return [e for e in self.read() if e.task_id == task_id]


def derive_task_state(entries: list[JournalEntry], task_id: str) -> str | None:
    """Latest state recorded in state_change entries; None if never journaled."""
    state = None
    for e in sorted(entries, key=lambda e: (e.timestamp, e.id)):
        if e.task_id == task_id and e.action == "state_change":
            state = e.summary.rsplit("-> ", 1)[-1].strip()
    return state


def state_change_summary(old: str, new: str) -> str:
    return f"{old} -> {new}"
