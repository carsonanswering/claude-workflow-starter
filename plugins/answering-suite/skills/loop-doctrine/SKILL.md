---
name: loop-doctrine
description: Operating doctrine for autonomous loop sessions. Use at the start of any /loop run, overnight agent fleet, or long autonomous session, and when the user says "loop doctrine" or "run the loop".
---

> Evidence base: `~/projs/loop-studies/04-loop-doctrine-v2.md` and
> `08-night-summary.md` (2026-07-19 experiment night, 12 experiments).
> Tools ship in `tools/` beside this file. Rules cite the experiment that
> validated them; a rule with no citation is doctrine, not measurement.

# Loop Doctrine

You are running an autonomous loop session. Every tick is one OODA cycle
(invoke the `ooda` skill at loop start). Explicit user "stop loop" is the only
terminator; directive changes mid-session are re-Orient events, never restarts.

## 1. Wake and change-gate

- Pace by events: background-job completions are the primary wake signal;
  `ScheduleWakeup` (60–3600s clamp) is the idle fallback; `CronCreate` for fixed
  cadence. Never busy-poll.
- Before any rescan, run the change gate — no change means no-op tick:

  ```sh
  ~/.claude/skills/loop-doctrine/tools/loop-fp.sh --gate --ledger <ledger.json> <repo>...
  ```

  Exit 0 = at least one repo changed (run discovery); exit 20 = all unchanged
  (skip the tick, do not rescan); exit 2 = a path is not a git repo (re-Orient,
  never guess). Add `--no-update` to peek without storing; omit `--gate` to just
  print fingerprints. Hashes live per-repo in the ledger's `fingerprints` field.
- Fingerprint = sha256 of `git for-each-ref` + `git stash list` + `git status
  --porcelain`. Do NOT substitute `rev-parse HEAD` or dir-mtime — EXP-01 measured
  6/6 change classes caught vs 0/6 and 1/6, zero false positives, ~0.04s/repo.
  The caveats (what trips the fingerprint, what it cannot see, what it costs)
  live in one place: `loop-fp.sh --help` prints them. Read it before re-timing on
  a large repo, or when a gate verdict surprises you.

## 2. Ledger discipline

- One ledger per session: `~/.claude/skills/loop-doctrine/tools/ledger.py` (flock + atomic
  replace; SIGKILL-safe). The session-scratchpad copy is authoritative — it is
  the only file the flock protects, so every verb runs against that path.
- For repo-bound work, mirror it to repo-local `.claude/loop-state.json` by
  copying the scratchpad file after the tick's last ledger write. The mirror is
  a read-only snapshot for whoever inspects the repo; on divergence the
  scratchpad copy overwrites the mirror, never the reverse.
- Claim before act: `ledger.py claim <task-id>` — exit 3 means another
  claimer won; drop the task, do not race it.
- Record every failure with exact params: `ledger.py record-failure`. Before
  any Act, `ledger.py check --action --params` — exit 4 means an identical
  failed action is on record; never retry unchanged (this is an exit code, not
  an aspiration). Failed-action refusal outranks all other verdicts.
- On shutdown, flush open/blocked ledger items into the session handoff note.

## 3. Result ingestion — parse ladder

- All worker/workflow results go through `~/.claude/skills/loop-doctrine/tools/ingest.py`:
  raw `json.loads` → `html.unescape` retry ONLY after raw failure → last-valid
  journal `.jsonl` line → exit 2. Never unescape preemptively (corrupts valid
  payloads containing literal entities). Exit 2 = re-Orient; never eyeball a
  truncated blob. Parsed results are Observations, not Decisions.

## 4. Isolation

- Concurrent same-repo work requires hand-rolled pinned worktrees — the
  certified path (EXP-12, zero cross-contamination under real concurrency):
  dispatcher runs `git -C <repo> worktree add .claude/worktrees/<task>
  -b loop/<task> <pinned-sha>` BEFORE launch, then `git worktree list` to
  confirm no path collisions.
- Isolation needs BOTH own-worktree confinement AND explicit commit pathspecs:
  `git commit -- <declared files>`. Never `git add -A`.
- Workflow `isolation: 'worktree'` flag caveats: it ERRORS LOUDLY outside a git
  repo (agents never run; in-script it shows only as null `agent()` results —
  check the failures channel), and the inside-repo positive case is untested
  (PROVISIONAL). Precondition-probe `git rev-parse --git-dir` from the dispatch
  cwd; on failure, hand-roll worktrees or abort. Never rely on the flag alone.
- Every worktree created is registered the same iteration as a human-gated
  cleanup item: `ledger.py claim cleanup-worktree:<task>`, then
  `ledger.py block cleanup-worktree:<task> --reason "<path> on loop/<task>"`.
  Claim first — `block` exits 5 on a task id the ledger has never seen. Those
  entries ride the session-end cleanup list (§7); deletion is human-gated, so
  the human runs `git worktree remove`.

