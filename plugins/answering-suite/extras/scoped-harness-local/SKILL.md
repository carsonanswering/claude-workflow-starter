---
name: scoped-harness-local
description: Build a scoped harness — one-responsibility role, hard tool allowlist, rigid output contract with a required `STATUS: OK|ESCALATE` field, pre-loaded context — and run it on a LOCAL Ollama model through `pi` (default `qwen3.6:35b-mlx`). Zero marginal cost and nothing leaves the machine; one GPU means the fan-out is a serial queue, never parallel agents. Use `local-delegate` (`lo`) instead when the work is one transform over text you already hold and needs no tools; use `pi-delegate` when a roster agent (scout, grunt, bulk, tester, reviewer, planner, worker) already covers it; use `scoped-harness-fw` when the fan-out must run wide or land fast. Trigger phrases "scoped harness on ollama", "local scoped harness", "run the harness on my GPU", "harness that stays on this machine", "offline agent with tools", "zero-cost agent with tools", "zero-cost serial queue", "harness on qwen3.6". A bare "build a scoped harness" with no locality or cost signal defaults to `scoped-harness-fw`.
---

# scoped-harness-local — build the harness, then run it on your own GPU

Opus 5 orchestrates; a local Ollama model does the legwork inside a harness you write for it. A weak model fails on *unbounded* choice, not on bounded execution: give it one responsibility, the smallest tool allowlist that can succeed, the context already pasted in, a rigid output shape, and a legal way to say "I don't know".

**Be exact about what that buys, because it was measured.** On one well-posed question — find the seeded defect in an 11-line Python file — a bare `pi -p` on the same model with **no** harness, **no** strip flags and **no** contract found the defect correctly in 5s, in fluent prose, with a diagnosis at least as good as the harnessed run's. The harness was marginally slower. On accuracy it was a tie. What the harness demonstrably bought instead: output a script can parse and aggregate across a fan-out, a scope the model cannot wander out of or edit past, a refusal path, and provenance via the nonce. So: for a single question you will read yourself, the harness is overhead and a bare call is the right move. The harness earns its keep the moment output must be parsed, aggregated, trusted unread, or fanned out. It is quality-control machinery, not a capability upgrade — and every part of it still has to be checked, because a harnessed 35B returns confidently formatted wrong coordinates (see "Resolve every coordinate yourself") and the refusal path it buys will sometimes be taken on a file that did have an answer (step 8).

This skill is how you build one harness for the task in front of you. `pi-delegate` is the operator manual for the existing Fireworks roster — read it for `pi-spawn` flags, prompt templates, chains, and the seven stock agents rather than re-deriving them here.

## Read this before running anything

**Every Bash call that runs `pi` or `tmux` needs `dangerouslyDisableSandbox: true`.** `pi` writes lockfiles under `~/.pi/agent/`; the sandbox denies it and the first command dies with:

```
EPERM: operation not permitted, mkdir '/Users/kai/.pi/agent/settings.json.lock'
```

That names a lockfile, not a sandbox, so it reads like a broken install. It isn't. `ollama`, `curl` and `jq` calls need no flag.

**Close stdin on every dispatch: append `< /dev/null`.** `pi -p` does not exit while stdin is an open pipe, and every Bash tool call hands it one. Measured, same command, same warm model, same file: **without** a redirect it stalled past 600s and was killed with a **0-byte** output file — reproduced three separate times; **with** `< /dev/null` appended it returned complete, contract-compliant output in **16s**. The fault reproduced independently on the Fireworks sibling substrate, where a `--mode json` run hung at 10 minutes, then again at 3 minutes, both times producing 0 bytes, and then exited rc=0 in 5s with 1.6MB once `< /dev/null` was added. Every run that completed in either substrate had stdin detached (backgrounded through `nohup`, or redirected); every stall was a foreground call without a redirect. One token, no cost when unnecessary, and the difference between a 16s answer and a spent cap — so it goes on every dispatch in this file, including the `--mode json` form and the queue loop.

**One caller at a time. This is the defining constraint of the local substrate.** Ollama serves a single GPU. Concurrent callers contend, and a second model loading mid-run evicts the first — measured on one-shot `lo` calls (`local-delegate` rule 6), a cold load that normally costs 7–9s took over 300s under contention; a harness run adds tool round trips on top of that. Fan-out here is a **serial queue through one lane**, never parallel agents. A wide or urgent fan-out belongs on `scoped-harness-fw`.

**Preflight, four probes** (the first needs `dangerouslyDisableSandbox: true`):

```bash
pi --list-models | grep ollama                 # pi's wiring — this only reads models.json
ollama list                                    # the tags actually pulled; models.json can name one that is not
ollama ps                                      # residency, the served CONTEXT, and the UNTIL eviction clock
curl -s localhost:11434/api/tags | head -c 200 # server alive (or: lo --check)
```

If `pi --list-models` shows no ollama entries, the provider block is missing. `~/.pi/agent/models.json` is the whole wiring — `apiKey` must be non-empty (Ollama ignores the value, but pi hides models without one) and both `compat` flags must be `false`, because Ollama's OpenAI-compatible endpoint understands neither the `developer` role nor reasoning-effort. **The file declares all three models; the block below is abridged to one — restore all three or step 2's fallbacks disappear:**

```json
{ "providers": { "ollama": {
  "name": "Ollama (local)", "baseUrl": "http://localhost:11434/v1",
  "api": "openai-completions", "apiKey": "ollama",
  "compat": { "supportsDeveloperRole": false, "supportsReasoningEffort": false },
  "models": [
    { "id": "qwen3.6:35b-mlx", "name": "Qwen3.6 35B A3B (local)", "contextWindow": 65536, "maxTokens": 8192,
      "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 } }
    /* plus gemma4:31b-mlx and gemma4:latest, contextWindow 32768, maxTokens 4096, same zero costs —
       see ~/.pi/agent/models.json for the full file */
  ] } } }
```

Provider reference: `/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/docs/models.md` and `docs/providers.md`. models.json is enough — no extension needed.

