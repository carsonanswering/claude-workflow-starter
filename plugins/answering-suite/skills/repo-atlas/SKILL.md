---
name: repo-atlas
description: Regenerates the Obsidian atlas of the projs monorepo (Atlas.md hub, per-project notes, domain MOCs, Bases table, JSON Canvas, graph colorGroups) and classifies any new top-level dirs. Use when the user says "/repo-atlas", "regenerate the atlas", "update the monorepo map", "the atlas is stale", or right after a top-level directory is added to, renamed in, or removed from /home/schmi/projs.
---

# Repo atlas

`/home/schmi/projs` **is** an Obsidian vault (`.obsidian/` sits at its root). The atlas is the
generated map of that vault: it turns every top-level project dir into a linked note so the
monorepo is navigable in Obsidian instead of only in the shell.

## What the generator owns

Everything under `atlas/` **except** `atlas/gen/` is rewritten from scratch on every run:

| Path | What it is |
|---|---|
| `atlas/Atlas.md` | home note / hub — needs-attention list, domains, all-projects table |
| `atlas/projects/<dirname>.md` | one note per top-level dir; frontmatter carries type, domain, status, git state |
| `atlas/domains/<slug>.md` | Maps of Content, one per domain |
| `atlas/Atlas.base` | Obsidian Bases table + cards views |
| `atlas/Atlas.canvas` | JSON Canvas map |
| `.obsidian/graph.json` | colorGroups merged in non-destructively; backup at `graph.json.atlas-backup` |

Full contract: `/home/schmi/projs/atlas/gen/SPEC.md`. Read it only when behavior contradicts this
runbook.

## Run it

```bash
cd /home/schmi/projs/atlas/gen && .venv/bin/python -m atlas_gen
```

Run `--dry-run` first (prints planned writes and deletes, writes nothing) when the user is
unsure what will change, when a top-level dir was just deleted or renamed, or when they ask
what the atlas *would* do. Otherwise go straight to the real run — the generator is
idempotent and re-runnable, so a plain run is the cheap path.

Other flags: `--skip-graph-json` (leave `.obsidian/graph.json` alone), `--root PATH`,
`--json-out PATH`.

**Done when** stdout contains exactly one line matching

```
atlas: <N> projects, <M> domains, <K> files written, <D> stale removed
```

and the exit code is 0. Report that line back verbatim — it is the whole result. A same-day
re-run legitimately reports `0 files written`, because byte-identical files are skipped to keep
Obsidian sync quiet; that is success, not a no-op failure.

## Handle Unclassified

New top-level dirs land in `atlas/Atlas.md` under `## Unclassified` until they are added to
`/home/schmi/projs/atlas/gen/atlas_config.json`. That file is the only curated input — classify
there, never by editing a generated note.

When the summary line lands, check whether the run reported unclassified dirs. If so, tell the
user which dirs are unclassified and offer to classify them. On a yes, add one entry per dir
under the top-level `projects` object, keyed by the directory name verbatim:

```json
"answering-brief": {
  "display_name": "Answering Brief",
  "type": "tool",
  "domain": "Answering",
  "purpose": "One sentence, present tense, describing what this repo is for.",
  "relations": [{ "kind": "feeds", "target": "answering-raise" }],
  "key_files": ["README.md"]
}
```

Reuse an existing `domain` name from the top-level `domains` array and an existing `type` and
relation `kind` from neighbouring entries rather than coining new vocabulary — consistent values
are what make the Bases views and canvas groups usable. `relations[].target` must be another
top-level dir name; targets that do not resolve are dropped with a stderr warning. Add
`"status_override": "archived"` only when the user says the project is done. Then regenerate
once and confirm `## Unclassified` is gone from `atlas/Atlas.md`.

## Manual edits

Hand-written content survives regeneration **only** between these markers inside a generated
note:

```
<!-- MANUAL:START -->
your notes here
<!-- MANUAL:END -->
```

Everything outside the markers is overwritten every run. If the user wants durable prose on a
project note, put it inside the block and say so.

## When it fails

On a traceback or nonzero exit, stop and diagnose — do not re-run the same command hoping for a
different result. Run the suite:

```bash
cd /home/schmi/projs/atlas/gen && .venv/bin/python -m pytest tests -q
```

Report which tests fail alongside the traceback, and let the user decide whether to fix the
generator. Two failures have known causes worth checking first: `ModuleNotFoundError: No module
named atlas_gen` means the command ran from the wrong directory (it must run from
`atlas/gen/`), and a complaint about a missing `.obsidian/graph.json` means the vault config is
absent — the generator deliberately refuses to create one, because Obsidian owns that file, so
open the vault in Obsidian once or re-run with `--skip-graph-json`.

## Stop and ask the human before

- restoring or deleting `.obsidian/graph.json.atlas-backup`, or hand-editing `graph.json`
- deleting any note under `atlas/` yourself — the generator sweeps its own stale notes and
  deliberately leaves files that lack a `generated: true` line, so a leftover file is a signal
  someone wrote it by hand
- committing or pushing the regenerated atlas
- running with `--root` pointed anywhere other than `/home/schmi/projs`

## Reporting

<example>
Ran clean, nothing new:
`atlas: 24 projects, 8 domains, 0 files written, 0 stale removed` — atlas is current, no changes needed.
</example>

<example>
Regenerated after a dir was removed:
`atlas: 23 projects, 8 domains, 4 files written, 1 stale removed` — dropped the note for `old-spike`; Atlas.md and its domain MOC updated.
</example>

<example>
Unclassified found:
`atlas: 25 projects, 9 domains, 6 files written, 0 stale removed` — `foo-lab` is unclassified and showing under "## Unclassified" in Atlas.md. Want me to add it to atlas_config.json? I'd file it as type `tool` under the Agent Infra & Skills domain.
</example>

<example>
Failed:
Generator raised `KeyError: 'domain'` in render_md.py. Test suite: 41 passed, 2 failed — test_render_md.py::test_domain_omitted and test_e2e.py::test_summary_line. The atlas was not modified. Fix the generator before re-running?
</example>

Before finishing, verify: the summary line was actually printed (not assumed), the counts are
quoted verbatim, and any Unclassified dirs were named rather than glossed as "some new dirs".