## 5. Verification — tier by oracle coverage, not stakes

- Never accept self-reported success.
- Tier A (deterministic oracle sees the claim's substance — greps, tsc, test
  suite): independently re-run the claim's *stated* check in a clean worktree,
  then stop. Verify content/behavior, never activity ("diff touched the file"
  false-accepts).
- Tier B (logic changes with test coverage): A + replay real recorded inputs.
- Tier C (new metrics, scoring/judging, silent-corruption risk): A + B + a
  live/adversarial stage. Record which tier the claim survived; report CIs,
  not magic sample thresholds.
- Any claim the deterministic oracle cannot see escalates a tier regardless.
- Fresh-context reviewer APPROVE before every merge; diff-only review certifies
  internal consistency only — cross-file "mirrors/matches" claims or duplicated
  gate constants force escalation with the referenced files. Merges serialized,
  tests between each; batch backstop (`tsc` + full suite) in a quiesced or
  dedicated tree. Red main blocks the next iteration.

## 6. fw delegation limits

- Discovery is a probe-loop, not a one-shot classification sweep (EXP-02
  falsified fw queue-rebuild: merged-status is undecidable from piped text).
  Queue rebuild stays with a tool-capable agent; sweeps must include the
  zero-LLM probes `git branch --merged main` and nested-repo `ls */.git`.
- fw drafts labels only for closed-world text where every needed fact is in the
  piped input. Verify before acting — untrusted draft, always.
- JSON extraction pins `fw -m oss` — `-j` on deepseek-v4-pro truncates on large
  context (reasoning exhausts budget). Parse strictly; map unparseable to
  "unknown", never to a verdict.
- fw never edits memory files: frontier extracts claims, targeted git commands
  confirm, only git-confirmed corrections are written.

## 7. Escalation and notification

- PushNotification (interrupt): only loop-stop events and hard blockers —
  budget pause, unrepairable red main, failed-action dead end, or a human gate
  blocking ALL remaining work. Once per event; record `notified_at` in the
  ledger so a persisting blocker never re-pushes.
- Blocked-queue surfacing (non-interrupting): every declined/blocked task gets
  a ledger entry (`blocked-on-carson`/`surfaced`) plus a DO-NOT-EXECUTE pickup
  prompt with a content-keyed `surfaced-items:` marker (sorted item set;
  topic+date markers prohibited). A silent skip is a doctrine violation.
- Session-end handoff (batch): aged surfaced items (>7 days: one line),
  cleanup lists, routine awaiting-you items. Escalation decisions are
  frontier judgment, never fw.

## 8. Budget

- Resolve this session's `<id>` once at loop start and reuse that one value for
  every reading: it is the basename (without `.jsonl`) of the newest file in
  `~/.claude/projects/<cwd-slug>/` — the transcript this session is actively
  writing — from `ls -t ~/.claude/projects/"${PWD//\//-}"/*.jsonl | head -1`.
  Pin it in the scratchpad beside the ledger path. `--all` sums every session in
  that directory, so keep it for manual inspection and out of the loop's reading.
- Every iteration: record the reading, then ask for a verdict.

  ```sh
  ~/.claude/skills/loop-doctrine/tools/spend_reader.py --session <id> --ledger <ledger.json>
  ~/.claude/skills/loop-doctrine/tools/ledger.py --ledger <ledger.json> check --ceiling 200000
  ```

  `spend_reader` dedupes by message.id (naive summing double-counts 2x), reads
  `~/.claude/projects/<cwd-slug>/` by default, and EXITS 6 if that directory is
  missing — a missing log dir must never read as 0 spend (override with
  `--project-dir`). It writes through `ledger.py tick`, which stores the DELTA
  since the previous reading as one iteration in `spend_history`.
- Exit 11 PAUSE — session total reached the absolute `--ceiling`: 200,000
  output tokens, set above the largest session observed here (156,645). Stop
  claiming, finish in-flight verification, queue the rest, notify. Never
  self-terminate; only an explicit user "stop loop" ends the loop.
- Exit 10 DEGRADE — the newest iteration burned at least `--iter-mult`
  (default 3x) the median of THIS loop's own prior iterations. Force new
  fan-out to fw/oss tiers, Sonnet→Haiku. No rate verdict until `--min-history`
  (default 3) prior iterations exist.
- Judge rate against this loop's own history, never a global median.
- The two gates cover each other's blind spot deliberately: the rate check goes
  blind to a *sustained* elevated burn (its own median drifts up to meet it),
  and the absolute ceiling catches exactly that case. Do not drop one because
  the other exists.
- `--baseline` is DEPRECATED and warns on stderr: it compares the session TOTAL
  against a per-iteration norm, so a long cheap loop trips it on duration
  rather than waste.