**Budget the context the server actually serves, not the one pi declares, and read it every session.** pi sends no `num_ctx` (zero occurrences in its `dist/`), so Ollama serves its own configured window and pi's declared number only drives pi's token accounting. Measured on this machine: `ollama ps` reported `CONTEXT 8192` on one load and `16384` on another for `qwen3.6:35b-mlx`, while models.json declared 65536 and `ollama show` reports a native ceiling of 262144. The served number is **not stable across loads — read it, do not memorise it.** Over-length input is dropped by the server with no error on either side, **from the front** (`local-delegate`, exit 7), so the harness itself is what disappears and the model answers fluently from a fragment. Size every paste against the `ollama ps` CONTEXT column of the load you are about to use, or raise `OLLAMA_CONTEXT_LENGTH` and re-read it.

**Budget the RAM.** `qwen3.6:35b-mlx` is 21GB on disk; resident it measured 21–22GB across this session's loads and 27GB at `lo`'s default `--ctx` (`local-delegate` rule 7) on this 48GB machine. pi sends no `keep_alive` either, so a pi-driven load holds for Ollama's own default rather than the 15m you get from `lo` (that 15m is `lo`'s argparse default, `/Users/kai/.local/bin/lo:169`). Read the `UNTIL` column in `ollama ps` before switching models mid-queue; two co-resident models make the third load thrash.

**Budget the clock, and know the ceiling.** One harness call: Bash `timeout` 180000 ms — generous on purpose, because warm harnessed calls with stdin closed measured **6s, 7s, 16s and 16s**. **The Bash tool's own maximum is 600000 ms**, and it was hit twice in one measured session — both times by calls stalled on an open stdin, never by slow inference. Close stdin and that ceiling stops being a live risk on single-file work. A serial queue of more than ~3 items still cannot fit in one foreground call at the 180s per-item cap: run the queue with `run_in_background: true`, give every item its own cap, and poll the per-item output files. **Always redirect a dispatch to a file** (`> "$OUT/out-<slug>.txt"`): when a call does blow the budget the tool kills it and unredirected output is lost entirely — no partial answer, no diagnosis.

**Privacy is the premise, so make it structural.** Add `--offline` (or `PI_OFFLINE=1`) to the dispatch to disable pi's startup network operations; the model call itself already goes to `localhost:11434`.

## Route first

| The work | Where it goes |
|---|---|
| Decomposition, synthesis, resolving two workers that disagree, anything whose wrong answer is expensive or hard to detect | Inline, Opus 5. Never delegate the split or the merge. |
| Finishes in a handful of tool calls — one grep, one line-ranged read, one command | Inline. Harness overhead exceeds the work. |
| One well-posed question whose answer you will read yourself | Bare `pi -p --provider ollama --model qwen3.6:35b-mlx --offline "<question>" < /dev/null`. Measured a tie on accuracy with the full harness and marginally faster; the contract buys nothing you are not going to parse. |
| One transform over text you already hold, no tools needed | `lo` (skill `local-delegate`) or `fw` (skill `fw-delegate`). Below the harness floor — a harness buys tool access and nothing else. |
| A roster agent already covers it (scout, grunt, bulk, tester, reviewer, planner, worker) | `pi-delegate`. Drive the roster; do not rebuild it. |
| Needs real tools (read/grep/bash/edit), bounded, and the output will be parsed, aggregated, trusted unread or fanned out | **This skill.** |
| Same shape, but the fan-out must run wide, or `N × per-call seconds` served serially will not fit the deadline, or the model must be stronger than 35B, or the coordinates it returns must be right first time | `scoped-harness-fw`. Read the two notes below before assuming local will do. |
| Needs Claude-quality reasoning *with* tools, or writes into a shared checkout under fleet guardrails | A Claude subagent; `team-orchestration` decides which. |

**Wide-or-fast is arithmetic here, and the arithmetic is honest again.** Concurrency is 1, so wall clock is at least N × per-call seconds and nothing overlaps. Measured warm with stdin closed: a harnessed call 6–16s (6s and 7s on bug-bearing files, 16s on the clean file that escalates), a bare unharnessed call 5s. Ten files is minutes, not seconds. **An earlier version of this section reported that the identical command sometimes returned in 7s and sometimes hung past 8 minutes, and concluded that local latency had no usable mean. That diagnosis was wrong.** The stalls were `pi -p` blocking on the Bash tool's open stdin pipe, not model variance; `< /dev/null` on the dispatch removes them (see "Read this before running anything"), and sizing a queue by multiplication works. What does not scale is concurrency, and no arithmetic fixes that.

So, mechanically: **keep the queue serial, and never run it as a foreground loop.** Dispatch each item in the background with its own output file, poll, and enforce a per-item cap — a stalled item is a *failed* item, not one to wait on, which is what stops a single pathological item from eating the whole queue's budget. When the fan-out must run wide, or N × per-call seconds does not fit the time you have, route to `scoped-harness-fw`; one GPU cannot be made parallel.

**Coordinates are a real substrate difference, and it was measured on both.** The same corpus was run through the Fireworks sibling on `gpt-oss-120b`, which returned the **correct line number on every defect it found** (4 of 5). The local 35B scored **0 for coordinates** on every file it diagnosed correctly. The local model gets the reasoning right and the arithmetic wrong, so its returns always need the `grep -n` re-derivation below; the hosted model's numbers held. Route coordinate-sensitive work — a patch applied by line, anything a script consumes as an index — to `scoped-harness-fw`, alongside the wide-and-fast reasons.

Two falsifiable gates before you build anything. **Name the observation that would prove the returned answer wrong** — if you cannot, you have no acceptance check and the harness will return confident fiction. **Fit harness plus paste inside the served window** — the `ollama ps` CONTEXT number, not models.json's 65536 (qwen3.6) or 32768 (either gemma4). If the excerpt will not fit, split the task rather than expecting the model to search.

## Build the harness

Eleven steps. Each produces a line of the harness file or a flag on the command.

1. **Name the single responsibility in one sentence.** "Find the one arithmetic bug in the Python file named in the task and report its location." If the sentence needs an "and", it is two harnesses — build the second one after the first returns.

