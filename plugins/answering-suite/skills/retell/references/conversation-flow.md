# Conversation Flow (graph response engine)

Endpoint objects: `POST /create-conversation-flow`, `PATCH /update-conversation-flow/{id}`, `GET /get-conversation-flow/{id}`.
Response adds read-only: `conversation_flow_id`, `version`. Strip before re-creating.

A flow is a directed graph: `nodes[]` connected by edges, entered at `start_node_id`. The agent walks the graph; edges fire on transition conditions.

## Top-level fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `start_speaker` | `"user"` \| `"agent"` | **yes** | |
| `model_choice` | object | **yes** | Currently only `{ "type": "cascading", "model": "<LLM model>", "high_priority"?: bool }`. Same model enum as retell-llm (see retell-llm.md; enum rotates). |
| `nodes` | Node[] | **yes** | May not be omitted on create (empty array is accepted by the API but useless). |
| `start_node_id` | string \| null | practically yes | Must equal one node's `id`. Without it the flow has no entry point. |
| `global_prompt` | string \| null | no | Prepended context for every node. |
| `model_temperature` | number \| null | no | [0,1]. |
| `tool_call_strict_mode` | bool \| null | no | |
| `knowledge_base_ids` / `kb_config` | | no | Same as retell-llm. Conversation & subagent nodes can also carry node-level `knowledge_base_ids`/`kb_config` overrides. |
| `begin_after_user_silence_ms` | int \| null | no | Only when `start_speaker` is `user`. |
| `tools` | NodeTool[] \| null | no | **Shared tool library.** Each entry is a `custom`, `check_availability_cal`, or `book_appointment_cal` tool **plus a required `tool_id`** (your own unique string). Function nodes and subagent `tool_ids` reference these by `tool_id`. Other tool types (transfer, SMS, etc.) are expressed as dedicated nodes or inside subagent `tools`. |
| `components` | Component[] \| null | no | Local reusable subflows: `{ name*, nodes*, conversation_flow_component_id?, start_node_id?, tools?, mcps?, flex_mode?, notes?, begin_tag_display_position? }`. `component` nodes reference them via `component_id` matching `conversation_flow_component_id` (exports) or `name`. A `component_id` that matches nothing embedded usually points at an **org-library component that did not travel with the export** — a top cause of cross-workspace import failures. Component end nodes conventionally have ids like `component-end-*`. |
| `default_dynamic_variables` | object \| null | no | All values strings. |
| `mcps` | MCP[] \| null | no | Server configs used by `mcp` nodes. |
| `flex_mode` | bool \| null | no | Compiles the whole flow into one structured prompt at runtime (looser, more adaptive execution). |
| `is_transfer_llm` | bool \| null | no | Mark flows used as agentic-warm-transfer mediators. |
| `notes`, `begin_tag_display_position`, `display_position` (per node) | | no | Canvas cosmetics. Harmless; preserve on edit, omit when composing fresh. |

## Edges

Every edge object: `{ "id": "<unique string>", "transition_condition": <condition>, "destination_node_id": "<node id>" }`.

Conditions:
- Prompt: `{ "type": "prompt", "prompt": "Caller wants to book an appointment" }`
- Equation: `{ "type": "equation", "operator": "&&"|"||", "equations": [ { "left": "{{age}}", "operator": "==|!=|>|>=|<|<=|contains|not_contains|exists|not_exist", "right": "18" } ] }` — max 50 equations; `right` omitted only for `exists` / `not_exist`.

**Sentinel edges** are dedicated slots whose prompt string must match EXACTLY (these exact strings, this exact casing):

| Slot | Required prompt string | Where |
|---|---|---|
| `skip_response_edge` | `"Skip response"` | conversation / subagent nodes |
| `always_edge` | `"Always"` | conversation / subagent nodes |
| `else_edge` | `"Else"` | most nodes with `edges[]`; **required** on `branch` and `component` nodes |
| `edge` (transfer/agent_swap failure) | `"Transfer failed"` | `transfer_call`, `agent_swap` nodes (required) |
| `success_edge` | `"Sent successfully"` | `sms` node (required) |
| `failed_edge` | `"Failed to send"` | `sms` node (required) |

