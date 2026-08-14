"""In-memory task queue: priority ascending (0 = urgent), FIFO within priority."""

import itertools

from .models import Task


class TaskQueue:
    def __init__(self) -> None:
        self._items: list[tuple[int, int, Task]] = []
        self._counter = itertools.count()

    def push(self, task: Task) -> None:
        self._items.append((task.priority, next(self._counter), task))
        self._items.sort(key=lambda t: (t[0], t[1]))

    def pop(self) -> Task | None:
        if not self._items:
            return None
        return self._items.pop(0)[2]

    def peek(self) -> Task | None:
        return self._items[0][2] if self._items else None

    def __len__(self) -> int:
        return len(self._items)