2. **Choose the model for the task class.** Three installed, all zero marginal cost:

   | model | shape | reach for it when |
   |---|---|---|
   | `qwen3.6:35b-mlx` | 35B-A3B MoE, ~3B active, 21GB on disk, ~125 tok/s warm, 7–9s cold, 65536 declared ctx | **Default.** The only one that should get tool-using work by default. |
   | `gemma4:latest` | 9.6GB on disk, smallest resident footprint, 32768 declared ctx | RAM is tight or a cold start dominates a very short call. |
   | `gemma4:31b-mlx` | 18GB dense, roughly a third of qwen's speed, 32768 declared ctx | Dense fallback when qwen's MoE output is visibly thin on one task class. |

   Declared ctx is pi's accounting figure; the served figure is `ollama ps`. Halving the window by taking a gemma fallback halves the paste you can afford.

3. **Derive the tool allowlist from the responsibility** — the smallest set that can succeed, read-only unless the job is to edit. Built-in names, exhaustive: `read`, `bash`, `edit`, `write`, `grep`, `find`, `ls` (`grep`/`find`/`ls` are OFF by default and only exist if you list them). `--tools` is an allowlist over **built-in, extension and custom tools alike**, so a registered extension tool is a legal name here — `subagent` is one, and a harness that must delegate has to list it explicitly. A name that matches no registered tool is silently not forwarded, so a typo leaves the model improvising without the capability. A bug-finder gets `--tools read`. In an *agent file*, always write the `tools:` line: omitting it grants everything including `subagent` itself, and there is no depth guard anywhere.

4. **Pre-load the context instead of making the model discover it.** A child process has EMPTY context — "fix the bug we discussed" means nothing. Hand it absolute paths, exact symbol names, the real question, and the relevant excerpt pasted in. Measured: qwen assembled a path from the wrong base directory, got `ENOENT: no such file or directory`, and self-corrected on the second call — one wasted round trip that an absolute path prevents.

5. **Write the output contract** — fixed keys, one per line (or a JSON object), plus "output nothing else, no prose, no preamble". Machine-checkable is the point; you will grep this. **The key order below was bought with two measured failures — keep it:**

   ```
   NONCE: <the literal token you put in the harness>
   STATUS: OK | ESCALATE
   REASON: <one line; required when STATUS is ESCALATE, `none` when OK>
   FILE: <absolute path>
   LINE: <integer>
   WRONG: <one line: the exact source line, quoted, and what it does>
   FIX: <one line, what it should do>
   ```

   **Nonce first, never last.** Measured: a run whose output was otherwise perfectly contract-shaped — right diagnosis, right `FIX:`, four of five keys — simply dropped the final `NONCE:` line. A weak model drops the tail, so put the provenance token where truncation cannot reach it. **`STATUS:` second, ahead of every field that only makes sense once an answer exists** — step 8 is why. **`WRONG:` quotes the accused source line verbatim**, because that quote and not the integer is what the line number gets re-derived from — step 6 is why.

6. **Make every coordinate carry a verbatim quote of the thing it points at, and resolve the coordinate yourself.** This is the highest-value line in the contract, and it generalises well past line numbers: treat any index a weak model returns — line number, byte offset, array position, match count — as noise, and the quoted string as ground truth. Five measured coordinate returns, **zero correct**: `auth.py` (16 lines, true line 7) drew `LINE: 6` under one contract and `LINE: 9` under the next; `cart.py` (true line 5) drew `LINE: 4` under one contract and `LINE: 6` under the next; and one 11-line file returned `LINE: 14`, a line that does not exist. Every one of those runs quoted the accused source line character for character, and the quote resolved the coordinate in one command:

   ```bash
   $ grep -Fn 'return now - issued_at < SESSION_TTL' auth.py
   7:    return now - issued_at < SESSION_TTL
   ```

   **`-F` is not optional, and leaving it off fails in the direction that costs you the finding.** Source lines are full of regex metacharacters — `*`, `.`, `[`, `(`, `+`, `?`. Measured: the quote `return total * pct / 100` resolved correctly under `grep -Fn` but exited 1 with no output under plain `grep -n`, because `l *` reads as "l repeated". A silent exit 1 looks exactly like "the quoted line is not in this file", so the orchestrator concludes the model fabricated its quote and discards a correct finding. In this corpus every source file carried metacharacters on 5–8 lines.

   So the contract *requires* the quote and the orchestrator does the arithmetic (verify section). A `WRONG:` that only paraphrases leaves nothing to grep and makes an otherwise correct return unusable — the diagnosis is right, and you still cannot say where it is. Write the rule into the harness body in these words: never guess a coordinate; quote the exact text instead.

7. **Give one worked example of each STATUS inside the harness** — an input and the exact expected output for it, including one where the answer does not exist. This is the highest-leverage token spend for a weak model; prose describing the format loses to one instance of it, and a model that has never seen an ESCALATE example will not produce one.

