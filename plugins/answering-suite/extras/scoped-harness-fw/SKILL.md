---
name: scoped-harness-fw
description: Build a scoped harness — one-responsibility role, hard tool allowlist, pre-loaded context, a rigid output contract carrying `NONCE:` first and a required `STATUS: OK|ESCALATE` field — and fan many of them out at once on cheap Fireworks models through `pi`. Use when the work needs real tools (read, grep, bash, edit), the fan-out must run wide or land fast, and a later stage can check the answer mechanically. Use `pi-delegate` instead to drive the roster that already exists (scout, grunt, bulk, tester, reviewer, planner, worker); `fw-delegate` for one-shot text work with no tools; `scoped-harness-local` when cost, privacy or offline picks the substrate and a serial queue is acceptable. Trigger phrases "build a scoped harness", "scoped harness on fireworks", "fan out cheap agents on fireworks", "run these harnesses in parallel", "purpose-built agent for this task", "spawn a pi agent with tools", "promote this harness into an agent file". A bare "build a scoped harness" with no locality or cost signal lands here.
---

# scoped-harness-fw — build the harness, then fan it out

`pi` (`/opt/homebrew/bin/pi`, v0.82.0) is a separate coding agent with its own config at `~/.pi/agent/`. Its default provider is already Fireworks (`~/.pi/agent/settings.json:4-5`: `"defaultProvider": "fireworks"`, `"defaultModel": "accounts/fireworks/models/deepseek-v4-pro"`), auth is in place, and agent files address models as `fireworks/<short-id>`. You orchestrate; cheap Fireworks models do the legwork with real tools.

This skill is how you build **one harness for the task in front of you** and run several at once. `pi-delegate` is the operator manual for the existing roster — read it for `pi-spawn` flags, prompt templates, chains, and the seven stock agents rather than re-deriving them here. `~/.pi/agent/README-delegation.md` is the source both defer to.

A weak model fails on **unbounded choice**, not on bounded execution. A scoped harness narrows the choice set until the failure rate collapses: one responsibility, the smallest tool allowlist that can succeed, the context pre-loaded instead of discovered, a machine-checkable output contract, one worked example, and a legal way to say "I can't". That recovers most of the capability gap for a fraction of the price — and unlike the local substrate, several can run at the same time.

**What it does not buy, measured on a five-file corpus of seeded defects: correctness.** The contract, the nonce and the tool census prove *shape* and *provenance*. A confidently wrong finding is contract-perfect by construction and passes every gate in this file. Read "Mechanical gates prove shape, never correctness" before you plan a sweep whose findings will be acted on unread.

## Read this before running anything

**Every Bash call that touches `~/.pi/` needs `dangerouslyDisableSandbox: true`** — the `mkdir`, the heredoc that writes the harness, the `pi` and `tmux` calls, the log greps, and `ps`/`pgrep`. The sandbox's write allowlist covers `$TMPDIR`, `/tmp/claude` and the cwd, not `~/.pi`. Two different errors both mean "sandbox", not "broken install":

```
EPERM: operation not permitted, mkdir '/Users/kai/.pi/agent/settings.json.lock'
mkdir: /Users/kai/.pi/agent/harnesses: Operation not permitted
```

**The Write tool cannot reach `~/.pi` either.** Write harness files with a `cat > "$H" <<'EOF'` heredoc inside an unsandboxed Bash call.

### `pi -p` does not exit while its stdin is an open pipe — append `< /dev/null` to every dispatch

This is the most expensive gotcha in this file, and redirection does not save you from it. Measured: a `--mode json` dispatch written exactly as this skill used to show it hung at **10 minutes**, and again at **3 minutes**, producing **0 bytes on stdout and 0 bytes on stderr both times** — despite the redirect-to-a-file that is supposed to preserve partial output. The identical command with `< /dev/null` appended returned **rc=0 in 5s with 1.6MB**. Independently reproduced on the local substrate (`scoped-harness-local`): three foreground stalls past 600s, then 16s with `< /dev/null`.

The cause is stdin inheritance. It is **not** output volume, **not** provider trouble, **not** batch width. So: `< /dev/null` on every `pi -p` in this file, text mode and json mode alike, single dispatch and fan-out alike. Redirect as well — but redirect for the volume, because a stall leaves both files empty and there is nothing to recover.

### Bound every call: there is a working timeout, and it is not the Bash tool's

There is no `timeout` binary here, but `perl`'s alarm works and was verified repeatedly at N=45, 90, 100, 120 and 200 seconds:

```bash
perl -e 'alarm 120; exec @ARGV' pi -p ... < /dev/null      # rc=142 when the alarm fires
```

`N≈120` is the right cap for a `--tools read` leaf on one small file. Raise it for chained tool calls; do not raise it to hide a stall, because a stall does not finish at 600s either.

Pair the cap with a **gate-and-retry loop** — a short bounded trivial probe first, the real dispatch only if the probe returned bytes:

```bash
P=$(perl -e 'alarm 20; exec @ARGV' pi -p --provider fireworks \
      --model fireworks/gpt-oss-120b -nt -nc -ns -ne --no-session \
      "say EXACTLY: PREFLIGHT_OK" < /dev/null)
[ -n "$P" ] || { echo "PROBE EMPTY — client-side stall, do not dispatch"; exit 1; }
perl -e 'alarm 120; exec @ARGV' pi -p --provider fireworks \
  --model fireworks/gpt-oss-120b --append-system-prompt "$H" \
  --tools read -nc -ns -ne --no-session "<task>" \
  > "$OUT/out.txt" 2> "$OUT/err.txt" < /dev/null
rc=$?; [ $rc -eq 142 ] && echo "ALARM at 120s — treat as a failed item, not a slow one"
```

- Set the Bash tool's own `timeout` to `600000` ms as the outer cap, but never as the mechanism. A Bash-tool kill tells you nothing; an alarm expiry gives you rc=142 and whatever partial output existed.
- **Always redirect a dispatch to a file** (`> "$OUT/out-<slug>.txt" 2> "$OUT/err-<slug>.txt"`). For a normal overrun this preserves the partial answer. For a stdin stall it preserves nothing — that is what `< /dev/null` is for.
- A killed Bash call is not a failed dispatch. Check the output file and `pgrep -f <harness-file>.md` before re-sending, or you re-run work that is still in flight.

**Preflight, two probes** (both need the sandbox flag). The first proves the model ids are wired — it is a config read, not a live check. The second is the only thing that proves auth and reachability:

```bash
pi --list-models fireworks | head -5
pi -p --provider fireworks --model fireworks/gpt-oss-120b -nt -nc -ns -ne --no-session \
  "say EXACTLY: PREFLIGHT_OK" < /dev/null
```

