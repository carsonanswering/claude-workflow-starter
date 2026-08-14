# Outreach drafting

**Run the verdict gate (SKILL.md step 4) on every factual sentence before it is written into a template.** A draft is filled with claims that already carry a ledger id or a claim-verifier verdict — never with claims collected while writing and checked afterwards, which is how a false sentence gets laundered into a send.

## Route to the right template

The email skeletons already exist in `/Users/kai/projs/answering-raise/templates/` and are enforced by `bin/gate.py`. Use them; do not re-invent a shape here.

| Situation | Template |
|---|---|
| No prior contact and no path in (`warm_score == 0`) | `templates/cold.md` |
| Step 2 found a warm path — the mail goes to the connector, not the investor | `templates/intro-request.md` |
| The one permitted second touch, day 5, in-thread | `templates/followup.md` |

`core/scoring.py:template_for` routes a warm prospect to the intro request automatically: cold-emailing someone you already have a path to is strictly worse than asking for the intro.

## Short-form skeleton (DM, X reply, LinkedIn note)

Not covered by the email templates, and the only shape drafted here. Same gate, tighter budget.

```
{Hook — one clause naming something they published or funded, with a date.
Must resolve to a live URL you fetched.}

{One sentence on what Answering is, in their vocabulary. Exactly one
verified ledger claim id.}

{The ask — a reply, not a meeting. "Worth a longer note?" beats a calendar
link in a DM.}
```

Bounds: 45 words or fewer, one claim, no link on the first message, no amount or terms. A DM that reads like a forwarded cold email gets the same fate as one.

## Bars that hold across every shape

- **No amount, valuation, cap, or terms in any outbound message.** Stating them in mass cold outreach is arguably general solicitation and risks the 506(b) exemption the round relies on. Ask for a conversation instead.
- **Exactly one factual claim about Answering per message**, mapped to a `verified` id in `claims/ledger.json`. Every extra claim is another chance to assert something that is not true yet.
- **Every personalization hook resolves to a live, dated URL you fetched.** A 404 is the shape a hallucinated source takes.
- **Two touches maximum, ever.** Any reply suppresses all follow-ups; `core/journal.py:touch_count` is the authority, not a state file.
- **A failing draft is never rewritten to pass.** It goes to `data/drafts/held/` with its reasons, and the fix is to correct the claim or cut the sentence.

## Before anything queues

Run the truth gate over the drafts:

```bash
cd /Users/kai/projs/answering-raise
python3 bin/gate.py --all              # denylist, claim mapping, hook resolution, adversarial judge
python3 bin/gate.py --all --no-judge   # checks 1-3, offline
```

The judge fails closed — a judge that cannot run holds the draft rather than releasing it.

Then stop. Sending, adding a target to the send pipeline, and loosening the ledger to let a draft through are Carson's calls, and a gate that passed is not permission to send.