8. **Make the refusal a FIELD of the contract, never an alternative output mode.** The obvious design — "if you cannot tell, reply `ESCALATE: <one line why>` and nothing else" — was dispatched at a deliberately clean file (a correct `clamp`, no bug) and failed in the most dangerous direction. The model did not switch modes. It emitted the full contract and smuggled the escape hatch into a field:

   ```
   FILE: /.../clean.py
   LINE: 1
   WRONG: clamp function appears correct as-written, no obvious bug found.
   FIX: ESCALATE: Cannot identify bug — clamp function correctly constrains value between low high using standard comparison logic.
   NONCE: HARNESS_9f31
   ```

   `grep '^ESCALATE:'` misses that entirely — the token is mid-line, inside `FIX:`. A key-presence compliance check **passes** it, and the orchestrator is handed `LINE: 1` as a genuine finding on a file with no bug. The general rule, and it applies to every harness you write: **an escape hatch that competes with a rigid contract loses, because the model would rather satisfy the format than exit it.** So the exit is `STATUS: ESCALATE` plus a `REASON:` line, both required keys, and the check becomes a parse of a required field instead of "did the whole output change shape". The harness rule reads: never guess; when the answer does not exist, keep this exact format and set `STATUS: ESCALATE`.

   **Re-dispatched at that same clean file, the field-shaped exit was taken cleanly** — no smuggling, no fabricated line:

   ```
   NONCE: HARNESS_9f31
   STATUS: ESCALATE
   REASON: clamp() correctly implements clamping logic; no arithmetic or behavioral bug present
   FILE: /.../clean.py
   LINE: 0
   WRONG: none
   FIX: none
   ```

   **The second effect is the one that pays on a queue, and it is not obvious: the legal exit made the no-answer case dramatically cheaper.** Same file, same model. Under the old contract it blew the 600000 ms Bash ceiling and returned 0 bytes; under the `STATUS:` contract it completed in **16s**. Two causes stack there and both fixes are needed — that 0-byte run also ran without `< /dev/null`, so stdin held it open, *and* a model with no legal way to say "nothing here" keeps hunting for something that is not there. Close stdin and give it a legal exit: a refusal path is then the difference between a spent cap and seven lines.

   **Now the cost, because there is no free version of this: an escalation-friendly contract trades fabrications for misses.** Same model, same file, same task; only the contract changed. `retry.py` carries a genuine seeded defect — after exhausting its attempts it does `return last`, handing back the exception object instead of raising it. The permissive contract **found it**: "after all retries fail, it returns the exception object instead of raising it". The `STATUS:` contract returned `STATUS: ESCALATE`, `REASON: Cannot identify a definitive bug — retry logic, exception handling, and loop structure all appear correct`. A real defect was missed because refusal had been made easy and legitimate. The two failure modes need opposite verification, so choose the contract shape by which one costs you more and plan to pay for the other:

   | The expensive failure | Contract shape | Where you pay |
   |---|---|---|
   | False positives — anything auto-applied, or a fan-out too wide for you to read every return | The `STATUS:` contract above | Misses. Every escalation is an open item to re-run, never a clean result. |
   | Misses — security sweeps, audits, any "find every X" | The permissive contract, no legal exit | Fabrications, caught at verification time where they are visible and cheap. |

   Two rules hold whichever you pick. **`STATUS: ESCALATE` means "unresolved — needs a second look", never "no defect present".** An orchestrator that files escalations as clean results loses real findings with no error anywhere — the same class of mistake as consuming a `LINE:` you never re-derived. And **calibrate before you trust either shape across a fan-out**: one pass over a handful of files whose defects you already know tells you which failure mode you actually have, for the cost of a few 6–7s calls.

9. **Add the forbidden actions explicitly.** Change only what the task names; never edit unless editing is the job; never run destructive commands (`rm`, `git reset --hard`, force push, `DROP`); never widen scope; never ask the user a question — set `STATUS: ESCALATE` instead, because nothing is listening. Anything outward-facing (push, merge, post, delete outside the named lane) is `STATUS: ESCALATE` too, never a self-authorized action.

10. **Strip the ambient context** with `-nc -ns -ne --no-session` — for prompt size and focus, not for a latency win. `-nc` kills AGENTS.md/CLAUDE.md discovery, `-ns` skills, `-ne` extensions; what leaves the prompt is a pile of ambient instructions competing with your harness, which is reason enough on its own. **An earlier 15.4s → 12.2s → 2.7s A/B in this file credited that drop to these flags. It did not reproduce on re-measurement and is best explained as cold-load versus warm — those early runs were the first calls after the model loaded.** Warm and with stdin closed, the honest figure is 6–16s per harnessed call (see the routing section); the multi-minute stalls this file once attributed to the substrate were `pi -p` blocking on an open stdin, not these flags and not the model. Keep the flags; do not budget a speedup from them. Two consequences: `-ne` removes the `subagent` tool, so a harness that must delegate drops `-ne` **and** adds `subagent` to its `--tools` list; and `--thinking off` is inert on this provider — pi's ollama entries declare no thinking support, so nothing is sent and qwen3.6 emits reasoning tokens regardless (one `--mode json` run with the flag set produced 824 `thinking` events). To cut reasoning, put "answer directly, do not deliberate" in the harness body.

11. **Decide the dispatch form.** Inline `pi -p` when you want the result in this turn — the default, and the only form that carries a harness file. An agent file in `~/.pi/agent/agents/` when the harness has earned reuse (see Promotion; there is no `--agent` flag, so it is reachable only via the `subagent` tool from a parent session). Detached `~/.pi/agent/bin/pi-spawn -m ollama/qwen3.6:35b-mlx -n <unique-slug>` only when the work must outlive this session — **and read both warnings first**: omitting `-m` routes the run to `fireworks/gpt-oss-120b` (`pi-spawn:10`), i.e. off this machine, and `pi-spawn` passes only `--model`, `-n` and the task string to pi (`pi-spawn:161-163`), so `--append-system-prompt`, `--tools` and every strip flag are silently dropped. A detached run must therefore fold its rules, contract and `STATUS:` field into the task text itself, and it runs with all tools enabled. Chains and prompt templates: `pi-delegate`.

## A complete worked harness

Write the harness to **one fixed absolute path** and reference that same literal path everywhere. Do not put `$$` in it: the Write tool takes `$$` literally, and every Bash call is a fresh shell with a different PID, so the write and the dispatch land on different files. That failure is silent and total — `--append-system-prompt` reads the file only if it exists and otherwise appends the path **as literal text** (`dist/core/resource-loader.js:19`), so a path slip yields a running, confident, entirely unharnessed worker.

```bash
mkdir -p ~/.pi/agent/harnesses ~/.pi/agent/logs/harness-runs   # once
H=/Users/kai/.pi/agent/harnesses/bugfind.md
OUT=/Users/kai/.pi/agent/logs/harness-runs
```

`$H`:

