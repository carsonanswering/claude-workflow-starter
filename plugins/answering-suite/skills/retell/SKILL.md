---
name: retell
description: Compose, edit, validate, import, and export Retell AI voice and chat agent JSON without schema inconsistencies. Use this skill whenever the user mentions Retell / RetellAI agents, Retell LLMs, conversation flows, single-prompt or multi-prompt phone agents, chat agents, agent JSON export/import, migrating agents between Retell workspaces or organizations, dashboard import failures, or "invalid request format" errors from api.retellai.com — even if they only paste a Retell agent JSON and ask for changes, or ask to "build a voice agent" on Retell without mentioning JSON.
---

# Retell Agent Composer

Build and edit Retell AI agent JSON that imports and creates cleanly on the first try. The single most common failure mode when composing Retell agents is a *structurally plausible* JSON that mixes fields from different resource types, uses the wrong discriminator pairing, or contains dangling references. This skill exists to prevent exactly that.

## The mental model (read this before writing any JSON)

Retell splits an agent into **two separate resources linked by ID**. Getting this wrong is the #1 source of inconsistencies.

```
┌─────────────────────────┐        ┌──────────────────────────────┐
│  AGENT                  │        │  RESPONSE ENGINE             │
│  (voice OR chat)        │───────▶│  (the "brain")               │
│                         │  by id │                              │
│  voice, language,       │        │  one of:                     │
│  webhooks, analysis,    │        │  • retell-llm  (single/multi │
│  telephony behavior     │        │    prompt: prompt + states)  │
│                         │        │  • conversation-flow (nodes  │
│  response_engine: {     │        │    + edges graph)            │
│    type, <id field>     │        │  • custom-llm (your own      │
│  }                      │        │    websocket server)         │
└─────────────────────────┘        └──────────────────────────────┘
```