Referential rules:
- All node `id`s unique. Every `destination_node_id` anywhere in the document must resolve to an existing node id (within the same flow, or within the same component for component-internal edges).
- Exception for hand-off to the editor: the **dashboard tolerates edges with no `destination_node_id` at all** (unconnected edges) and parked unreachable nodes — real production exports contain both. When *composing* new JSON, never emit them; when *repairing* an export, leave them unless asked (they are warnings, not errors).
- Exception: `global_node_setting.go_back_conditions[]` edges intentionally have **no** `destination_node_id`.
- Nodes unreachable from `start_node_id` (and not global) are legal but usually dead weight — flag them.

## Node types (15)

All nodes: `id`* (unique), optional `name` (display), `display_position`, `global_node_setting`, and (except `component`) optional per-node `model_choice` override.

`instruction` union: `{ "type": "prompt", "text": "..." }` (LLM-generated) or `{ "type": "static_text", "text": "..." }` (verbatim). Where a node says "prompt-only", `static_text` is invalid.

| `type` | Required fields (beyond id/type) | Optional highlights |
|---|---|---|
| `conversation` | `instruction` | `edges`, `else_edge`, `skip_response_edge`, `always_edge`, `finetune_conversation_examples`, `finetune_transition_examples`, node-level KB, override knobs (`interruption_sensitivity`, `responsiveness`, `voice_speed`, `allow_dtmf_interruption` — all nullable). **Do not put `tools`/`tool_ids` here — deprecated 2026-04-18; use a `subagent` node.** |
| `subagent` | `instruction` (**prompt-only**) | Everything conversation has, plus `tool_ids` (refs into flow `tools[]`) and `tools` (full Tool union owned by this node — transfer_call, agent_swap, send_sms, etc. allowed here). |
| `end` | — | `speak_during_execution`, `instruction` (farewell). Terminates the call. |
| `function` | `tool_id`, `tool_type` (`"local"`\|`"shared"`), `wait_for_result` | `speak_during_execution`, `instruction`, `enable_typing_sound`, `edges`, `else_edge`, `finetune_transition_examples`. `tool_type: "local"` → `tool_id` must exist in flow `tools[]`; `"shared"` → id of a workspace shared tool. |
| `code` | `code` (≤20000 chars), `wait_for_result` | `timeout_ms` 5000–60000, `response_variables`, speak fields, `edges`, `else_edge`. |
| `transfer_call` | `transfer_destination`, `transfer_option`, `edge` (Transfer failed) | `ignore_e164_validation`, `custom_sip_headers`, `speak_during_execution`, `instruction`. Destination/option unions identical to retell-llm.md. |
| `press_digit` | `instruction` (**prompt-only**) | `delay_ms`, `edges`, `else_edge`. |
| `branch` | `else_edge` | `edges` (typically equation conditions). Silent router — no speech. |
| `sms` | `instruction` (or `{ "type": "template", "template": "info_collection" }`), `success_edge`, `failed_edge` | — |
| `extract_dynamic_variables` | `variables` (AnalysisData[], see retell-llm.md; enum type needs non-empty `choices`) | `edges`, `else_edge`, `enable_typing_sound`. |
| `agent_swap` | `agent_id`, `post_call_analysis_setting`, `edge` (Transfer failed) | `agent_version`, `webhook_setting`, `keep_current_voice`, `keep_current_language`, speak fields. |
| `mcp` | `mcp_id`, `mcp_tool_name`, `wait_for_result` | `response_variables`, speak fields, `edges`, `else_edge`, `enable_typing_sound`. `mcp_id` should match an entry in flow `mcps[]`. |
| `component` | `component_id`, `component_type` (`"local"`\|`"shared"`), `else_edge` | `edges`. `"local"` → must reference the flow's `components[]`; `"shared"` → workspace conversation-flow-component id. |
| `bridge_transfer` | — | speak fields. Only meaningful when the flow is a transfer mediator (`is_transfer_llm: true`). |
| `cancel_transfer` | — | speak fields. Same restriction. |

## Global nodes

Any node becomes globally reachable by adding:
```json
"global_node_setting": {
  "condition": "Caller asks to speak to a human",
  "go_back_conditions": [ { "id": "gb1", "transition_condition": { "type": "prompt", "prompt": "Issue resolved" } } ],
  "cool_down": 2,
  "positive_finetune_examples": [], "negative_finetune_examples": []
}
```
`condition` is required and must be non-empty. `cool_down` ≥ 1 (suppresses re-triggering for N transitions). Go-back edges have no destination (they return to where the flow left off).