```markdown
You find bugs. You do not fix them.

Rules:
- Read only the file named in the task. Do not open other files.
- Report exactly one bug: the one that makes the stated behaviour wrong.
- Answer directly; do not deliberate at length.
- In WRONG:, quote the accused source line character for character, then say what it does.
- Never guess a line number. If the file has no such bug, or you cannot tell which line
  is wrong, keep this exact format and set STATUS: ESCALATE with a one-line REASON.
- Never edit, never write, never run a command.

Output format — exactly these seven lines, in this order, nothing else, no prose, no preamble:

NONCE: HARNESS_9f31
STATUS: OK
REASON: none
FILE: <absolute path>
LINE: <integer>
WRONG: <one line: the quoted source line and what it does>
FIX: <one line, what it should do>

Example 1 — a file whose `add` returns `a - b`:

NONCE: HARNESS_9f31
STATUS: OK
REASON: none
FILE: /abs/path/calc.py
LINE: 2
WRONG: `return a - b` — add() subtracts instead of adding
FIX: return a + b

Example 2 — a file with no such bug:

NONCE: HARNESS_9f31
STATUS: ESCALATE
REASON: clamp() is correct as written; no arithmetic bug present
FILE: /abs/path/clean.py
LINE: 0
WRONG: none
FIX: none
```

Then the dispatch — this flag shape was run and honoured the contract (`dangerouslyDisableSandbox: true`, Bash `timeout` 180000):

```bash
test -s "$H" || echo "MISSING HARNESS: $H"      # preflight; a missing file is appended as literal text
pi -p --provider ollama --model qwen3.6:35b-mlx --offline \
  --append-system-prompt "$H" \
  --tools read -nc -ns -ne --no-session \
  "Find the bug in /abs/path/buggy.py" < /dev/null > "$OUT/bugfind.txt"
cat "$OUT/bugfind.txt"
```

`< /dev/null` is load-bearing, not decoration: without it this exact command stalled past the 600s ceiling and wrote 0 bytes, three times running. With it, warm calls of this shape measured 6s (`auth.py`) and 7s (`retry.py`) on the bug-bearing files and 16s on the clean file that escalates — the no-answer case stays the slow one even once it exits legally. It returned the contract keys and nothing else, no prose, no preamble. Treat any single timing as one sample, never as a budget. **Capture your own first return verbatim** and keep it as the reference string to diff later runs against; a remembered shape is not a diffable baseline. Use `--append-system-prompt` (appends, repeatable, takes text or a file path) rather than `--system-prompt`, which *replaces* pi's coding-assistant prompt and takes the tool-use instructions with it.

## Dispatch and verify

A worker's report is evidence, never authority. On the measured corpus this model got the *reasoning* right every time it produced one and the *coordinates* wrong every time it produced one — and under the `STATUS:` contract it also declined a file that held a real defect (step 8), so a clean-looking answer and an escalation each need their own check. Verification here is not ceremony; it is the step that converts a plausible return into a usable one. Five moves, cheapest first:

- **Nonce.** `NONCE:` is the cheapest signal in the file. Present → the harness reached the model and a process returned (it says nothing about correctness). Absent → **look at the shape of the rest of the output before you diagnose, because absence has two causes with opposite fixes.** Fluent unstructured prose → the harness never loaded: run `test -s "$H"` and check the path in the dispatch. Otherwise contract-shaped with the right diagnosis and one line missing → the model truncated the contract's tail; measured on a return that carried four of five keys and simply dropped `NONCE:`. That is a contract-ordering fix (nonce first, step 5), not a path bug — hunting the path will find nothing wrong with it.

- **Parse `STATUS:`; never grep for the escape token.** `grep -c '^STATUS: OK' "$o"` and `grep -c '^STATUS: ESCALATE' "$o"` — exactly one of the two, on its own line, or the contract broke and nothing in the file is trustworthy. Do **not** use `grep '^ESCALATE:'`: measured, the model kept the format and buried `ESCALATE:` inside `FIX:`, where a line-anchored grep cannot see it and a key-presence check calls the output valid (step 8).

- **Resolve every coordinate from the quote. Never consume the integer you were handed.** Measured across the corpus: diagnosis correct on every dispatch that produced one — 3/3 on the first round, each naming the real seeded defect with a correct `WRONG:` and a correct `FIX:`, and both re-runs quoting the accused line correctly — while line numbers came back **0 for 5**. One named the line above the bug (`LINE: 6`, actual 7). One named the `def` instead of the `return` (`LINE: 4`, actual 5). One returned `LINE: 14` **for a file 11 lines long**. Re-runs under the new contract moved `auth.py` from `LINE: 6` to `LINE: 9` while the truth stayed 7, and `cart.py` from `LINE: 4` to `LINE: 6` while the truth stayed 5. The integer is noise across contracts and runs; the quoted line is stable. So the required move is a grep for the quote:

  ```bash
  grep -Fn '<the WRONG: quote, or a distinctive fragment of it>' "$f"  # the authoritative number; -F is mandatory
  awk 'END{print NR}' "$f"                                            # sanity ceiling; a LINE: past this is fabricated
  sed -n '<the number grep just gave you>p' "$f"                      # follow-up only
  ```

  **Never drop the `-F`.** Quoted source is full of regex metacharacters, and without `-F` grep exits 1 with no output — indistinguishable from "that line is not in this file", which frames a correct model as a fabricator and throws the finding away. Measured: `return total * pct / 100` resolved under `grep -Fn` and silently missed under `grep -n`.

  **`sed -n '<N>p'` on the number the model returned is the trap, not the check.** For the 11-line file it prints nothing, which at least fails loudly; for both off-by-ones it prints a real, plausible, wrong line and reads exactly like confirmation. Use `sed` only *after* `grep -Fn` has produced the number, to confirm you are on the occurrence you meant — a quote proves the text, not that the text appears once, so on boilerplate-heavy code check the enclosing function is unique too. Fix the number yourself and carry on: a right diagnosis with a wrong coordinate is a correction, not a failed item.