- **Prompts, tools, states, nodes, `start_speaker`, `begin_message`, model choice, knowledge bases** live on the **engine**, never on the agent.
- **Voice, language, webhooks, voicemail/IVR handling, post-call analysis, data storage** live on the **agent**, never on the engine.
- A voice agent and a chat agent can share the same engine, but their agent-level field sets are different (see the consistency contract below).
- Creation order via API is always: **engine first, then agent** (the agent's `response_engine` must reference an existing engine id).

## Workflow

1. **Classify the request.** Voice or chat agent? Which engine type?
   - Simple, mostly-linear conversation, one persona → `retell-llm` with just `general_prompt` (single prompt).
   - Distinct phases with different rules/tools (qualify → book → confirm) → `retell-llm` with `states` (multi-prompt).
   - Strict branching call control, per-step tools, IVR/transfer logic, visual-canvas parity → `conversation-flow`.
   - User runs their own LLM server → `custom-llm` (engine is just a websocket URL; nothing else to compose).
2. **Read the matching reference file(s)** in `references/` before writing JSON — they contain the exact field tables, required flags, numeric ranges, and enum values distilled from the official OpenAPI spec:
   - `references/retell-llm.md` — single/multi-prompt engine: prompt, states, edges, all 13 tool types.
   - `references/conversation-flow.md` — flow engine: all 15 node types, edge rules, sentinel edges, components, global nodes, and **"Design patterns from production agents"** (read that section whenever composing a new flow, not just repairing one).
   - `references/voice-agent.md` — voice agent fields, ranges, voicemail/IVR, analysis.
   - `references/chat-agent.md` — chat agent fields **and the voice-vs-chat field split** (which fields are illegal on chat).
   - `references/import-export.md` — dashboard export bundles, API round-trips, cross-workspace migration, secret scrubbing. Read this whenever the task involves an exported file, importing, cloning, or moving agents.
3. **Compose the JSON.** Engine document first, agent document second. Keep them as **separate JSON documents/files** unless the user is specifically working with a dashboard export bundle (see `references/import-export.md`).
4. **Validate before delivering.** Run the bundled validator on every JSON you produce or edit:
   ```bash
   python3 scripts/validate_retell.py path/to/file.json [more files...]
   ```
   It auto-detects the document kind (voice agent / chat agent / retell-llm / conversation flow / export bundle) and reports errors (will break create/import) and warnings (suspicious but possibly intentional). Fix every error. Review every warning and either fix it or explain to the user why it is intentional. Do not hand the user JSON that you have not validated.
5. **Deliver with a note on what's environment-specific** — ids like `llm_id`, `knowledge_base_ids`, `agent_id` in agent-swap tools, and any API keys are placeholders the user must fill from their own workspace.

## The consistency contract

These are the rules that, when broken, produce rejected imports and `400 Invalid request format` responses. Apply them to every document you write. The validator enforces all of them, but you should not be writing violations in the first place.

**Casing and keys**
- Every API field is `snake_case`. There are no camelCase fields in agent, LLM, or flow documents (`agentName`, `voiceId`, `generalPrompt` are always wrong).
- JSON only: no comments, no trailing commas, no unquoted keys.

**Discriminator pairing** — a `type` field dictates which sibling fields must exist:
- `response_engine.type: "retell-llm"` → requires `llm_id`. `"conversation-flow"` → requires `conversation_flow_id`. `"custom-llm"` → requires `llm_websocket_url`. Never mix (e.g. `type: "retell-llm"` with `conversation_flow_id` is a hard error).
- Tool objects, node objects, instruction objects, transfer destinations/options, SMS content, voicemail actions, and analysis-data entries are all discriminated unions. Each `type` has its own required fields — check the reference file rather than guessing.

**Naming rules**
- Tool names and state names: `^[a-zA-Z0-9_-]{1,64}$`. No spaces, no dots, max 64 chars.
- Tool names must be unique within every scope the LLM can see at once: for a retell-llm that is `general_tools + <state>.tools + transition_to_<edge destinations>` per state; for a flow it is per-subagent-node plus the shared `tools[]` names.
- State transitions implicitly create tools named `transition_to_<destination_state_name>` — a hand-written tool with that name collides.

**Referential integrity** (dangling references are the #1 import killer in flows)
- retell-llm: if `states` is non-empty, `starting_state` is required and must name an existing state; every `edges[].destination_state_name` must name an existing state.
- conversation-flow: `start_node_id` must be the `id` of a node; every edge's `destination_node_id` must resolve to a node id; every function node's `tool_id` (with `tool_type: "local"`) must exist in the flow's `tools[]`; `component` nodes with `component_type: "local"` must reference a name/id in `components[]`; node ids must be unique.
- Deleting a node or state means hunting down every edge that pointed at it. Never leave an edge pointing at a removed target.

**Voice vs chat field walls**
- Chat agents accept only their documented field set. Voice-only fields (`voice_id`, `interruption_sensitivity`, `ambient_sound`, `voicemail_option`, `stt_mode`, `pronunciation_dictionary`, `boosted_keywords`, and ~25 more — full list in `references/chat-agent.md`) must never appear on a chat agent.
- Paired names differ deliberately: voice uses `version_description` / `post_call_analysis_data` / webhook events `call_*`; chat uses `version_title` / `post_chat_analysis_data` / webhook events `chat_*`. Copy-pasting between the two without renaming breaks imports.

**Engine-level rules**
- `start_speaker` (`"user"` or `"agent"`) is **required** on both retell-llm and conversation-flow.
- retell-llm: `model` and `s2s_model` are mutually exclusive — set one, never both.
- `model_temperature` range is [0,1] on engines; the agent's `voice_temperature` range is [0,2]. Do not confuse them.
- conversation-flow: `model_choice` is required and currently must be `{ "type": "cascading", "model": "<model>" }`.
- Sentinel edges in flows require exact prompt strings: `"Else"`, `"Always"`, `"Skip response"`, `"Transfer failed"`, `"Sent successfully"`, `"Failed to send"`. Any other casing/wording breaks the special edge semantics.

**Values**
- Dynamic variables are `{{variable_name}}` — double braces, balanced, no spaces in the name. `default_dynamic_variables` values must all be **strings** (`"true"`, `"9"`, not `true`, `9`).
- Phone numbers in transfer destinations: E.164 (`+16175551212`) or a `{{dynamic_variable}}`.
- Durations are milliseconds and range-checked (e.g. agent `ring_duration_ms` 5000–300000, chat `end_chat_after_silence_ms` 120000–259200000). Ranges are in the reference tables.
- `null` vs omitted are different: `null` typically means "remove/clear this setting" on update, omitted means "leave default/unchanged". When composing a *create* document, omit fields you don't need rather than nulling them.
- Custom tool `parameters` must be a JSON Schema object: `{"type": "object", "properties": {...}, "required": [...]}` where every `required` entry exists in `properties`.

**Freshness**
- Model name enums (`gpt-*`, `claude-*`, `gemini-*`), voice model enums, and some endpoints rotate on Retell's deprecation schedule (they deprecate and replace models several times a year). The enum lists in the references were verified against the live OpenAPI spec when this skill was written; if a create call rejects a model string or the user reports a deprecation notice, check https://docs.retellai.com (the machine-readable index is https://docs.retellai.com/llms.txt) rather than trusting memory. The validator intentionally treats unknown model strings as warnings, not errors, for this reason.

## Editing existing JSON

When the user pastes an exported agent or asks for a modification:
1. Run the validator on the input **first** — establish whether problems pre-exist or were introduced by your edit.
2. Make the minimal edit. Preserve unknown/extra fields you don't recognize (dashboard exports carry extra metadata; stripping it can break dashboard re-import). The exception: strip fields listed as read-only in `references/import-export.md` when converting an export into an API create payload.
3. Re-run the validator. Diff mentally: did your edit orphan any edge, duplicate a tool name, or move a field across the voice/chat wall?

## What the validator cannot check

Be explicit with users about these residual risks: whether referenced ids (`llm_id`, `knowledge_base_ids`, `agent_id`, `mcp_id`, voice ids) actually exist in *their* workspace; whether API keys/webhook URLs are live; whether a model string is still served this month; and whether prompt content behaves well on calls. Structural validity ≠ a good agent — for prompt quality, point users at Retell's prompt engineering guide (https://docs.retellai.com/build/prompt-engineering-guide).
