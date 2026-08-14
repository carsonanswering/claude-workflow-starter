#!/usr/bin/env python3
"""Render Open Items dashboard from items.json into out/open-items.html.

items.json is the curated source of truth (edited by the /open-items skill turn).
Schema: {"updatedAt": ms, "items": [{"id", "title", "section": you|ready|idea|blocked,
"repo", "note", "effort", "blocker", "prompt"}]}
"""
import json, time
from pathlib import Path

SKILL = Path(__file__).resolve().parent
OUT = SKILL / "out" / "open-items.html"


def main():
    data = json.loads((SKILL / "items.json").read_text())
    data["updatedAt"] = int(time.time() * 1000)
    tpl = (SKILL / "template.html").read_text()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(tpl.replace("/*__DATA__*/null", json.dumps(data)))

    url = ""
    sf = SKILL / "state.json"
    if sf.is_file():
        try:
            url = json.loads(sf.read_text()).get("artifactUrl", "")
        except Exception:
            pass
    secs = {}
    for it in data["items"]:
        secs[it["section"]] = secs.get(it["section"], 0) + 1
    print(f"items={len(data['items'])} {secs} out={OUT} url={url or 'UNSET'}")


if __name__ == "__main__":
    main()
