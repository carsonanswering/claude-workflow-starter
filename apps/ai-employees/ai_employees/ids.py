"""ULID generation (stdlib-only, spec-compatible: 48-bit ms timestamp + 80 random bits).
Monotonic within a process so IDs always sort chronologically."""

import os
import threading
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_lock = threading.Lock()
_last = 0


def new_ulid() -> str:
    global _last
    with _lock:
        value = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10))
        if value <= _last:
            value = _last + 1
        _last = value
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))
