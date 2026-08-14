#!/usr/bin/env python3
"""EXP-11 spend reader: sum output tokens from Claude Code session logs
into the loop ledger's spend_estimate.

Source: ~/.claude/projects/<project-slug>/<session-id>.jsonl — assistant
records carry message.usage.output_tokens. The same message id appears
multiple times (streamed updates), so we dedupe by message.id keeping the
LAST occurrence; naive summing double-counts ~2x.

Usage:
  spend_reader.py --session <id> [--project-dir DIR] [--ledger ledger.json]
  spend_reader.py --all [--project-dir DIR] [--ledger ledger.json]

Prints the deduped output-token total. With --ledger it records the reading
via ledger.py's `tick` verb, which stores the DELTA since the previous reading
as one iteration in spend_history (the session total only ever grows, so
comparing it against a per-iteration norm trips on duration, not waste).
`--total` restores the legacy set-spend write.
"""
import argparse, glob, json, os, subprocess, sys

# Claude Code slugs the project root by replacing "/" with "-".
# Derived from cwd so the tool is portable; override with --project-dir.
DEFAULT_DIR = os.path.expanduser(
    "~/.claude/projects/" + os.getcwd().replace("/", "-"))

def session_output_tokens(path):
    per_msg = {}
    anon = 0
    with open(path) as f:
        for line in f:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            m = o.get("message") or {}
            u = m.get("usage") or {}
            if "output_tokens" not in u:
                continue
            mid = m.get("id")
            if mid is None:
                anon += u["output_tokens"]  # no id: count each occurrence
            else:
                per_msg[mid] = u["output_tokens"]  # last occurrence wins
    return sum(per_msg.values()) + anon

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", default=DEFAULT_DIR)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--session", help="session id (basename without .jsonl)")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--ledger", help="ledger.json to update")
    ap.add_argument("--total", action="store_true",
                    help="write the cumulative total via set-spend (legacy) "
                         "instead of recording a per-iteration delta via tick")
    ap.add_argument("--ledger-cli", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ledger.py"))
    a = ap.parse_args()

    if not os.path.isdir(a.project_dir):
        print(f"project dir not found: {a.project_dir} — pass --project-dir; "
              f"refusing to report 0 spend from a missing log dir",
              file=sys.stderr)
        return 6

    if a.session:
        paths = [os.path.join(a.project_dir, a.session + ".jsonl")]
    else:
        paths = sorted(glob.glob(os.path.join(a.project_dir, "*.jsonl")))

    total = 0
    for p in paths:
        try:
            t = session_output_tokens(p)
        except OSError as e:
            print(f"skip {p}: {e}", file=sys.stderr)
            continue
        total += t
        if a.all:
            print(f"{os.path.basename(p):55s} {t:>10d}")
    print(f"TOTAL output_tokens: {total}")

    if a.ledger:
        verb = "set-spend" if a.total else "tick"
        r = subprocess.run([sys.executable, a.ledger_cli, "--ledger",
                            a.ledger, verb, str(total)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            return r.returncode
        print(f"ledger updated: {r.stdout.strip()}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
