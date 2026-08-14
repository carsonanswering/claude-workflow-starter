#!/usr/bin/env python3
"""Defensive result-ingestion parse ladder (loop doctrine, experiment 4).

Ladder:
  1. json.loads on the raw payload.
  2. On failure: html.unescape the payload, retry json.loads.
  3. On failure: scan the journal .jsonl bottom-up, return the last valid JSON line.
  4. Else: exit 2.

Usage: ingest.py PAYLOAD_FILE [JOURNAL_JSONL]
Prints the recovered object as canonical JSON on stdout.
Exit codes: 0 = recovered, 2 = unrecoverable, 3 = usage error.
"""
import html
import json
import sys


def ingest(payload, journal_path):
    # Rung 1: parse as-is. Ordering matters: valid JSON containing literal
    # entities (e.g. "&quot;") must be returned untouched, never unescaped.
    try:
        return json.loads(payload), "rung1-json"
    except (json.JSONDecodeError, ValueError):
        pass

    # Rung 2: unescape-then-retry, only after raw parse failed.
    try:
        return json.loads(html.unescape(payload)), "rung2-unescape"
    except (json.JSONDecodeError, ValueError):
        pass

    # Rung 3: last valid JSON line of the journal.
    if journal_path:
        try:
            with open(journal_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            lines = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line), "rung3-journal"
            except (json.JSONDecodeError, ValueError):
                continue

    return None, "exhausted"


def main(argv):
    if len(argv) < 2 or len(argv) > 3:
        print("usage: ingest.py PAYLOAD_FILE [JOURNAL_JSONL]", file=sys.stderr)
        return 3
    with open(argv[1], "r", encoding="utf-8") as f:
        payload = f.read()
    journal = argv[2] if len(argv) == 3 else None
    obj, rung = ingest(payload, journal)
    if rung == "exhausted":
        print("ingest: unrecoverable payload", file=sys.stderr)
        return 2
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))
    print(f"ingest: recovered via {rung}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
