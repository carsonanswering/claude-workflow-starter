#!/usr/bin/env python3
"""Loop ledger v0 (EXP-05/EXP-11).

JSON ledger: {iteration, tasks:[{id,status,surfaced_at}], failed_actions:[],
              fingerprints:{}, spend_estimate}
Verbs: claim | complete | block | record-failure | check | set-spend | show

Concurrency: every read-modify-write holds an exclusive flock on
<ledger>.lock; writes go to a temp file in the same dir then os.replace
(atomic on POSIX), so a kill at any point leaves either the old or the
new complete ledger, never a torn one.

Exit codes:
  0  ok / claim won / check passed (verdict ok)
  3  claim lost (task already claimed/completed)
  4  check refused: identical failed action already recorded
  5  usage error / unknown task
 10  check verdict: degrade (spend >= soft threshold)
 11  check verdict: pause  (spend >= hard threshold)
"""
import argparse, fcntl, hashlib, json, os, statistics, sys, tempfile, time

EMPTY = {"iteration": 0, "tasks": [], "failed_actions": [],
         "fingerprints": {}, "spend_estimate": 0, "spend_history": []}

def _fp(action, params):
    blob = json.dumps({"action": action, "params": params}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()

class Ledger:
    def __init__(self, path):
        self.path = path
        self.lockpath = path + ".lock"

    def __enter__(self):
        self._lockfd = os.open(self.lockpath, os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(self._lockfd, fcntl.LOCK_EX)
        try:
            with open(self.path) as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = json.loads(json.dumps(EMPTY))
        return self

    def write(self):
        d = os.path.dirname(os.path.abspath(self.path)) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".ledger-")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self.data, f, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)  # atomic
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def __exit__(self, *exc):
        fcntl.flock(self._lockfd, fcntl.LOCK_UN)
        os.close(self._lockfd)
        return False

    def task(self, tid):
        for t in self.data["tasks"]:
            if t["id"] == tid:
                return t
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="ledger.json")
    sub = ap.add_subparsers(dest="verb", required=True)
    for v in ("claim", "complete", "block"):
        p = sub.add_parser(v); p.add_argument("task_id")
        if v == "block":
            p.add_argument("--reason", default="")
    p = sub.add_parser("record-failure")
    p.add_argument("action"); p.add_argument("params_json")
    p = sub.add_parser("check")
    p.add_argument("--action"); p.add_argument("--params")
    p.add_argument("--ceiling", type=float, default=None,
                   help="absolute session output-token ceiling; at or above "
                        "it, PAUSE (exit 11)")
    p.add_argument("--iter-mult", type=float, default=3.0,
                   help="DEGRADE (exit 10) when the newest iteration's delta "
                        "reaches this multiple of the median of THIS loop's "
                        "prior iterations")
    p.add_argument("--min-history", type=int, default=3,
                   help="prior iterations required before a rate verdict")
    p.add_argument("--baseline", type=float, default=None,
                   help="DEPRECATED: compares the SESSION TOTAL against a "
                        "per-iteration norm — trips on duration, not waste. "
                        "Use --ceiling with --iter-mult.")
    p.add_argument("--soft-mult", type=float, default=2.0)
    p.add_argument("--hard-mult", type=float, default=4.0)
    p = sub.add_parser("set-spend"); p.add_argument("tokens", type=float)
    p = sub.add_parser("tick", help="record a CUMULATIVE session total; stores "
                                    "the per-iteration delta in spend_history")
    p.add_argument("tokens", type=float, help="cumulative session output tokens")
    p = sub.add_parser("gate", help="change-gate a repo fingerprint (see loop-fp.sh)")
    p.add_argument("repo"); p.add_argument("fingerprint")
    p.add_argument("--no-update", action="store_true",
                   help="compare only; do not store the new fingerprint")
    sub.add_parser("show")
    a = ap.parse_args()

    with Ledger(a.ledger) as led:
        d = led.data
        if a.verb == "claim":
            t = led.task(a.task_id)
            if t and t["status"] in ("claimed", "completed"):
                print(f"REFUSED claim {a.task_id}: already {t['status']}",
                      file=sys.stderr)
                return 3
            if t is None:
                t = {"id": a.task_id}; d["tasks"].append(t)
            t["status"] = "claimed"
            t["surfaced_at"] = t.get("surfaced_at") or time.time()
            t["claimed_at"] = time.time()
            t["claimed_by"] = os.getpid()
            led.write()
            print(f"claimed {a.task_id} by pid {os.getpid()}")
            return 0
        if a.verb in ("complete", "block"):
            t = led.task(a.task_id)
            if t is None:
                print(f"unknown task {a.task_id}", file=sys.stderr); return 5
            t["status"] = "completed" if a.verb == "complete" else "blocked"
            if a.verb == "block":
                t["reason"] = a.reason
            led.write(); print(f"{a.verb} {a.task_id}"); return 0
        if a.verb == "record-failure":
            params = json.loads(a.params_json)
            d["failed_actions"].append(
                {"action": a.action, "params": params,
                 "fingerprint": _fp(a.action, params), "at": time.time()})
            led.write(); print(f"recorded failure of {a.action}"); return 0
        if a.verb == "set-spend":
            d["spend_estimate"] = a.tokens
            led.write(); print(f"spend_estimate={a.tokens}"); return 0
        if a.verb == "show":
            print(json.dumps(d, indent=1)); return 0
        if a.verb == "tick":
            prev = d.get("spend_estimate", 0) or 0
            total = a.tokens
            delta = max(0.0, total - prev)   # session switch/reset -> 0, never negative
            d["iteration"] = d.get("iteration", 0) + 1
            d.setdefault("spend_history", []).append(
                {"iteration": d["iteration"], "delta": delta,
                 "total": total, "at": time.time()})
            d["spend_estimate"] = total
            led.write()
            print(f"iteration {d['iteration']}: +{delta:,.0f} output tokens "
                  f"(session total {total:,.0f})")
            return 0
        if a.verb == "gate":
            fps = d.setdefault("fingerprints", {})
            prev = fps.get(a.repo)
            if prev == a.fingerprint:
                print(f"UNCHANGED {a.repo} {a.fingerprint[:12]}")
                return 20
            if not a.no_update:
                fps[a.repo] = a.fingerprint
                led.write()
            was = "new" if prev is None else prev[:12]
            print(f"CHANGED {a.repo} {was} -> {a.fingerprint[:12]}")
            return 0
        if a.verb == "check":
            # 1) failed-action re-attempt refusal
            if a.action is not None:
                fp = _fp(a.action, json.loads(a.params or "{}"))
                for fa in d["failed_actions"]:
                    if fa["fingerprint"] == fp:
                        print(f"REFUSED: action '{a.action}' with identical "
                              f"params already failed at {fa['at']}",
                              file=sys.stderr)
                        return 4
            # 2) absolute ceiling -> PAUSE
            spend = d.get("spend_estimate", 0)
            if a.ceiling is not None:
                if spend >= a.ceiling:
                    print(f"PAUSE: session spend {spend:,.0f} >= ceiling "
                          f"{a.ceiling:,.0f} — stop claiming, finish in-flight "
                          f"verification, queue the rest, notify")
                    return 11
                # 3) per-iteration rate anomaly -> DEGRADE
                hist = [h["delta"] for h in d.get("spend_history", [])]
                prior = hist[:-1]
                if len(prior) >= a.min_history:
                    last, med = hist[-1], statistics.median(prior)
                    if med > 0 and last >= a.iter_mult * med:
                        print(f"DEGRADE: iteration {len(hist)} burned "
                              f"{last:,.0f} >= {a.iter_mult}x this loop's "
                              f"prior-iteration median {med:,.0f} — force "
                              f"fw/oss tiers")
                        return 10
                    print(f"OK: iteration {last:,.0f} vs prior median "
                          f"{med:,.0f}; total {spend:,.0f}/{a.ceiling:,.0f}")
                else:
                    print(f"OK: {len(prior)} prior iteration(s) < "
                          f"--min-history {a.min_history}; no rate verdict "
                          f"yet; total {spend:,.0f}/{a.ceiling:,.0f}")
                return 0

            # legacy (deprecated) session-total-vs-per-iteration-norm verdict
            if a.baseline is not None:
                print("WARNING: --baseline compares the SESSION TOTAL to a "
                      "per-iteration norm; it trips on duration, not waste. "
                      "Use --ceiling/--iter-mult.", file=sys.stderr)
                if spend >= a.hard_mult * a.baseline:
                    print(f"PAUSE: spend {spend} >= {a.hard_mult}x baseline "
                          f"{a.baseline} — pause-and-notify, queue for user")
                    return 11
                if spend >= a.soft_mult * a.baseline:
                    print(f"DEGRADE: spend {spend} >= {a.soft_mult}x baseline "
                          f"{a.baseline} — force fw/oss tiers")
                    return 10
                print(f"OK: spend {spend} < {a.soft_mult}x baseline {a.baseline}")
            else:
                print("OK: no prior failure recorded for action")
            return 0
    return 5

if __name__ == "__main__":
    sys.exit(main())
