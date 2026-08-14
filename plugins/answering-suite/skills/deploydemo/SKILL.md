---
name: deploydemo
description: Stand up the Answering demo appliance and reconcile docs/handoff/DEMO-PILOT.md against what the box actually does. Use when Carson says "/deploydemo", "deploy the demo", "spin up the demo", "get the demo ready", "is the demo still working", or before a pilot call. Accepts an optional argument, e.g. "/deploydemo preflight" (blockers only, change nothing) or "/deploydemo --fresh" (destroy the demo workspace corpus and reseed) or "/deploydemo --teardown" (remove the workspace).
argument-hint: "(optional) preflight | --fresh | --teardown"
---

# deploydemo

Get the Answering demo appliance running, prove every beat in the guide still
works, patch the guide where reality has moved, and hand back the short list of
things only a human can do.

Repo: `~/Desktop/projs/answering`. Guide: `docs/handoff/DEMO-PILOT.md`. Everything you run
lives under `deploy/appliance/`.

## The one rule

**The guide is a transcript, not a description.** Its entire value is that every
output in it was observed on a real box. So when the guide and the running
system disagree, the system is right and the guide gets edited — never the
reverse, and never by writing what you expect the output to be.

If a beat fails, say so in the guide. A demo guide that quietly drops a broken
beat is worse than one that says "beat 3 returned no suppressed row on
2026-08-14, do not run it" — the second one saves the call, the first one loses
it.

## Run it

```bash
cd ~/Desktop/projs/answering/deploy/appliance
./demo/verify.sh              # preflight, build, seed, run all six beats
./demo/verify.sh --preflight  # blockers only, changes nothing
./demo/verify.sh --fresh      # destroy this workspace's corpus, then rebuild
./demo/verify.sh --teardown   # remove the workspace entirely, run nothing
```

**The demo builds its own throwaway workspace.** It runs as the compose project
`answering-demo` with its own network, its own `answering-demo_pgdata` volume, and its
own corpus under `demo/workspace/drop` — all created on demand, all git-ignored.
Nothing you do here can reach a pilot deployment or another project on the same
machine, and `--teardown` removes only this one.

That isolation is the reason `--fresh` and `--teardown` are safe to offer at
all. Before it existed the demo shared the `answering` project and volume with any
real deployment from the same compose file, so a demo reset would have destroyed
a pilot's corpus. Override the name with `ANSWERING_DEMO_PROJECT` if you ever need
two demo boxes side by side.

`verify.sh` is the source of truth, not this file. It prints each beat between
`<<<BEAT:n>>>` / `<<<END:n>>>` markers so you can lift the blocks verbatim.

Exit codes: `0` all beats ran and the structural checks held · `1` a blocker,
nothing was demoed · `2` it ran but something drifted (look for `DRIFT:` lines).

Argument handling:

- `preflight` — run with `--preflight`, report blockers, stop. Change nothing,
  edit nothing.
- `--fresh` — destroys the demo workspace's corpus first, then rebuilds. Scoped
  to `answering-demo`, so it cannot touch anything else — but still only when
  asked. Never destroy on a bare invocation.
- `--teardown` — remove the workspace and stop. Use after a demo, or when the
  box is being handed to someone else.
- no argument — full run. Creates the workspace if it does not exist.

## What to do with each exit code

### Exit 1 — blocked

Stop. Do not build, do not edit the guide. Print the blocker and the single
command that clears it. Blockers are always the human's: Docker not running, a
missing `.env`, an empty secret, no model credential.

### Exit 0 — clean

1. Read `docs/handoff/DEMO-PILOT.md`.
2. For each `<<<BEAT:n>>>` block, compare the observed output with the quoted
   output in that beat. Where they differ **in substance**, replace the quoted
   text with what was observed.
3. Update the `*Last verified …*` line to today's date and the current commit
   (`git rev-parse --short HEAD`).
4. Report what you changed, in one line per beat.

Do **not** rewrite a beat because the wording of a generated answer shifted
slightly — the model is not deterministic and churning the doc every run makes
the diff worthless. Rewrite when the *substance* moved: a different set of
sources, a different governance outcome, a person who now sees something they
did not, a number that is no longer close.

### Exit 2 — drifted

Something structural moved. Read the `DRIFT:` lines, then work out **why**
before touching the doc — drift is usually a real regression, and editing the
guide to match a regression is how a broken product gets a passing demo.

Most common causes, in order:

- **reach line changed** — a roster stopped matching a bound name. Governance
  problem, not a doc problem. Check `demo/seed.sh` bound `--transcript-name`
  values against the `attendees` on the documents.
- **no `suppressed` row** — beat 3 has nothing to point at. Either Sam gained a
  room, or audit writes are being lost again.
- **a beat's outcome flipped** — someone now sees something they did not.
  That is a leak until proven otherwise. Do not update the doc; report it and
  stop.

## Then: serve the manual steps

Always end by printing the short list of things the human has to do. Split it
in two, because they have different deadlines.

**Before the demo can run at all** — only the items that are actually
outstanding, checked rather than recited:

- Docker Desktop running.
- Secrets. These are no longer hand-pasted: `.env` is generated from the
  committed, encrypted `secrets.env`, and `verify.sh` decrypts it automatically
  when missing. The human part is only the **age key** — it must exist at
  `~/.config/sops/age/keys.txt`, restored from the team password manager
  (docs/handoff/SECRETS.md). `./demo/secrets.sh check` reports the state without
  decrypting anything.
- `FIREWORKS_API_KEY` — and check it is the rotated one (tracker #36). A key
  exported in the shell silently **overrides** `.env`, which is how the leaked
  key travelled; `verify.sh` now flags it as drift. The fix is to remove it from
  the shell profile and open a new terminal, not to work around it.

**On the day, in front of the prospect:**

- Run beat 1 once yourself first — the first generation call is the slowest and
  the pause reads as a hang.
- Have the principal ids ready if you plan to run beat 5 (the verifier prints
  them).
- Decide up front whether you are running five beats or six. Beat 5 lands with
  engineers, not with a CFO.
- Say the boundaries unprompted: Slack ingest is built but has never touched a
  real workspace, the model plane is hosted today, four documents is not a
  corpus. The guide's "Do not demo" section is the list.

Anything the run already proved is done, drop from the list. A checklist that
recites satisfied items trains people to skip it.

## Keeping the guide honest over time

Two things go stale on their own and are worth checking every run even when
nothing failed:

- **The "Do not demo" list.** Something on it may have shipped since. Cross-check
  against the repo rather than trusting the list: if a connector now exists, it
  moves out of "not built" — but only as far as "built, never run against a real
  workspace" until someone has actually run it. Those are different claims and
  the guide must not blur them.
- **Tracker references.** If the guide cites an issue that has since closed,
  update the sentence rather than deleting it; the reason it was worth saying
  usually survives the ticket.

## Boundaries

- Never commit `deploy/appliance/.env`, and never print a secret's value —
  length only. `secrets.env` is the encrypted one and IS committed.
- Never `docker compose down -v` unless `--fresh` was passed.
- The demo corpus under `demo/corpus/` is synthetic and safe to commit. Anything
  in `drop/` may be real and is git-ignored; leave it alone.
- Commit guide edits with a message that says what moved and why. Do not push
  unless asked.