**Auth lives in the environment, not in a file.** `~/.pi/agent/auth.json` contains **no Fireworks credential at all** — only a stale anthropic OAuth block — so inspecting it when a batch fails tells you nothing. The Fireworks credential is `FIREWORKS_API_KEY`. One line separates a dead key from a client-side stall:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://api.fireworks.ai/inference/v1/chat/completions \
  -H "Authorization: Bearer $FIREWORKS_API_KEY" -H 'Content-Type: application/json' \
  -d '{"model":"accounts/fireworks/models/gpt-oss-120b","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}'
```

A batch-wide zero-byte failure was measured **while that endpoint was verifiably healthy**. Zero bytes across a whole batch is a client-side stall (stdin, above) until this probe says otherwise — not auth, not throttling.

**`-nt` is legal only in that echo probe, and its real failure mode is worse than "obviously fake".** With `-nt` on a genuine bugfind task the model returned a **contract-perfect answer carrying the valid nonce**, with an invented line number and invented quoted source. Verbatim, against an 11-line file:

```
FILE: /.../src/retry.py
LINE: 42
ENCLOSING: except Exception as e:
WRONG: Returns the caught exception object (`return e`) instead of re-raising it.
FIX: Raise the exception (`raise`) or re-raise the caught exception (`raise e`).
NONCE: HARNESS_F3a1
```

`wc -l` on that file is 11, `sed -n '42p'` is empty, and the string `return e` does not occur in it. Every mechanical gate this skill offers passed it. **So the nonce does not survive as evidence of tool use** — it proves the harness text reached the model and nothing more. Only a `--mode json` `toolName` census, or a token planted in the file that the answer is required to quote, distinguishes a read from a recollection.

**Budget the wall clock from measurements, and know they were taken under load.** A no-tool one-shot returns in roughly **0.6–2s**. A trivial single-file `--tools read` harness call ran **~3s**; two real harness dispatches (a genuine defect hunt over a real file) measured **8.5s and 12.4s**. All of these were measured with **5–12 concurrent `pi` processes** on the machine, so they are not best-case numbers. `README-delegation.md:32` reports 8.83s for a single-step `scout` through the `subagent` harness and ~18s for an 8-file `bulk` extraction, and explicitly disavows its own older per-agent timings — consistent with the above, and still not a schedule you can compute up front. The old stall figures in this file ("zero bytes at 180s and again at 420s") were **not** a latency phenomenon: they are the stdin bug, and they reproduce or vanish on command.

**Cost is real and tiny, and now exact.** A single-file harness dispatch on `gpt-oss-120b` measured **$0.00034** at `totalTokens 1749` (list price 0.15/0.60 USD per 1M, `~/.pi/agent/models-store.json:122-123`). Three thousand of them cost a dollar. That number is the whole justification for the standing rule: **re-run to verify rather than trust a doubtful result** — a second run costs less than the tokens you would spend reasoning about whether to believe the first.

**Parallelism is the advantage over the local substrate, and it is real.** Measured at width 6, six independent `pi -p` processes all started within **7 ms** of each other and the batch wall clock equalled the slowest single worker: **14.76s versus 55.68s serial (3.77x)**, and **15.24s versus 62.07s** on a second run. Local means one GPU and one caller (a 7–9s cold call measured over 300s under contention, `local-delegate` rule 6); this substrate has no such lane.

**Correct a causal error this file used to carry: high process count does not cause stalls.** The data inverts it — the wide batches were the *healthy* ones, and the zero-byte stalls hit nearly idle moments. Do not cap batch width as a stall remedy; fix stdin and bound each call. The only measured concurrency ceiling anywhere is `subagent`'s own (max 8 tasks, 4 concurrent, `extensions/subagent/index.ts:33-34`), which applies to that dispatch form only.

## Route first

| The work in front of you | Route |
|---|---|
| You can name the file, and one grep or one line-ranged read answers it | Inline. Spawn overhead exceeds the return. |
| One transform over text you already hold, no tools needed | `fw` — skill `fw-delegate`. |
| A roster agent already covers it: read-only recon, a fully-specified mechanical edit, bulk extraction, run the suite, review a diff, write a plan | `pi-delegate`. Drive the roster; do not rebuild it. |
| Several tool calls, narrow and mechanical or bounded-judgment, and a later stage checks the answer | **This skill.** Build a harness. |
| Same shape, but cost, privacy or offline decides the substrate and a serial queue is acceptable | `scoped-harness-local`. |
| A wrong answer is terminal, expensive, or hard to detect; or the item is as hard as the whole task | A Claude subagent, or keep it inline. |

**Rows 3 and 4 overlap — break the tie on the output shape.** Prefer `pi-delegate` when the roster agent's prose return is what you want to *read* (scout returns `file:line` and that is fine). Build a harness when you need to **grep or diff the returns mechanically**: N workers, one fixed-key row each, asserted against an expected count. No roster agent has a fixed-key contract.

The boundary is falsifiable, not a feeling: **name the command or the `sed -n '<N>p'` that would prove the return wrong**, and name the grep that will consume the returns. If you can name neither, the item is not harness work — a cheap model given an uncheckable brief returns confident, well-formatted, unverifiable prose.

## Build the harness

1. **Name the single responsibility in one sentence.** "Report the line in `<abs path>` where `<symbol>` is assigned." If the sentence needs an "and", that is two harnesses — split it, because the second responsibility is where the model starts choosing.

2. **Choose the model for the task class.** Costs are USD per 1M tokens from `~/.pi/agent/models-store.json`; every Fireworks entry there carries `reasoning: true`, which says a thinking level exists — **not** that `--thinking off` is accepted (step 9).

   | Task class | `model:` | ctx / max out | in → out | Why this one, and what rules the others out |
   |---|---|---|---|---|
   | **Bounded-judgment inspection of one named file** (this skill's flagship case) | `fireworks/gpt-oss-120b` | 131k / 32k | 0.15 → 0.60 | Measured: held the contract on **every** single-read judgment dispatch across a five-file corpus, at **$0.00034** each. No cheaper model is worth probing for this. |
   | Mechanical edits, running a suite | `fireworks/gpt-oss-120b` | 131k / 32k | 0.15 → 0.60 | What `grunt`, `tester` and `worker` already run. The 131k window rules it out for whole-repo inputs. |
   | Bulk extraction over huge inputs | `fireworks/deepseek-v4-flash` | 1M / 384k | 0.14 → 0.28 | `bulk`'s model, and the only 1M-context model under $0.20 in. `bulk.md:6-7` flags it as slower than the others on chained tool calls and suggests swapping to `qwen3p7-plus` when latency matters — the underlying timings are disavowed in `README-delegation.md:32`, so treat the direction as real and the magnitude as unmeasured. |
   | Read-only recon, many chained tool calls | `fireworks/qwen3p7-plus` | 262k / 65k | 0.40 → 1.60 | `scout`'s model, and the swap `bulk.md` names for chained calls. 2.7x gpt-oss-120b on input rules it out for purely mechanical work. |
   | Review, planning | `fireworks/minimax-m3` | 512k / 512k | 0.30 → 1.20 | What `reviewer` and `planner` run; 512k both ways holds a large diff plus the finding list. |
   | Never | `accounts/fireworks/routers/*` | — | 1.5–2.1x the base model | The five `routers/` entries cost 1.5–2.1x the equivalent `models/` id for the same window (e.g. `glm-5p2-fast` 2.1/6.6 vs `glm-5p2` 1.4/4.4; `kimi-k2p6-fast` 2/8 vs `kimi-k2p6` 0.95/4). Point a harness at `models/`. |
   | Not a harness model | `fireworks/deepseek-v4-pro` | 1M / 384k | 1.74 → 3.48 | The interactive `pi` default. 12x gpt-oss-120b on input — keep it for the session you drive by hand. |

   `claude-*` through pi currently 400s (subscription auth conflict). Pick a Fireworks model rather than routing around it.

3. **Derive the tool allowlist from the responsibility** — the smallest set that can succeed, read-only unless the job is to edit. Built-in names, exhaustive: `read`, `bash`, `edit`, `write`, `grep`, `find`, `ls` (`grep`/`find`/`ls` are OFF by default; `read,bash,edit,write` is what you get with no `--tools` at all). `--tools` is an allowlist over **built-in, extension and custom tools alike** (`pi --help`, `dist/cli/args.js:245-246`), so a registered extension name is legal too — `subagent` is the one you will actually use, and a harness that must delegate has to list it. A name matching no registered tool is silently not forwarded, so a typo leaves the model improvising without the capability. `ask_question` is a real tool: leave it out, so a headless harness cannot stall waiting for a human who is not there. In an *agent file* the `tools:` line is mandatory — omitting it grants everything including `subagent` itself, with no depth guard anywhere.

4. **Pre-load the context instead of making the model discover it.** A child process has empty context: absolute paths, exact symbol names, the real question, and the relevant excerpt pasted in. "Fix the bug we discussed" means nothing to it. Absolute paths especially — a run this session assembled a path from the wrong base directory, got `ENOENT: no such file or directory`, and self-corrected on the second call, costing a round trip.

5. **Write the output contract**: fixed keys, one per line, machine-checkable, plus "nothing else, no prose, no code fences". The contract is what lets you grep the return instead of reading it. **This key order is ported from `scoped-harness-local`, where it was bought with two measured failures — keep it:**

   ```
   NONCE: <the literal token written into the harness>
   STATUS: OK | ESCALATE
   REASON: <one line; required when STATUS is ESCALATE, `none` when OK>
   FILE: <absolute path>
   LINE: <integer>
   ENCLOSING: <the unique function or block containing that line>
   WRONG: <what the line does now, one line, quoting the accused source line>
   FIX: <what the line should be, one line>
   ```

   **`NONCE:` first, never last.** A weak model drops the tail, so provenance goes where truncation cannot reach it (measured locally: a return carrying four of five keys, right diagnosis, missing only the final `NONCE:`). **`STATUS:` second**, ahead of every field that only makes sense once an answer exists — step 7 is why.

   For any harness that runs commands or edits, add `COMMAND:` (the exact line run, with its real output) and `NOT_EXERCISED:` (mocked, skipped, unapplied; `none` is a legal value, absence is not) as **required** lines. Cheap models drop optional fields first, so an evidence field that is not in the contract does not exist.

6. **Put one worked example of each `STATUS` inside the harness** — an input and the exact expected output, including one case where the answer does not exist. This is the highest-leverage token spend in the whole file; a contract stated without an example is where cheap models drift back into prose, and a model that has never seen an `ESCALATE` example will not produce one.

7. **Make the refusal a FIELD of the contract, never an alternative output mode.** The obvious design — "reply `ESCALATE: <one line why>` and nothing else" — is what this file used to teach, and `scoped-harness-local` measured it failing in the most dangerous direction: the model did not switch modes, it emitted the **full contract** and smuggled the token into a field (`FIX: ESCALATE: cannot identify bug ...`), where `grep '^ESCALATE:'` cannot see it and a key-presence check calls the output valid. It also broke this file's own fan-out gate: `grep -L '^NONCE: '` flags a correct escalation as a broken contract, because `ESCALATE:`-and-stop and `NONCE:` were mutually exclusive, and the orchestrator then debugs a harness that loaded fine.

   Two measured effects of the field design, both from the sibling and both worth having here:
   - It eliminated the smuggling failure — the exit was taken cleanly, with no fabricated line number.
   - It cut the no-answer case from a **>600s stall to 16s**. A model with no legal way to say "nothing here" keeps hunting for something that is not there.

   **The cost, because there is no free version of this: an escalation-friendly contract trades fabrications for misses.** Measured on the sibling: a real seeded defect that the permissive contract *found* was declined by the `STATUS:` contract on the same file with the same model. Choose by which failure costs you more, and plan to pay for the other:

   | The expensive failure | Contract shape | Where you pay |
   |---|---|---|
   | False positives — anything auto-applied, or a fan-out too wide to read every return | The `STATUS:` contract above | Misses. Every escalation is an open item to re-run, never a clean result. |
   | Misses — security sweeps, audits, any "find every X" | The permissive contract, no legal exit | Fabrications, caught at verification where they are visible and cheap. |

   Two rules hold whichever you pick. **`STATUS: ESCALATE` means "unresolved, needs a second look", never "no defect present"** — filing escalations as clean results loses real findings with no error anywhere. And **calibrate against known-answer files before trusting either shape across a fan-out**: one pass over a handful of files whose defects you already know tells you which failure mode you actually have, for the cost of a few sub-cent calls.

8. **Name the hard guardrails, each paired with the legal move.** Read only the file the task names — anything else is `STATUS: ESCALATE`. Change only what the task names; report anything further as text rather than applying it. Never run destructive commands (`rm`, `git reset --hard`, force push, `DROP`). Anything outward-facing (push, merge, post, delete outside the named lane) is `STATUS: ESCALATE`, never a self-authorized action. Answer from the file, never by asking — nothing is listening on a headless run.

9. **Strip the ambient context: `-nc -ns -ne --no-session`.** These drop AGENTS.md/CLAUDE.md discovery, skills, extensions and session persistence, which is what keeps a cheap model on the brief. The measured latency ladder for this strip — 15.4s defaults → 12.2s with harness and `--tools read` → **2.7s** stripped → 2.5s adding `--thinking off` — was taken on the **LOCAL** substrate and did not survive re-measurement there (best explained as cold-versus-warm load). On Fireworks the API round trip dominates regardless, so treat these flags as a focus lever, not a latency lever. Three consequences that do port:
   - `-ne` disables extension discovery and therefore removes the `subagent` tool. Drop `-ne` on any parent that must delegate further, and keep it on every leaf.
   - **The strip is unavailable on the detached form.** `pi-spawn` cannot pass these flags at all (step 10), so a detached run always discovers AGENTS.md/CLAUDE.md, loads skills, and persists a named session.
   - **`--thinking off` is per-model, measured.** Accepted on `qwen3p7-plus`, `minimax-m3` and `deepseek-v4-flash`; rejected on `fireworks/gpt-oss-120b` with HTTP 400 `Invalid reasoning effort: none` (`off` maps to reasoning effort `none`), even though `pi --list-models` shows `thinking yes` for it. One lane could not reproduce the 400 at all — its dispatch **stalled silently instead of erroring**, so the symptom may be an empty output file rather than a legible message. Omit the flag unless you have probed that exact model; it costs nothing to leave out.

10. **Decide the dispatch form.** Inline `pi -p` when you want the result in this turn — the default, and the only form that carries a harness *file*. An agent file in `~/.pi/agent/agents/` once the harness is proven and you want it callable by name through `subagent` (there is **no `--agent` flag** — that is the only route in). `~/.pi/agent/bin/pi-spawn` when the work must outlive this session — **read the four warnings in the fan-out section first: it cannot carry a harness, it eats your flags, it always gets the full tool set, and its default model comes from the environment.**

## A complete worked harness

Write the harness to **one fixed absolute path** and reference that same literal path everywhere. Never put `$$` in it: the Write tool takes `$$` literally, and every Bash call is a fresh shell with a different PID, so the write and the dispatch land on different files. The failure is silent and total — `--append-system-prompt` reads the file only if it exists and otherwise appends **the path string itself as system-prompt text** (`dist/core/resource-loader.js:15-28`), so the run exits 0 with no contract, no guardrails, no refusal path, and a fluent unharnessed answer. `$$` is fine only for `pi-spawn` session names, where the create and the check sit in one Bash call.

```bash
mkdir -p ~/.pi/agent/harnesses ~/.pi/agent/logs/harness-runs   # once; needs dangerouslyDisableSandbox
H=/Users/kai/.pi/agent/harnesses/bugfind.md
OUT=/Users/kai/.pi/agent/logs/harness-runs/$(date +%Y%m%d-%H%M%S)-bugfind   # session-scoped; see below
mkdir -p "$OUT"
cat > "$H" <<'EOF'
You find the single bug in one named file and report it. You never edit.

Rules:
- Read only the file named in the task. Do not open other files.
- Report exactly one bug: the one that causes the symptom in the task.
- In WRONG:, quote the accused source line character for character, then say what it does.
- Never guess a line number. If no bug in that file explains the symptom, or the task
  is ambiguous, keep this exact format and set STATUS: ESCALATE with a one-line REASON.
- Never edit, never write, never run a command, never ask a question.

Output contract — exactly these eight lines, in this order, nothing else, no prose, no code fences:
NONCE: HARNESS_9f31
STATUS: OK
REASON: none
FILE: <absolute path>
LINE: <integer>
ENCLOSING: <the function or block containing that line>
WRONG: <the quoted source line and what it does, one line>
FIX: <what the line should be, one line>

Example 1 — task: "Find the bug in /tmp/add.py. Symptom: add(2,3) returns -1."
/tmp/add.py line 2, inside `def add(a, b):`, reads `return a - b`.
Your entire reply:
NONCE: HARNESS_9f31
STATUS: OK
REASON: none
FILE: /tmp/add.py
LINE: 2
ENCLOSING: def add(a, b)
WRONG: `return a - b` — add() subtracts b from a
FIX: return a + b

Example 2 — task names a file whose clamp() is correct; no bug explains the symptom.
Your entire reply:
NONCE: HARNESS_9f31
STATUS: ESCALATE
REASON: clamp() is correct as written; no bug in this file explains the symptom
FILE: /tmp/clean.py
LINE: 0
ENCLOSING: none
WRONG: none
FIX: none
EOF
test -s "$H" || echo "MISSING HARNESS: $H"
```

Dispatch it (`dangerouslyDisableSandbox: true`, Bash `timeout` 600000 as the outer cap):

```bash
H=/Users/kai/.pi/agent/harnesses/bugfind.md
OUT=/Users/kai/.pi/agent/logs/harness-runs/$(date +%Y%m%d-%H%M%S)-bugfind; mkdir -p "$OUT"
test -s "$H" || { echo "MISSING HARNESS: $H"; exit 1; }   # a missing path is appended as literal text
perl -e 'alarm 120; exec @ARGV' \
pi -p --provider fireworks --model fireworks/gpt-oss-120b \
  --append-system-prompt "$H" \
  --tools read -nc -ns -ne --no-session \
  "Find the bug in /Users/kai/Desktop/projs/<your-file>.py. Symptom: <the observed wrong behaviour>." \
  > "$OUT/bugfind.txt" 2> "$OUT/bugfind.err" < /dev/null
cat "$OUT/bugfind.txt"
```

**`test -s "$H"` is the only *pre-hoc* guard you have.** The nonce is a post-hoc detector: it arrives after any writes have already happened. So for any harness carrying `edit` or `write`, the existence check is **mandatory in the same Bash call as the dispatch** — not advisable, mandatory — because an unharnessed run with those tools has already changed files by the time you notice the missing nonce.

**Provenance:** this flag shape has now run on Fireworks against a corpus of Python files with seeded defects, holding the contract on every dispatch, at 8.5s and 12.4s on the two real defect hunts. Capture your own first return verbatim as the reference string to diff later runs against — a remembered shape is not a diffable baseline.

### The no-symptom sweep variant

The harness above is **symptom-driven**, and so was every bugfind template this file used to carry. But the canonical fan-out case is sweeping N files for defects **you have not found yet**, where no symptom exists. Following the symptom template literally forces you to invent N symptoms — which is exactly the confident fabrication the harness exists to prevent, moved upstream into your own brief.

For a sweep, keep the same contract keys and change two lines. Replace the report rule with an explicit **defect-class predicate**, and key the escalation to the ambiguity that actually arises:

```
- Report exactly one defect: the most serious defect of class <X> in this file.
  ("Class <X>" examples that work: unhandled error path; resource never closed;
  behaviour that contradicts the function's own name or docstring; a test that
  asserts nothing about what it calls.)
- If the file contains zero defects of class <X>, or two that are equally
  defensible as "most serious", keep this exact format and set STATUS: ESCALATE
  with a one-line REASON naming which case it is.
```

Two structural costs of these defaults, both correct to keep and both worth planning around:

- **`Report exactly one defect` suppresses second findings.** A file with three defects returns one. Budget a second pass on any file whose first return came back `STATUS: OK`, or narrow the class and re-sweep.
- **`Read only the file named in the task` makes cross-file reasoning impossible.** Measured: in a five-lane sweep, no worker ever noticed that a test in the corpus *asserts the buggy behaviour* of a function another worker had just called broken. A single-file sweep structurally cannot find contradictions between files — plan a second pass with a two-file brief for that, or do it yourself.

## Dispatch, then verify

A harness return is evidence, never authority. **A relayed claim becomes yours**, so run one probe before you believe it or repeat it.

- **Nonce — as a contract line, never bolted onto the task string.** The harness declares `NONCE: HARNESS_9f31` first and the "exactly these lines" clause requires it. Present → the harness text reached the model and a process returned. **It says nothing about correctness and nothing about tool use** — a `-nt` run with no child process at all returned a valid nonce (see above). **Absent → look at the shape of the rest of the output**, because absence has two causes with opposite fixes: fluent unstructured prose means the harness never loaded (check `test -s "$H"` and the path in the dispatch); contract-shaped output missing only that line means the model truncated, which nonce-first is designed to prevent. Asking for the nonce in the *task* instead is self-defeating: a harness obeying "nothing else" correctly suppresses it, and you read a good return as a failure. Change the token whenever you rewrite the harness.
- **Parse `STATUS:`; never grep for a bare escape token.** `grep -c '^STATUS: OK' "$o"` and `grep -c '^STATUS: ESCALATE' "$o"` — exactly one of the two, on its own line, or the contract broke and nothing in the file is trustworthy. Do **not** use `grep '^ESCALATE:'`: measured on the sibling, the model kept the format and buried `ESCALATE:` inside `FIX:`, where a line-anchored grep cannot see it. A field parse survives both branches; a mode switch does not.
- **`--mode json`** — the run emits `tool_execution_start` / `tool_execution_end` events carrying `toolName`, real `args` and the real `result`. **Redirect it to a file and close stdin:**
  ```bash
  perl -e 'alarm 180; exec @ARGV' \
  pi -p --provider fireworks --model fireworks/gpt-oss-120b --mode json \
    --append-system-prompt "$H" \
    --tools read -nc -ns -ne --no-session "<task>" \
    > "$OUT/bugfind.jsonl" 2> "$OUT/bugfind.jsonl.err" < /dev/null
  grep -o '"toolName":"[^"]*"' "$OUT/bugfind.jsonl" | sort | uniq -c
  ```
  The volume is why you redirect: a trivial one-file task on Fireworks produced **1.6MB / 613 lines** of JSONL (another lane measured ~755KB on the same shape), roughly 2–5x the 289KB measured locally. The stall is why you close stdin — the 10-minute and 3-minute zero-byte hangs were both this exact command without `< /dev/null`.
  Pass condition, stated before you look: **at least one `"toolName":"read"` whose args name the path you handed it.** Zero means the answer came out of the model's head. Use `[^"]*`, never `[a-z]*` — the lowercase class silently drops `ask_question` and every name with an underscore, digit or dash, and shows you a clean, incomplete census.
- **Spot-check the claim against ground truth** — `sed -n '<N>p' <file>` for a cited line, or rerun the exact command the harness says it ran. **Coordinates were reliable on this substrate**: across the seeded corpus the model found 4 of 5 defects with a **correct line number on every one** — a real advantage over the local sibling, which got the diagnosis right and scored **0/3 on line numbers** and therefore mandates re-deriving every coordinate from the quoted line. Here the spot-check is one cheap command rather than a mandatory correction step. Run it anyway; it is the only thing that catches a `-nt` fabrication cheaply.

  When a coordinate does *not* check out, fall back to the sibling's move and resolve it from the quote — but **`grep -Fn`, never `grep -n`**. Source lines carry regex metacharacters (`*`, `.`, `[`, `(`), and without `-F` grep exits 1 with no output, which is indistinguishable from "that line is not in the file" and frames a correct model as a fabricator. Measured on the sibling: `return total * pct / 100` resolves under `-F` and silently misses without it.

### Mechanical gates prove shape and provenance, never correctness

**A confidently wrong finding is contract-perfect by construction.** This is the headline result of the five-lane test and the reason the gates above are necessary and not sufficient.

`tests/test_net.py` in the corpus contains a test that makes a **live network call** — the defect. Two independent dispatches **18 minutes apart** both returned contract-perfect, nonce-bearing answers citing the correct line and quoting the file accurately, and both prescribed a fix that **keeps the live network call**, treating "no assertion on the response" as the defect:

```
WRONG: Calls urlopen but does not verify the response (no assertion)
FIX: response = urllib.request.urlopen("https://example.com"); assert response.status == 200
```

`grep -L '^NONCE: '` passes it. The key-order assertion passes it. `sed -n '<N>p'` confirms the quoted line exists exactly where claimed. Nothing short of a human reading the `WRONG:` field catches it. Same class, second example: on a path-traversal defect in `paths.py`, one of three dispatches proposed `os.path.abspath(os.path.join(base, user_path))` as the fix — correct detection, and a remedy that **does not prevent traversal** and would have shipped the bug.

So, for any sweep whose findings will be acted on unread: **the `WRONG:` field of every non-escalated return must be read — by you, or by a second, differently-prompted checker.** Budget that reading time as part of the sweep. At $0.00034 a dispatch the model time is free and your attention is the scarce resource; do not spend the savings pretending the gates covered it.

### In-flight probes

- **`pgrep -lf 'pi -p'` is broken for this purpose** — it has exactly the false-positive weakness this file used to attribute only to `ps aux | grep`. The `-f` match hits every `/bin/zsh -c …` wrapper whose command string merely contains those flags; measured, it reported **4 live workers when zero existed**.
- **Inline runs:** `pgrep -f bugfind.md | wc -l` — the harness filename is a unique marker that appears only in real dispatch command lines.
- **Detached runs:** `pgrep` cannot see them at all. Use `~/.pi/agent/bin/pi-spawn -l`, or `tmux has-session -t pi-<name>`. The log's last line, `[pi-spawn] exit=0`, is the only ground truth for success — and it does not exist for the first several seconds (see the wait loop below).

A return that misses the contract is a failed dispatch, not a partial result. **A `STATUS: ESCALATE` that does not reproduce is not evidence of an underspecified brief** — measured, one run escalated where another on the same file returned a confident correct answer. Re-run the item once before you act on it. If it escalates twice, then fix the pre-loaded context or split the responsibility. Never re-send the same brief unchanged after a *failure*; a second identical attempt is a skipped Orient.

## Orchestrate a team of harnesses

You decompose and you synthesize; harnesses do everything in between. Never spawn one to plan the run it belongs to — decomposition needs whole-task context, and a bad partition gets executed faithfully by every worker downstream. Never hand the merge of N returns to another cheap agent: deciding which of two disagreeing workers is wrong is exactly the judgment you are paying for.

**Fan-out shapes.**

- *Independent `pi -p` processes* — **the only shape that carries a one-off harness**, and the measured 3.77x. Background each one and `wait`; one output file per worker, never a shared stdout, because interleaved returns cannot be attributed. Index the filenames (`basename` alone collides: `tests/api/test_client.py` and `tests/worker/test_client.py` write the same file and the second silently wins) and **scope `$OUT` to this batch** — a fixed directory with `$i`-indexed names restarting at 1 every batch collides with the last batch and with every other session.
  ```bash
  H=/Users/kai/.pi/agent/harnesses/bugfind.md
  OUT=/Users/kai/.pi/agent/logs/harness-runs/$(date +%Y%m%d-%H%M%S)-$$; mkdir -p "$OUT"
  test -s "$H" || { echo "MISSING HARNESS: $H"; exit 1; }
  i=0
  for f in /abs/a.py /abs/b.py /abs/c.py /abs/d.py; do
    i=$((i+1))
    perl -e 'alarm 120; exec @ARGV' \
    pi -p --provider fireworks --model fireworks/gpt-oss-120b \
      --append-system-prompt "$H" \
      --tools read -nc -ns -ne --no-session \
      "Find the bug in $f. Symptom: <the observed wrong behaviour>." \
      > "$OUT/out-$i-$(basename "$f").txt" 2> "$OUT/err-$i.txt" < /dev/null &
  done
  wait
  grep -L '^NONCE: ' "$OUT"/out-*.txt          # harness never loaded, or the model truncated
  grep -c '^STATUS: ESCALATE' "$OUT"/out-*.txt # open items — re-run once each, never file as clean
  ```
  All six processes in a width-6 batch started within 7 ms and the batch cost the slowest worker (14.76s vs 55.68s serial), so `wait` under one Bash timeout is fine at this width; the per-item `alarm` is what keeps one stalled worker from eating the batch. More items than fit: run the loop `run_in_background: true` and poll `$OUT`. The contract's `FILE:` key is what lets you assert return count == item count.
- *Parallel `subagent`* — one call becomes `{tasks:[{agent, task}, ...]}`, **max 8, 4 concurrent** (`extensions/subagent/index.ts:33-34,451`). **Each task must name an agent file that already exists in `~/.pi/agent/agents/`**; a `--append-system-prompt` harness has no name and is unreachable here. To fan a new harness out this way, promote it first (below). The parent needs the `subagent` tool, so it runs **without** `-ne`:
  ```bash
  pi -p --provider fireworks --model fireworks/gpt-oss-120b \
    --tools subagent -nc -ns --no-session \
    "run 2 scouts in parallel: one find <X> in <abs path>, one find <Y> in <abs path>" < /dev/null
  # -ne omitted on purpose: it would remove the subagent tool. -nc -ns --no-session still apply.
  ```
- *Detached `pi-spawn`* — for work that outlives the session, with four warnings that each cost a real run.

  **1. It cannot carry a harness.** It forwards only `-p --model -n <task>` (`pi-spawn:162`), silently dropping `--append-system-prompt`, `--tools` and every strip flag. Fold the rules, contract and `STATUS:` field into the task text itself, or promote the harness to an agent file first (its `tools:`/`model:` frontmatter does travel).

  **2. Flag placement is a live footgun in both directions.** Flags after the task string are silently dropped. Flags *before* it — where every other example in this file puts them — are consumed by `pi-spawn`'s own `getopts ":m:d:n:k:lh"` (`pi-spawn:42`): `-nc`, `-ns`, `-ne` and `-nt` each parse as `-n <letter>`, **silently renaming the session and its log file** to `pi-c` / `~/.pi/agent/logs/c.log` and so on, and `--`-style long flags hard-fail with `pi-spawn: unknown option --` and exit 2 (`pi-spawn:50`). The only correct form is `pi-spawn`'s own four flags before the task, and nothing after it.

  **3. It always gets `read, bash, edit, write`, so isolation must be structural.** Measured: an unharnessed `pi-spawn` run was observed **editing a second file the task never named**. You cannot make a detached run read-only, so **`-d <throwaway dir or git worktree>` is mandatory on every `pi-spawn` dispatch** — not conditional on whether you think it will edit.

  **4. Its default model comes from the environment** — `DEFAULT_MODEL="${PI_SPAWN_MODEL:-fireworks/gpt-oss-120b}"` (`pi-spawn:10`). Always pass `-m` explicitly so an inherited env var cannot redirect the dispatch off the model you costed. And note that a detached run cannot strip ambient context: AGENTS.md/CLAUDE.md discovery and skills load, and the session persists under its name.

  ```bash
  N=audit-$$
  ~/.pi/agent/bin/pi-spawn -m fireworks/gpt-oss-120b -d /abs/path/worktree -n "$N" \
    "self-contained task prompt with the rules, contract and STATUS field folded in"
  L=~/.pi/agent/logs/$N.log; n=0
  until grep -q '^\[pi-spawn\] exit=' "$L" 2>/dev/null || [ $n -ge 60 ]; do sleep 5; n=$((n+1)); done
  grep -q '^\[pi-spawn\] exit=0$' "$L" && echo ok || echo "failed-or-still-running: $(tail -1 "$L" 2>/dev/null)"
  ```
  The wait loop is not optional: `pi-spawn` returns as soon as tmux creates the session (`pi-spawn:148`), so the log does not exist yet and a `grep` issued immediately reports failure for a run that is fine. All of it must sit in the **same** Bash call or `$$` differs between the create and the check. Session names are global across the machine and `pi-spawn` refuses to clobber one, so a literal name collides with every other agent reading this file. `-l` lists, `-k NAME` kills, `-d DIR` sets the working directory.

**Chains and prompt templates** (`/scout-and-plan`, `/implement`, `/implement-and-review`) are `pi-delegate`'s material; reach for one before hand-rolling a three-harness pipeline. The one gotcha that bites a harness author: `{previous}` is a plain string replace, so type the token literally or the downstream step gets zero context, invents its input, and the chain still reports success.

**Applied doctrine** — the rules that bite hardest on cheap workers:

- One harness = **one Decide→Act arc** with its expected outcome written into the brief. Without a stated expectation every return looks like success. The return is an Observation to re-Orient on, not a conclusion to merge.
- **One LIVE candidate per fork.** Do not fan out one harness per competing hypothesis — that is a parallel deep dive with extra steps, and cheapness is not an exemption. Parallelism is legal across independent lanes of already-validated work.
- **Partition before dispatch.** Each brief names the files that worker owns *and* whose it must not touch, including shared helpers no lane claimed. Lanes assigned after worker one starts are assigned too late.
- **Calibrate the fan-out before you trust it.** Run the first few items against files whose answers you already know — that is what tells you whether this contract, on this task class, is fabricating or missing (step 7) while changing it is still cheap.
- **If most returns come back to you for judgment, the partition failed** — split harder rather than escalating the model.
- **Compact returns only.** The contract keeps the harness's reading out of your window; a return that pastes file contents has broken the contract even when it is correct — and at N-wide fan-out that is N times *your* context, not the harness's.
- **Isolation is structural.** A harness that writes gets its own git worktree as cwd (`-d DIR` for `pi-spawn`, mandatory; for `pi -p` there is no `-d`, so it is the Bash call's own cwd: `cd /abs/worktree && pi -p ...`), created before the spawn, with deps installed *inside* it — or the suite silently exercises the parent checkout's code and reports green. Prose in a harness is not enforcement.
- **Guard outward-facing actions mechanically** — commit, push and post bars belong in a pre-commit hook gated on an env var you set. **Stop and ask Carson** before: pushing to a remote, merging anything, deleting or overwriting outside the named lane, changing collaborator or org settings, spending money, or sending anything outward-facing. A harness never self-authorizes past a guard addressed to a human, and a denied worker never hands the blocked action to a sibling.
- **Every return carries its evidence as required contract keys**: the claim, the exact command that proves it with real output, and what was *not* exercised. Optional fields are the first thing a cheap model drops.
- **A fix is verified by someone other than its author.** Spawn a fresh harness with no shared context, ideally a different model, and tell it that falsifying beats blessing.
- **The write-up is its own turn.** Workers finish the work and drop the trailing non-code step. Send a second dispatch containing only the write-up ask, the exact command, and the report-back requirement.
- **Re-run rather than trust.** $0.00034 per single-file dispatch, so the cheapest way to resolve "is this return real" is to run it again and diff.
- **Fan-out completes when every input has a result or a named failure.** Retry each failure once, then report which inputs are missing — never synthesize over a silent gap (`fw-delegate` rule 4).

## Failure modes

| Symptom you would actually see | Cause | Fix |
|---|---|---|
| The call never returns; **stdout and stderr are both 0 bytes**. Measured at 10 min and again at 3 min on the same command | `pi -p` does not exit while its stdin is an open pipe. Not volume, not the provider, not batch width | Append `< /dev/null` to every dispatch — the same command returned rc=0 in 5s with 1.6MB. Bound it with `perl -e 'alarm 120; exec @ARGV' pi -p ...` |
| A Bash call is killed at the timeout and the redirected files are empty | Redirection recovers a *timeout*, never a *stall* — a stalled call produced nothing to redirect | `< /dev/null` for the stall; `perl` alarm (rc=142) so you learn it stalled instead of guessing; keep the redirect for the volume |
| Every worker in a batch returns zero bytes at once | A client-side stall, **not** auth and **not** throttling — measured while the Fireworks API was verifiably healthy. `~/.pi/agent/auth.json` holds **no Fireworks credential** (stale anthropic OAuth only), so inspecting it tells you nothing | Confirm liveness with the `curl` status probe against `api.fireworks.ai` and `$FIREWORKS_API_KEY`; then fix stdin. Do **not** cap batch width — the wide batches were the healthy ones |
| A **contract-perfect** answer with a **valid nonce**, an invented line number and invented quoted source | `-nt` / `--no-tools` was passed; no child process ran, and the nonce proves only that the harness text reached the model | Drop `-nt`; pass an explicit `--tools` list. Prove tool use with a `--mode json` `toolName` census or a token planted in the file, never with the nonce |
| A finding that is correctly located, accurately quoted, and prescribes a fix that **preserves the defect** | Cheap-model judgment error. Every gate in this skill passes it by construction — measured twice, 18 minutes apart, on the same live-network test | Read the `WRONG:` field of every non-escalated return, or route it to a second differently-prompted checker. Budget that reading as part of the sweep |
| `grep -L '^NONCE: '` flags a worker that escalated correctly | An `ESCALATE:`-and-stop escape hatch replaces the whole output, so `NONCE:` and `ESCALATE:` were mutually exclusive | Use the `NONCE:`-first + required `STATUS: OK\|ESCALATE` + `REASON:` contract; check by parsing `STATUS:`, so every branch carries the nonce |
| Every key present, compliance check passes, but `FIX:` (or another field) begins `ESCALATE:` | The escape hatch competed with the rigid format and lost; `grep '^ESCALATE:'` cannot see a mid-line token | Make the exit a required field, not a mode switch; parse `^STATUS: ` |
| `STATUS: ESCALATE` on a file that does contain a real defect | The escalation-friendly contract under-reports — measured on the sibling substrate, where the permissive contract found the same seeded defect the `STATUS:` contract declined | Re-run that item under the permissive contract; never file an escalation as a clean result; calibrate on known-answer files first |
| One run escalates, another on the identical file answers confidently and correctly | Run-to-run variance, **not** an underspecified brief | Re-run once before acting on any single escalation; change the brief only if it escalates twice |
| A sweep brief forces you to invent a symptom per file | The symptom-driven bugfind template applied to a "find defects we haven't found yet" sweep | Use the no-symptom variant: defect-class predicate plus an ESCALATE trigger on "zero, or two equally defensible" |
| Nothing in the sweep notices that file A's test asserts file B's buggy behaviour | `Read only the file named in the task` + `Report exactly one defect` — correct fan-out defaults with this exact cost | Plan a second pass with a two-file brief, or do the cross-file reasoning yourself |
| `pgrep -lf 'pi -p'` reports live workers that do not exist | `-f` matches every `/bin/zsh -c …` wrapper whose command string contains the flags — measured 4 phantom workers against zero real ones | `pgrep -f <harness-file>.md` for inline runs; `pi-spawn -l` or `tmux has-session -t pi-<name>` for detached, which `pgrep` cannot see at all |
| `EPERM ... mkdir '/Users/kai/.pi/agent/settings.json.lock'`, or `mkdir: /Users/kai/.pi/agent/harnesses: Operation not permitted` | The sandbox denies writes under `~/.pi`; not a broken install | `dangerouslyDisableSandbox: true` on every Bash call touching `~/.pi` |
| The Write tool fails writing the harness file | `~/.pi` is outside the write allowlist (cwd, `$TMPDIR`, `/tmp/claude`) | `cat > "$H" <<'EOF'` heredoc inside an unsandboxed Bash call |
| Fluent, contract-free prose, no `NONCE:` line, exit 0 | The `--append-system-prompt` path did not exist, so pi appended the path **as literal text** (`resource-loader.js:15-28`) | `test -s "$H"` in the same Bash call as the dispatch — mandatory for any harness with `edit`/`write`, since the nonce only tells you afterwards; never build the path from `$$` |
| Contract-shaped output, right diagnosis, only the final line missing | The model truncated the tail — the harness DID load | Put `NONCE:` first; do not go path-hunting |
| HTTP 400 `Invalid reasoning effort: none`, **or** a silent stall with no error at all | `--thinking off` maps to reasoning effort `none`; rejected on `gpt-oss-120b` (measured), accepted on `qwen3p7-plus`, `minimax-m3`, `deepseek-v4-flash` (measured). One lane saw the rejection present as a stall, not a message | Omit `--thinking off` unless you have probed that exact model |
| The parent cannot find the `subagent` tool when you asked for parallel tasks | `-ne` disabled extension discovery, **or** `--tools` excluded it — the allowlist filters extension tools too | Drop `-ne` on the delegating parent AND pass `--tools ...,subagent`; keep `-ne` on the leaves |
| `Unknown agent:` from a parallel `subagent` call | `{tasks:[...]}` takes `{agent, task}` — agent *names*, not harness paths | Promote the harness to `~/.pi/agent/agents/<name>.md`, or fan out with independent `pi -p` processes |
| A detached run ignores the harness entirely | `pi-spawn` forwards only `-p --model -n <task>` (`pi-spawn:162`) | Fold the harness into the task text, promote it to an agent file, or dispatch inline |
| A detached session and its log are named `c`, `s`, `e` or `t` | Strip flags placed before the task string are eaten by `pi-spawn`'s `getopts ":m:d:n:k:lh"` (`pi-spawn:42`): `-nc` parses as `-n c` | Pass only `-m -d -n -k -l -h` before the task, nothing after it; fold strip semantics into the task text |
| `pi-spawn: unknown option --` and exit 2 | A `--`-style long flag placed before the task string (`pi-spawn:50`) | Same fix: `pi-spawn` takes only its own short flags |
| A detached run edits a file the task never named | `pi-spawn` always gets the full `read, bash, edit, write` set and cannot be made read-only | `-d <throwaway dir or git worktree>` on **every** `pi-spawn` dispatch, unconditionally |
| A detached run picks up project instructions or skills you stripped inline | `pi-spawn` cannot pass `-nc -ns -ne --no-session`; AGENTS.md/CLAUDE.md discovery and skills load, and the session persists | Assume ambient context is on; make the task text survive it, or dispatch inline |
| A detached run lands on a model you did not choose | `DEFAULT_MODEL="${PI_SPAWN_MODEL:-fireworks/gpt-oss-120b}"` (`pi-spawn:10`) — environment-dependent | Always pass `-m` explicitly |
| `grep -q '^\[pi-spawn\] exit=0$'` reports failure immediately after spawning | `pi-spawn` returns as soon as tmux creates the session (`pi-spawn:148`); the log does not exist yet | Poll with the `until grep -q '^\[pi-spawn\] exit=' ...` loop before judging |
| A detached run "looks done" because the log has output | Output present is not exit status | `grep -q '^\[pi-spawn\] exit=0$' ~/.pi/agent/logs/<name>.log` |
| A downstream chain step invents its input while the chain reports success | `{previous}` is a plain string replace and the token was never typed | Type `{previous}` verbatim; verify the handoff with `--mode json` |
| `ENOENT: no such file or directory`, then the agent self-corrects | A relative path assembled from the wrong base directory | Absolute paths in the task string, always |
| A `--mode json` read hangs a long Bash call | Two separate causes: stdin inheritance (0 bytes, above) and sheer volume — **1.6MB / 613 lines** measured on Fireworks for one trivial file, ~755KB on another lane, versus 289KB locally | `< /dev/null` for the hang, redirect to a file for the volume, then grep the file |
| Tool census looks clean but the run asked a question or delegated | `grep -o '"toolName":"[a-z]*"'` drops names with `_`, digits or dashes | Use `"[^"]*"`, and keep `ask_question` out of the allowlist |
| Output drifts into prose or invents extra keys | Contract stated with no worked example | Add one input→exact-output example per `STATUS` value inside the harness |
| A citation quotes its source line perfectly but points at the wrong occurrence | Identical lines (copy-pasted guards, repeated error handling) | `sed -n '<N>p'`, and require the `ENCLOSING:` key to be unique |
| Fewer output files than inputs, no error anywhere | Two inputs shared a `basename` and the second overwrote the first | Index the output filenames (`out-$i-...`) |
| Output files from a previous batch or another session read as this batch's results | A hardcoded `$OUT` with `$i` names that restart at 1 every batch | Scope `$OUT` per batch: `.../harness-runs/$(date +%Y%m%d-%H%M%S)-$$` |
| A new agent has more power than intended, or spawns its own children | `tools:` omitted grants everything including `subagent`, no depth guard | Write the allowlist explicitly |
| A listed tool never gets used | The name matches no built-in and no loaded extension tool; invalid names are silently not forwarded | Correct the name; confirm extension tools are reachable (no `-ne`) |
| `pi-spawn` refuses to start | tmux session names are global across the machine and it will not clobber | Unique `-n` (`task-$$` in the same Bash call); `~/.pi/agent/bin/pi-spawn -l` |
| One wasted round trip on a refusal | `agentScope` escalated to `project`/`both`; the confirm dialog needs a UI headless runs lack (`extensions/subagent/index.ts:509`) | Leave `agentScope` at `"user"` — never pass it |
| Every `claude-*` call 400s | Subscription auth conflict | Use a Fireworks model |

## Reuse and promotion

Promote a harness once it has earned it: dispatched at least twice, both returns passing their spot-check — **or immediately, when the only route to the fan-out you need is `subagent`'s `{tasks:[...]}` form**, in which case the first parallel batch is those two spot-checks and you verify every row of it. Move the body into `~/.pi/agent/agents/<name>.md` — **user scope only**, never a repo `.pi/agents/`, because project scope is hard-refused headless.

```markdown
---
name: my-agent
description: One line — what it does, and the one thing it must never do.
tools: read, grep, find, ls
model: fireworks/gpt-oss-120b
---
Body: the single responsibility, the rules, the guardrails, the nonce-first
`STATUS:`-bearing output contract, and one worked example per STATUS value.
```

Once promoted it is callable by name through the `subagent` tool from a parent pi session — the only route in, since there is no `--agent` flag. The parent must keep extensions on (no `-ne`) **and** list `subagent` in its own allowlist, or the promoted agent is unreachable with no error pointing at the allowlist. Record it in `pi-delegate`'s roster table so the next session finds it, and per CLAUDE.md copy it into `/Users/kai/Desktop/projs/skills/` and push.

## Reference

Roster, `pi-spawn` flags, prompt templates and chains: skill `pi-delegate`. Operator manual: `~/.pi/agent/README-delegation.md` (mirrored at `/Users/kai/Desktop/projs/skills/pi-delegation/`) — read it before changing a roster agent's allowlist or model, and note its own warning that none of its timings are rigorously benchmarked. No-tools one-shot text work: `fw-delegate`. Same harness on your own GPU, zero marginal cost, serial queue: `scoped-harness-local` — read as a pair with this file; the contract shape, the escalation cost table and the stdin stall are shared findings. Fan-out wider than this file covers — phase caching, `{scriptPath, resumeFromRunId}` replay, supervision probes: `frontier-orchestrator`.
