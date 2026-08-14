#!/bin/bash
# Rebuild the tracker dashboard from live GitHub state. Zero LLM calls.
# Prints one summary line; the caller publishes the `out` path.
set -e
LIVE=/Users/kai/projs/tracker-live
cd "$LIVE"
./build.sh >/dev/null 2>&1

URL=$(python3 -c "import json,sys;print(json.load(open('/Users/kai/.claude/skills/tracker-refresh/state.json')).get('artifactUrl','UNSET'))" 2>/dev/null || echo UNSET)

python3 - "$URL" <<'PY'
import json, sys, pathlib
d = pathlib.Path('/Users/kai/projs/tracker-live')
data = json.loads((d / 'viz-data.json').read_text())
wf = lambda i: any(l.startswith('wayfinder:') for l in i['l'])
openb = lambda i: [b['n'] for b in i['b'] if b['s'] == 'OPEN']
work = [i for i in data if i['s'] == 'OPEN' and not wf(i)]
flight = [i for i in data if i['s'] == 'OPEN' and i['a']]
ready = [i for i in work if not openb(i) and 'needs:carson' not in i['l']]
needs = [i for i in work if 'needs:carson' in i['l']]
print(f"open={len(work)} inflight={len(flight)} ready={len(ready)} needsyou={len(needs)} "
      f"out={d/'dashboard.html'} url={sys.argv[1]}")
PY