- **`--mode json`** to prove a tool actually ran. The stream is pi's session events dumped one JSON object per line. A measured local run carried two `tool_execution_start` and two `tool_execution_end` lines, each with `toolName`, the real `args`, and the real `result` — including the failed first `read` that returned `ENOENT`. Grep for either, but grep with `[^"]*`: `"type":"[a-z]*"` stops at the underscore and reports the events absent when they are right there. That artifact was mistaken for a finding once already. **Close stdin and redirect to a file — two separate faults, and the fix for one is not the fix for the other.** Volume is real: a trivial one-file task produced 289KB of JSONL here (1.6MB on the Fireworks sibling), so write it to a file and grep the file rather than piping it into an inline reader. The five-minute *hang* an earlier version of this file blamed on that volume was `pi -p` blocking on an open stdin — redirecting stdout does not prevent it, only `< /dev/null` does.

  ```bash
  pi -p --provider ollama --model qwen3.6:35b-mlx --offline --mode json \
    --append-system-prompt "$H" \
    --tools read -nc -ns -ne --no-session \
    "Find the bug in /abs/path/buggy.py" < /dev/null > "$OUT/bugfind.jsonl"
  grep -o '"toolName":"[^"]*"' "$OUT/bugfind.jsonl" | sort | uniq -c
  grep -o 'FILE: [^"]*' "$OUT/bugfind.jsonl" | tail -3   # contract lines, still JSON-escaped
  jq -r 'select(.type=="text") | .text' "$OUT/bugfind.jsonl" | tail -20   # /usr/bin/jq, unescaped tail
  ```

  ```bash
  grep -c '"type":"tool_execution_start"' "$OUT/bugfind.jsonl"   # underscore-safe, counts real executions
  ```

  Pass condition, stated before you look: **at least one `"toolName":"read"` whose args name the path you handed it.** Zero means the model answered out of its head. Use `[^"]*`, never `[a-z]*` — the lowercase class silently drops `ask_question`, every extension or custom tool with an underscore, digit or dash, and the `tool_execution_*` events themselves, and shows you a clean, incomplete census. `--mode json` is also the **retry mode for anything that spun**: a task that returned no text at all in text mode completed under json, with the answer recoverable from the `agent_end` event.

- **Compare against the expectation you wrote before dispatching.** No pre-stated expected outcome means every return looks like success. A mismatch re-enters the loop at Orient; it does not authorise a retry of the same brief.

**Every gate above proves shape and provenance. None of them proves correctness, and a confidently wrong finding is contract-perfect by construction.** Measured on the Fireworks sibling, and it applies here unchanged because the gates are identical: two independent dispatches at a test file containing a live network call both returned contract-perfect, nonce-bearing answers that cited the correct line and quoted the file accurately — and both prescribed a fix that **kept the live network call**, having decided the defect was a missing assertion. Every mechanical check passed on a wrong answer. Separately, a `-nt` (no-tools) run returned a contract-perfect answer with a valid nonce citing line 42 of an 11-line file and quoting source text that does not appear in it. So for any sweep whose findings will be acted on unread, the orchestrator — or a second, differently-prompted checker harness — **reads the `WRONG:` field of every non-escalated return** and judges the diagnosis itself. Budget that read into the sweep; it is the only gate that catches this class.

**The case with no answer is the one that spins — until refusal is legal.** A dispatch at a deliberately clean file produced 824 `thinking` events and, in text mode, no final assistant text at all — a >600s foreground kill and a 0-byte output file, indistinguishable from "no findings". That dispatch also ran without `< /dev/null`, so close stdin first and re-run before concluding anything about the model. Under `--mode json` the same task completed and the answer sat in `agent_end`. Adding the `STATUS:` field (step 8) fixed the remaining half at the root: same file, same model, text mode, a clean `STATUS: ESCALATE` in **16s**. Keep all three defences — closed stdin, the field so "nothing here" is a legal cheap move rather than an open-ended search, and a hard per-item cap, because 16s is one sample and the cap is what keeps one pathological item from eating the queue.

Handling the returns: a contract-shaped answer with its nonce and `STATUS: OK` goes to the coordinate re-derivation and then the ground-truth spot-check (rerun the test it says now passes). **`STATUS: ESCALATE` means unresolved, and it has two causes that read identically on the page**: an underspecified brief, or the contract's easy exit taken on a file that did have an answer (step 8). Either way it is an open item — fix the pre-loaded context or split the responsibility and re-dispatch with a **changed** brief, or re-run that one item under the permissive contract. What it never means is "clean"; filing escalations as clean results is how a fan-out loses real findings with no error anywhere. Prose where the contract should be means either the harness never loaded (check the nonce first) or it lacked a worked example (step 7). Never re-send a brief unchanged; a second identical attempt is a skipped Orient phase.

## Orchestrating a queue of harnesses

Opus keeps decomposition, synthesis, conflict resolution, and every judgment whose wrong answer is expensive or hard to detect. Everything mechanical and checkable goes into a harness. If most items are coming back to Opus, the decomposition failed — split harder rather than escalating the substrate.

**Concurrency is 1, and no item gets to run forever.** Build the harnesses in parallel (that is just writing files), then run them one at a time, each in the background under its own cap, so one pathological item cannot consume the whole budget. Index every output and check each item — `basename` alone collides (`tests/api/test_client.py` and `tests/worker/test_client.py` write the same file and the second silently wins), and a stalled or spun item leaves a 0-byte file that reads exactly like "no findings":

```bash
H=/Users/kai/.pi/agent/harnesses/bugfind.md
OUT=/Users/kai/.pi/agent/logs/harness-runs; mkdir -p "$OUT"
CAP=180                       # seconds per item; a stalled item is a FAILED item, not one to wait on
i=0
for f in /abs/path/a.py /abs/path/b.py; do
  i=$((i+1)); o="$OUT/out-$i-$(basename "$f").txt"
  pi -p --provider ollama --model qwen3.6:35b-mlx --offline \
    --append-system-prompt "$H" \
    --tools read -nc -ns -ne --no-session \
    "Find the bug in $f" < /dev/null > "$o" 2> "$OUT/err-$i.txt" &
  pid=$!; t=0
  while kill -0 "$pid" 2>/dev/null && [ "$t" -lt "$CAP" ]; do sleep 2; t=$((t+2)); done
  if kill -0 "$pid" 2>/dev/null; then kill -9 "$pid"; echo "STALLED $i $f"; fi
  wait "$pid" 2>/dev/null
  [ -s "$o" ] || echo "EMPTY $i $f"
  grep -q '^NONCE:' "$o" || echo "NO NONCE $i $f"
done
```

