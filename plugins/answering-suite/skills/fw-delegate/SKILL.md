---
name: fw-delegate
description: >-
  Delegate bulk stateless one-shot LLM work — summarizing, classifying, extracting, transforming, boilerplate, second opinions — to cheap Fireworks models via the `fw` CLI. Trigger phrases: "use fw", "delegate to fireworks", "offload this", "second opinion from deepseek".
---

# fw-delegate — cheap one-shot delegation

`fw` (in PATH) makes a single call to a Fireworks-hosted open model and prints the text response. Python stdlib, no proxy, needs `FIREWORKS_API_KEY` (in `~/.zshenv` — `source` it if the Bash env lacks it).

## Invocation

```bash
fw "prompt"                          # deepseek-v4-pro (default)
cat file | fw "prompt"               # stdin appended as <input> context
fw -m oss "prompt"                   # gpt-oss-120b — fast/cheapest
fw -s "system prompt" -j "prompt"    # system prompt + forced JSON object
fw -t 500 --temp 0.9 "prompt"        # max tokens / temperature
```

Model aliases: `ds` deepseek-v4-pro (default, reasoning, slower), `oss` gpt-oss-120b (mechanical tasks), `kimi` kimi-k2p6, `glm` glm-5p2. Full Fireworks IDs also accepted.

## When to delegate

Anywhere a one-shot call over text suffices — the description lists the shapes. Two that carry extra craft:

- Structured extraction (use `-j` + a schema in the system prompt)
- An *independent* second opinion on a design or diff — send the artifact, not your conclusion

## Route elsewhere instead

- Tool use, file edits, or repo-wide context → a `claude-oss -p` worker (read `/home/schmi/.claude/skills/oss-session/SKILL.md` — user-invoked, not reachable by skill name) or a Claude subagent; `fw` has no tools and sees only what you paste.
- Multi-step reasoning where an early error compounds → keep it inline, or cut it into single-step `fw` calls you check between.
- Decisions → yours. `fw` output informs.
- Tasks smaller than the Bash round trip → answer inline.

## Rules

1. Pick `oss` for mechanical work, `ds` only when quality matters — deepseek burns paid thinking tokens and is slower to first token (figures in `/home/schmi/.claude/skills/oss-session/SKILL.md`).
2. Treat output as untrusted draft: verify claims against the actual code/data before acting on them.
3. For JSON pipelines, always pass `-j` and validate the parse; retry once with the parse error appended on failure.
4. Fan-out is fine: loop `fw` over many files in one Bash call, collect results, synthesize yourself. The fan-out is done when every input has either a result or a named failure — retry each failure once, then report which inputs are missing rather than synthesizing over a silent gap.

## Failure modes

- `FIREWORKS_API_KEY not set` — prefix command with `source ~/.zshenv;`
- `HTTP 403: error code: 1010` — Cloudflare UA block; `fw` spoofs curl UA, so script was modified
- Full docs: `~/projs/open-sourced/README.md`
