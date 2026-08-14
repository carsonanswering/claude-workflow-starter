# Worked traces

Three renderings of the pinned trace format from [SKILL.md](SKILL.md) — the kill case, the child-branch nesting case, and the pop-then-discharge case.

Kill, then the next candidate at the same branch point goes live:

```
⚡ trace
B0 401s on /api/upload since Tuesday's deploy
├─ P1 JWT clock skew              ✗ dead: token exp 2026-08-01, 3 days out
├─ P2 proxy strips Authorization  ◀ LIVE  probe: curl direct vs through nginx — kill if header present both ways
└─ P3 new RBAC middleware order   queued
```

Validation opens a child branch point and the trace nests:

```
⚡ trace
B0 recall dropped 0.94 → 0.61 overnight
├─ P1 embedder swapped         ✗ dead: EMBEDDING_PROVIDER unchanged in env
├─ P2 index lost rows          ✗ dead: row count matches baseline
└─ P3 gate threshold moved     ✓ validated → B1
   B1 which change moved the gate?
   ├─ P3a config default edit   ✗ dead: default still 0.60
   └─ P3b per-embedder profile  ◀ LIVE  probe: git log -1 on the profile file — kill if untouched this week
```

Every candidate at the child branch point is dead, so pop to the parent, take its next candidate, and discharge when it validates:

```
⚡ trace
B0 nightly job silently produces zero rows
├─ P1 upstream data empty       ✗ dead: source table has 40k rows for that date
├─ P2 query filter bug          ✗ dead: B1 EXHAUSTED — every filter candidate dead
│  B1 which filter drops the rows?
│  ├─ P2a date-range off-by-one ✗ dead: same SQL returns rows in psql
│  └─ P2b tenant filter         ✗ dead: tenant_id present in params
└─ P3 writer swallows an error  ◀ LIVE  probe: grep -n "except" in the writer module

⚡ DISCHARGE P3 — bare except at writer.py:212 swallowing IntegrityError. Fixing now; no further hypothesis probing.
```

Over the ~12-line cap, that third trace collapses to the `P2` line alone: the `B1` subtree drops and its inherited verdict stays, because a popped frame is never re-entered.