Run that loop itself with `run_in_background: true` and poll `$OUT` — measured items finish in 6–16s, but four items at the 180s cap already exceed the 600000 ms Bash ceiling in the worst case. Size the queue as N × per-call seconds and keep the cap as the worst-case bound. If that product does not fit the time you have, or the fan-out has to run wide, it belongs on `scoped-harness-fw` — the GPU serves one caller and no scheduling changes that.

Applied rules, with the local specifics:

- **One harness is one probe.** One falsifiable question, the kill condition stated in the brief, a verdict back — never an open sweep. "Read the module and understand it" has no outcome that could kill a path, and it is exactly the brief that makes a 35B model produce well-formatted fiction.
- **Never fan out one harness per competing hypothesis.** Probe the most promising candidate, take the verdict, move to the next. On one GPU that is not just doctrine, it is the only thing that finishes.
- **Calibrate the fan-out before you trust it.** Run the first three items against files whose answers you already know. That tells you which failure mode this contract has on this task class — fabrications or misses (step 8) — while it is still cheap to change the contract.
- **Every guardrail goes in this harness, in its own words.** The pi roster's agent files carry none of yours, and a verdict you reached but never transmitted has no effect — the model runs its own default.
- **Isolation is structural, never prose.** A harness that edits gets `--tools read,edit` and a dedicated git worktree as its cwd. There is no `-d` on `pi` — it exits `Error: Unknown option: -d` — so for `pi -p` the worktree is the Bash call's own cwd: `cd /abs/path/worktree && pi -p ...`. Only the detached form takes a directory flag (`pi-spawn -d /abs/path/worktree`). pi resolves relative paths and project trust from the process cwd, so the `cd` is what actually scopes it. Probe `git rev-parse --git-dir` from that cwd first, because outside a repo there is no isolation to have. Bar commit/push with a hook gated on an env var, not with a sentence.
- **Every return carries its evidence, as required contract keys.** `CLAIM:`, `COMMAND:` (the exact line run, with its real output), `NOT_EXERCISED:` (mocked, skipped, unapplied, no live DB — `none` is a legal value, absence is not). Optional fields are the first thing a 35B model drops, so make all three required lines of the contract — the same reason `STATUS:` and `REASON:` are required rather than conditional.
- **Never self-authorize past a guard addressed to a human.** Pushing to a remote, merging, deleting or overwriting outside the named lane, changing collaborator or org settings, spending money, or anything outward-facing stops and comes back to Carson. A harness that hits such a guard returns `STATUS: ESCALATE` — it never sets the override flag itself, and a blocked harness never hands the action to the next item in the queue.
- **Compact returns only.** The contract is what keeps the harness's 40k tokens of reading out of your window; a return that pastes file contents has broken the contract even when it is correct.
- **The write-up is its own turn.** Workers finish the work and drop the trailing non-code step. Send a second, separate dispatch containing only the write-up ask.
- **The author never verifies its own fix.** A fresh harness with no shared context checks it, and its brief says falsifying beats blessing.
- **Escalate the substrate, not the brief.** Moving the same unchanged brief from qwen to Fireworks is a cost change, not a new instrument — it does not reopen a question that came back inconclusive twice.

## Failure modes

