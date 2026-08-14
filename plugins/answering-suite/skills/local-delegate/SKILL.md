---
name: local-delegate
description: >-
  Delegate one-shot LLM work to a local Ollama model via the `lo` CLI — private, offline, zero marginal cost, no rate limit. Trigger phrases: "delegate locally", "use the local model", "run this on ollama", "local delegate", "keep this on my machine", "offline".
---

# local-delegate — one-shot work that stays on the machine

`lo` (`/Users/kai/.local/bin/lo`) makes a single Ollama call and prints the assistant text. Python stdlib, no auth, talks to `http://localhost:11434` (`OLLAMA_HOST` overrides). Local sibling of `fw-delegate`: local wins on privacy, offline, zero marginal cost, and no rate limit — `fw` wins on quality.

## Invocation

```bash
lo "prompt"                                  # q = qwen3.6:27b-mlx (default)
cat file | lo "prompt"                       # stdin appended as <input> context
lo -m fast "prompt"                          # gemma4:latest — mechanical work
lo -s "system prompt" -j "prompt"            # system prompt + forced JSON object
lo -t 2000 --temp 0.4 --ctx 32768 "prompt"   # tokens / temperature / context
lo --think "prompt"                          # reasoning on (off by default, for speed)
lo --stats "prompt"                          # tok/s + token counts to stderr
lo --check                                   # preflight; --list for the roster
lo -i "prompt" < file.txt                    # read a redirected file (see below)
```

A pipe is read automatically; a *redirected* file needs `-i`. That asymmetry is deliberate: inside `while read line; do lo ...; done < inputs.txt` the loop's own file is on stdin, and draining it makes iterations 2..N vanish with a clean exit 0.

Models — measured on this machine, decode rate over real generations:

| alias | model | on disk | resident | warm | cold |
|---|---|---|---|---|---|
| `q`/`qwen` | qwen3.6:27b-mlx | 19GB | ~19GB @ctx16384 | ~29.5 tok/s | ~5s |
| `moe` | qwen3.6:35b-mlx | 21GB | 27GB | ~125 tok/s | 7–9s |
| `fast` | gemma4:latest | 9.6GB | ~10GB | ~100–107 tok/s | ~3.5s |
| `g`/`gemma` | gemma4:31b-mlx | 18GB | ~20GB | ~36–44 tok/s | ~6.6s |

Rates are steady-state decode over 25–250 token outputs; they fall on long generations as the KV cache grows, and outputs under ~10 tokens read high enough to be meaningless.

`q` is the 27B **dense** model — strongest per-token quality here (the 2026-08-02 local-models verdict picked it for coding) and the default when the task needs quality. It decodes ~4x slower than `moe`, the 35B-**A3B** MoE (~3B active params, ~125 tok/s): reach for `moe` when throughput dominates and the task is easy, `fast` for mechanical work / when RAM is tight / when cold start dominates; `g` is a dense fallback. Full ollama tags also accepted.

## The viability gate

`lo` sees only what you paste into it, and a 27B local model is materially weaker than what `fw` reaches. Run this gate before the Bash call; every line must read yes.

1. **Fits** — system + prompt + stdin under 24000 chars. `lo` enforces this one itself: over budget it exits `7` without calling the model. Split per-file or per-chunk rather than reaching for `--force`.
2. **Single step** — one transform over the pasted text: summarize, classify or label, extract to a schema, rewrite, translate, name things, draft boilerplate or a commit message.
3. **Cheaply verifiable** — you can eyeball the answer or check it mechanically.
4. **Cheap to be wrong** — a bad answer costs one retry, never corrupted work.

A `no` on any line routes the task elsewhere.

Two conditions make `lo` the right call even with `fw` available: text that should not leave the machine, and no network / no key / rate-limited / high fan-out where per-call cost matters.

## Route elsewhere instead

- Tools, file reads, or repo-wide context → a Claude subagent, or `pi-delegate` for a cheap agent with real tool access.
- Multi-step reasoning where an early error compounds → keep it inline, or cut it into single-step `lo` calls you check between.
- Quality matters more than privacy or cost and the network is up → `fw` (skill `fw-delegate`). This is the likeliest misroute.
- A wrong answer would silently corrupt work → not delegable at all.
- Smaller than the Bash round trip → answer inline.

## Rules

1. Default to `q`; add `--think` only when the answer needs reasoning, since it spends decode time.
2. Treat output as untrusted draft — verify against the real code or data before acting on it.
3. JSON pipelines: pass `-j`, validate the parse, retry once with the parse error appended.
4. Fan-out one input per call, in a loop. Batching many inputs into a single call is the tempting token-saving shape and it fails silently: measured on 48 commit messages, `fast` returned 26 labels for 48 inputs at exit `0`, drifted two positions so even those were misaligned, and used a fifth of its token budget — the model decided it was done, so no `-t` would have saved it. `q` managed 44 of 48, also exit `0`. Batching also biases each label toward its neighbours; the same line classified `docs` per-call and `fix` in every batch. Per-line costs ~0.4–0.6s on `fast` and was 12/12 and 48/48 correct. If you batch anyway, assert the output count equals the input count and treat a short count as failure, never as a partial result.
5. A fan-out is done when every input has either a result or a named failure — retry each failure once, then report which inputs are missing rather than synthesizing over the gap.
6. One caller at a time. Ollama serves a single GPU: concurrent `lo` calls — especially from several subagents at once — contend, and a second model loading mid-run evicts the first. Measured under contention, a cold call that normally costs 7–9s took over 300s. Delegating to `lo` from a fleet means routing those calls through one agent.
7. A resident `q` costs ~19GB (`moe` 27GB) with KV cache at the default `--ctx` on a 48GB machine, and the 15m default `keep-alive` will hold two models co-resident. `ollama ps` shows what is loaded; `--keep-alive 0` evicts after the call.

## Failure modes

Exit codes branch cleanly: `3` timeout, `4` empty output, `5` server unreachable, `6` model not installed, `7` input over budget or too large for `--ctx`, `8` output truncated, `1` other, `2` usage error.

- `3` on the first call of a session — a cold load into RAM. 7–9s from page cache, longer on the first load after a pull, and unbounded if another process holds the GPU. Retry, raise `--timeout`, or check `ollama ps`.
- `4` — retry with `--retry`, drop `-j`, or raise `-t` if the answer was cut off mid-thought.
- `5` — `ollama serve` is not running; `lo --check` confirms server, model, and thinking capability.
- `7` with "would silently discard the front" — the input needs a bigger window than `--ctx`. Ollama truncates from the front, so the instruction is what goes first; `lo` refuses rather than answer from a fragment. Raise `--ctx`, pass `--grow-ctx` to size it automatically, or split.
- `8` — generation stopped on the `-t` cap. Under `-j` the JSON is an unterminated fragment and the exit is non-zero; in prose you get the fragment plus a stderr warning. Raise `-t`.