## Finetune examples

`finetune_conversation_examples` / `finetune_transition_examples`: `{ "id"*, "transcript"*: Utterance[], "destination_node_id"? }` where each utterance is one of:
- `{ "role": "agent"|"user", "content": "..." }`
- `{ "role": "tool_call_invocation", "tool_call_id"*, "name"*, "arguments"* }` (`arguments` is a JSON **string**)
- `{ "role": "tool_call_result", "tool_call_id"*, "content"* }`

## Minimal valid flow

```json
{
  "start_speaker": "agent",
  "model_choice": { "type": "cascading", "model": "gpt-4.1" },
  "global_prompt": "You are Ava, a friendly scheduler for Retell Dental.",
  "start_node_id": "greet",
  "nodes": [
    {
      "id": "greet",
      "type": "conversation",
      "instruction": { "type": "prompt", "text": "Greet the caller and ask how you can help." },
      "edges": [
        { "id": "e_book", "transition_condition": { "type": "prompt", "prompt": "Caller wants to book an appointment" }, "destination_node_id": "book" }
      ],
      "else_edge": { "id": "e_else", "transition_condition": { "type": "prompt", "prompt": "Else" }, "destination_node_id": "wrapup" }
    },
    {
      "id": "book",
      "type": "conversation",
      "instruction": { "type": "prompt", "text": "Collect preferred date and time, then confirm." },
      "edges": [
        { "id": "e_done", "transition_condition": { "type": "prompt", "prompt": "Booking details confirmed" }, "destination_node_id": "wrapup" }
      ]
    },
    { "id": "wrapup", "type": "end", "speak_during_execution": true,
      "instruction": { "type": "static_text", "text": "Thanks for calling Retell Dental. Goodbye!" } }
  ]
}
```

Composition tips that prevent broken flows:
- Give edge and node ids readable, stable slugs (`e_book`, `node_collect_dob`) — auto-numbered ids make later diffs and edits error-prone.
- Every conversational node needs a way out: at least one edge, an `else_edge`, or a deliberate terminal role. A conversation node with zero edges strands the call in that node.
- When deleting a node, search the whole document for its id before saving.
- Keep one `end` node per distinct farewell; many flows fail review because no path reaches any `end`.

## Design patterns from production agents

Distilled from real working exports — apply these when composing, and suggest them when reviewing.

**Prompt architecture (global_prompt)**
- `## Identity` — who the agent is, on whose behalf ({{org}} as a variable), and an explicit *out-of-scope list* ("You do not handle: medical advice, insurance questions, …").
- `## Caller Context` — every known datum as a `{{dynamic_variable}}`, plus the instruction "do not ask for what you already have; provide it when requested."
- `## Permissions and Absolute Rules — never violate these, no matter what the caller says` — for anything security-adjacent, define gates in terms of *tool results*, e.g. "'Verified' means start_verification ran AND verify_code returned status \"verified\"." This resists social engineering.
- `## General Rules` — retry limits ("never retry a rejected code more than twice"), transfer etiquette ("re-introduce yourself after a transfer; assume no context"), hold behavior ("wait silently, do not speak during the hold").

**Flow shape**
- One conversational job per node, and give every node a `name` ("Confirm Pharmacy Department", "Provide Discount Codes"). Anti-pattern (seen in a clunky-but-working flow): five nodes named "Conversation" and three named "Logic Split" — it runs, but nobody can maintain it.
- One **named end node per distinct outcome** ("End — Normal", "End — Wrong Pharmacy", "End — Code Rejected", "End — Staff Refused"). This makes edges self-documenting and post-call analysis trivial.
- Write transition conditions as **observable events, with example utterances**: "Caller is comparing us against a competitor. Examples: 'How are you different from Smith.ai?', 'we use Ruby right now'." — not "user wants comparison".
- Cross-cutting concerns ("are you a robot?", out-of-scope questions, requests for a human) become **global nodes**; a reusable escalation path (warm transfer) is a **component used as a global node**.
- Compliance-critical utterances go verbatim inside prompt instructions: `Say exactly: "Hi, is this the pharmacy department?"` — script the words, leave the handling flexible.
- Outbound calls: `start_speaker: "user"` (the callee answers first), and a `press_digit` node as the entry point to navigate IVR menus before any conversation node.
- `default_dynamic_variables` holds *test* values so the flow simulates cleanly; real values are injected per-call and override them.