| Symptom you would actually see | Cause | Fix |
|---|---|---|
| `EPERM ... mkdir '/Users/kai/.pi/agent/settings.json.lock'` on the first command | Sandbox denies pi's lockfile | `dangerouslyDisableSandbox: true` on the Bash call |
| The dispatch never returns; stdout *and* stderr are both 0 bytes; the Bash call is killed at the ceiling | `pi -p` inherited the Bash tool's open stdin pipe and blocks on it. Nothing about the model, the input or the output volume changed | Append `< /dev/null` to every dispatch. Measured on one command, same warm model, same file: >600s and 0 bytes without it (three times), 16s and a full contract with it |
| `Error: Unknown option: -d` | `pi` has no working-directory flag; only `pi-spawn` does | `cd <worktree> && pi -p ...`, or `pi-spawn -d <worktree>` |
| Fluent, unconstrained *prose*; no `NONCE:` line | The harness path did not exist, so pi appended the path string as literal system prompt text | `test -s "$H"`; never build the path from `$$` |
| Output is *contract-shaped* with the right diagnosis, four of five keys, no `NONCE:` | The model truncated the contract's last line — the harness DID load | Put `NONCE:` first in the contract; do not go path-hunting |
| Every key present, compliance check passes, but `FIX:` (or another field) begins `ESCALATE:` | The escape hatch competed with the rigid format and lost; `grep '^ESCALATE:'` cannot see a mid-line token | Make the exit `STATUS: ESCALATE` + `REASON:` as required keys; parse the field |
| Correct diagnosis, correct fix, and a `LINE:` that is off by one, points at a real but wrong line, or does not exist in the file at all | 35B gets the reasoning right and the coordinates wrong — 0 for 5 across the measured corpus: `auth.py` drew 6 then 9 against a truth of 7, `cart.py` drew 4 then 6 against a truth of 5, and an 11-line file drew `LINE: 14` | `grep -Fn '<the WRONG: quote>' "$f"` for the authoritative number; ceiling-check with `awk 'END{print NR}'`; `sed -n '<N>p'` on the *returned* number is the trap, not the check. Coordinate-critical work routes to `scoped-harness-fw`, whose 120B returned the right line on 4 of 4 defects found |
| `grep -n` on the quote exits 1 with no output, so a correct return looks fabricated | The quoted source contains a regex metacharacter (`*`, `.`, `[`, `(`) — measured on `return total * pct / 100`, which resolves under `-F` and silently misses without it | Always `grep -Fn`. Every file in the measured corpus carried metacharacters on 5–8 lines |
| Every gate passes — nonce present, `STATUS: OK`, quote matches the file, `grep -Fn` resolves — and the finding is still wrong | Mechanical gates prove shape and provenance, never correctness; measured, two independent runs cited the right line, quoted accurately, and prescribed a fix that left the real defect in place | Read the `WRONG:` field of every non-escalated return, or send a second, differently-prompted harness to falsify it. Budget that read into any sweep acted on unread |
| `STATUS: ESCALATE` on a file that does contain a real defect | The escalation-friendly contract under-reports — measured: the permissive contract found the same seeded `retry.py` bug (`return last` instead of raising) that the `STATUS:` contract declined | Re-run that item under the permissive contract, or escalate the substrate; never file an escalation as a clean result |
| >600s and a 0-byte file on a file that genuinely has no bug | Two causes stack: the dispatch had no `< /dev/null`, **and** a no-answer task with no legal exit keeps hunting (824 `thinking` events measured) | Close stdin, then add the `STATUS:` field so refusal is legal — same file, same model, 16s instead of a 600s kill — plus the per-item cap; retry under `--mode json` and read `agent_end` |
| `pi --list-models` shows no ollama entries | `~/.pi/agent/models.json` missing, or `apiKey` empty | Add the provider block keeping **all three** model entries; non-empty `apiKey` |
| `model not found` at dispatch though `pi --list-models` listed it | models.json names a tag that was never pulled — `--list-models` is a config read, not a server query | `ollama list`, then `ollama pull <tag>` |
| Provider errors on a role or effort field | `compat.supportsDeveloperRole` / `supportsReasoningEffort` not set to `false` | Set both `false` — Ollama's compat endpoint has neither |
| A confident answer built from a fragment of the paste | Input exceeded the served window; Ollama truncated from the front, taking the harness with it, and reported nothing | Size against the `ollama ps` CONTEXT of *this* load (8192 and 16384 both observed here, never 65536); split, or raise `OLLAMA_CONTEXT_LENGTH` |
| A convincing tool-call-shaped JSON blob arrives as plain TEXT; `toolResults` is `[]` | `-nt` / `--no-tools` was passed; no child process ever ran | Drop `-nt`; pass an explicit `--tools` allowlist |
| `ENOENT: no such file or directory` on the first read, answer still arrives | Relative path assembled from the wrong base dir | Absolute paths in the task string, always |
| Bash call killed at the timeout with zero output recovered | No redirection, so the kill took the whole answer | Redirect every dispatch to a file; queues of >3 go `run_in_background: true` |
| A `--mode json` call hangs for minutes on a trivial task | The hang is the open stdin, not the volume — though the volume is real: one file produced 289KB of JSONL here, 1.6MB on the Fireworks sibling | `< /dev/null` stops the hang; redirect to a file and grep the file so the volume never enters your window |
| A cold call takes minutes instead of 7–9s | Another caller holds the GPU, or a second model load evicted the first | Serialize the queue; `ollama ps` to see residency |
| Tool census looks clean but the run delegated or asked a question | `grep -o '"toolName":"[a-z]*"'` drops every name with `_`, a digit or a dash | `grep -o '"toolName":"[^"]*"'` |
| The harness cannot delegate; `subagent` is absent | `-ne` disabled extension discovery, **or** `--tools` excluded it — the allowlist filters extension tools too | Drop `-ne` AND pass `--tools read,subagent` |
| Fewer output files than inputs, no error anywhere | Two inputs shared a `basename` and the second overwrote the first | Index the output filenames (`out-$i-...`) |
| A detached run ignores the harness entirely | `pi-spawn` forwards only `--model`, `-n` and the task string | Fold the harness into the task text, or dispatch inline with `pi -p` |
| A detached run is fast, costs money, and leaves the machine | `pi-spawn` defaults to `fireworks/gpt-oss-120b` | Pass `-m ollama/qwen3.6:35b-mlx` |
| `pi-spawn` refuses to start | tmux session names are global across the machine and it will not clobber | Unique `-n` (a task slug plus a timestamp); `-l` lists what runs |
| Output wraps the contract in prose or a preamble | No worked input→output example in the harness | Add step 7's examples |
| A promoted agent spawns its own children | `tools:` omitted in the agent file — grants everything including `subagent` | Write the explicit allowlist |

## Reuse and promotion

When a one-off harness has proven itself across several runs, promote it to `~/.pi/agent/agents/<name>.md` — **user scope only**, never a repo `.pi/agents/`. The `subagent` tool's optional `agentScope` parameter defaults to `"user"`; escalating it to `project`/`both` headless is hard-refused by this machine's patched copy of the extension (`~/.pi/agent/extensions/subagent/index.ts:509`). That guard is a local patch — the upstream example extension has no headless refusal at all and would run project agents unconfirmed — so do not rely on it elsewhere. Simply never pass `agentScope`, and keep the agent out of repo directories.

```markdown
---
name: bugfind-local
description: One line — what it does, and what it must never do.
tools: read
model: ollama/qwen3.6:35b-mlx
---
Body: the same role sentence, rules, both worked examples, and the nonce-first
`STATUS:`-bearing output contract you already validated as a harness file.
```

There is no `--agent` flag: a promoted agent is reachable only through the `subagent` tool from a parent `pi` session, so the parent must keep extensions on (no `-ne`) **and list `subagent` in its own allowlist** (`--tools subagent`, or `--tools read,subagent`) — `--tools` filters extension tools too, so a parent running the recommended `--tools read` sees no `subagent` and the promoted agent is unreachable with no error pointing at the allowlist. The parent is itself a local call: two calls, still one at a time. The pi `subagent` parallel form (`{tasks:[...]}`, max 8, 4 concurrent) is the contention case on this substrate; leave it to `scoped-harness-fw`.

Then record the agent in `pi-delegate`'s roster table so the next session finds it, and per CLAUDE.md copy it into `/Users/kai/projs/skills/` and push.

Roster, `pi-spawn` flags, prompt templates and chains: skill `pi-delegate`. Operator manual: `~/.pi/agent/README-delegation.md`. Doctrine this skill instantiates: `team-orchestration`, `frontier-orchestrator`, `lightning`, `ooda`.
