# Retell LLM (single / multi-prompt response engine)

Endpoint objects: `POST /create-retell-llm`, `PATCH /update-retell-llm/{llm_id}`, `GET /get-retell-llm/{llm_id}`.
The response adds read-only fields: `llm_id`, `version`, `is_published`, `last_modification_timestamp`. Strip those before re-creating (see import-export.md).

## Top-level fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `start_speaker` | `"user"` \| `"agent"` | **yes** | Who talks first. Required on create. |
| `model` | string enum | no* | Text LLM. As of 2026-07: `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5.1`, `gpt-5.2`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.5`, `claude-4.5-sonnet`, `claude-4.6-sonnet`, `claude-4.5-haiku`, `gemini-3.0-flash`, `gemini-3.1-flash-lite`. Defaults to `gpt-4.1`. Verify against live docs if rejected — this enum rotates. |
| `s2s_model` | string enum | no* | Speech-to-speech model (`gpt-realtime-2`, `gpt-realtime-1.5`, `gpt-realtime`, `gpt-realtime-mini`). ***Mutually exclusive with `model` — set one, never both.*** |
| `model_temperature` | number | no | **[0,1]** (not [0,2]). Default 0. Keep low when tools are involved. |
| `model_high_priority` | boolean | no | Dedicated capacity pool, higher cost. |
| `tool_call_strict_mode` | boolean | no | Strict JSON-schema tool calls; only some models support it. |
| `general_prompt` | string \| null | no | System prompt in every state. `system prompt = general_prompt + state_prompt`. |
| `general_tools` | Tool[] \| null | no | Tools available in every state. |
| `states` | State[] \| null | no | Multi-prompt state machine. Omit for single-prompt. |
| `starting_state` | string \| null | **iff states** | Required when `states` is non-empty; must equal one state's `name`. |
| `begin_message` | string \| null | no | First agent utterance. Unset → LLM generates one. `""` → agent stays silent, waits for user. Supports `{{vars}}`. |
| `begin_after_user_silence_ms` | int \| null | no | Only when agent waits for user first; agent speaks after this silence. |
| `default_dynamic_variables` | object \| null | no | Key→value, **all values must be strings**. Fallbacks when a call doesn't supply the variable. |
| `knowledge_base_ids` | string[] \| null | no | Workspace-scoped KB ids. |
| `kb_config` | object | no | `{ "top_k": 1–10, "filter_score": 0–1 }`. |
| `mcps` | MCP[] \| null | no | `{ name*, url*, headers?, query_params?, timeout_ms? }`. Headers commonly carry secrets — see import-export.md before sharing files. |

## States (multi-prompt)

```json
{
  "name": "information_collection",
  "state_prompt": "## Task\nCollect the caller's name and reason for calling...",
  "edges": [
    {
      "destination_state_name": "appointment_booking",
      "description": "Transition when the caller wants to book.",
      "parameters": {
        "type": "object",
        "properties": { "caller_name": { "type": "string", "description": "Full name collected" } },
        "required": ["caller_name"]
      }
    }
  ],
  "tools": []
}
```

Rules:
- `name` required; pattern `^[a-zA-Z0-9_-]{1,64}$`; unique across states.
- Every `edges[].destination_state_name` must name an existing state; `description` is required on edges.
- Each edge becomes an implicit tool `transition_to_<destination_state_name>` — that name counts toward tool-name uniqueness within the state.
- Edge `parameters` (optional) is a JSON Schema object (same shape as custom-tool parameters); extracted values become dynamic variables in later states.
- Effective toolset in a state = `general_tools` + that state's `tools` + that state's transition tools. All names must be unique within that union.
- Unreachable states (no edge path from `starting_state`) are legal but almost always a mistake — flag them.

## Tools (13 types)

Common to all: `type`* and `name`* (name pattern `^[a-zA-Z0-9_-]{1,64}$`); `description` recommended (tells the LLM when to call it). Tools that speak share: `speak_during_execution` (bool), `execution_message_description` (string), `execution_message_type` (`"prompt"` = generate from description, `"static_text"` = say verbatim; default `"prompt"`).

| `type` | Additional required | Key optional fields |
|---|---|---|
| `end_call` | — | speak fields |
| `transfer_call` | `transfer_destination`, `transfer_option` | `ignore_e164_validation`, `custom_sip_headers`, speak fields |
| `check_availability_cal` | `cal_api_key`, `event_type_id` | `timezone` (IANA or `{{var}}`) |
| `book_appointment_cal` | `cal_api_key`, `event_type_id` | `timezone` |
| `agent_swap` | `agent_id`, `post_call_analysis_setting` (`both_agents` \| `only_destination_agent`) | `agent_version`, `webhook_setting` (`both_agents`\|`only_destination_agent`\|`only_source_agent`), `keep_current_voice`, `keep_current_language`, speak fields |
| `press_digit` | — | `delay_ms` 0–5000 (default 1000) |
| `send_sms` | `sms_content` | speak fields |
| `custom` | `url` (the HTTPS endpoint — despite a copy-paste bug in Retell's own docs describing it otherwise) | `method` (GET/POST/PUT/PATCH/DELETE, default POST), `headers`, `query_params`, `parameters` (JSON Schema), `response_variables` (var → JSON path), `speak_during_execution`, `speak_after_execution`, `timeout_ms` 1000–600000 (default 120000), `args_at_root`, `parameter_type` (`json`\|`form`), `enable_typing_sound` |
| `code` | `code` (JS, ≤ 20000 chars) | `timeout_ms` 5000–60000 (default 30000), `response_variables`, speak fields, `enable_typing_sound` |
| `extract_dynamic_variable` | `variables` (AnalysisData[]), `description` | `enable_typing_sound` |
| `bridge_transfer` | — | speak fields. Only valid on transfer agents in agentic warm transfer. |
| `cancel_transfer` | — | speak fields. Only valid on transfer agents in agentic warm transfer. |
| `mcp` | `description` | `mcp_id`, `input_schema`, `response_variables`, speak fields, `enable_typing_sound` |

### transfer_destination (union)
- `{ "type": "predefined", "number": "+16175551212", "extension": "123*456#"? }` — number in E.164 or `{{var}}`; extension digits/`*`/`#` or `{{var}}`.
- `{ "type": "inferred", "prompt": "Transfer to the store the caller mentions..." }`.

### transfer_option (union)
- `{ "type": "cold_transfer", "cold_transfer_mode": "sip_invite"|"sip_refer", "show_transferee_as_caller": bool, "transfer_ring_duration_ms": 5000–90000 }` — `show_transferee_as_caller` only takes effect with `sip_invite`.
- `{ "type": "warm_transfer", ... }` — optional `agent_detection_timeout_ms`, `on_hold_music` (`none`|`relaxing_sound`|`uplifting_beats`|`ringtone`|`custom` + `custom_on_hold_music_asset_id`), `public_handoff_option` / `private_handoff_option` (each `{ "type": "prompt", "prompt": ... }` or `{ "type": "static_message", "message": ... }`), `ivr_option` (prompt), `opt_out_human_detection`, `enable_bridge_audio_cue`.
- `{ "type": "agentic_warm_transfer", "agentic_transfer_config": { "transfer_agent": { "agent_id"*, "agent_version"* }, "transfer_timeout_ms": 30000, "action_on_timeout": "bridge_transfer"|"cancel_transfer" }, ... }` — `agentic_transfer_config` (with both nested fields) is required.

### sms_content (union)
- `{ "type": "predefined", "content": "..." }` (supports `{{vars}}`)
- `{ "type": "inferred", "prompt": "..." }`
- `{ "type": "template", "template": "info_collection" }`

### AnalysisData (used by extract_dynamic_variable; also by agent-level analysis)
All require `type`, `name` (min length 1), `description`. Optional `required` (bool), `conditional_prompt`.
- `string` — optional `examples: string[]`
- `enum` — **requires non-empty `choices: string[]`**
- `boolean`
- `number`

### Custom tool `parameters` shape
```json
{
  "type": "object",
  "properties": {
    "order_id": { "type": "string", "description": "The order to look up" }
  },
  "required": ["order_id"]
}
```
`type` must be `"object"`; every entry in `required` must be a key of `properties`. Omit `parameters` entirely for a no-argument tool.

## Minimal valid examples

Single-prompt:
```json
{
  "start_speaker": "agent",
  "model": "gpt-4.1",
  "begin_message": "Hi, this is Ava from Retell Dental. How can I help?",
  "general_prompt": "## Identity\nYou are Ava, a scheduling assistant for Retell Dental...",
  "general_tools": [
    { "type": "end_call", "name": "end_call", "description": "End the call when the conversation is complete." }
  ]
}
```

Multi-prompt skeleton:
```json
{
  "start_speaker": "agent",
  "model": "gpt-4.1",
  "general_prompt": "You are Ava...",
  "starting_state": "intake",
  "states": [
    { "name": "intake", "state_prompt": "Collect name and reason...",
      "edges": [ { "destination_state_name": "booking", "description": "Caller wants to book an appointment." } ] },
    { "name": "booking", "state_prompt": "Book via the calendar tool...", "tools": [] }
  ]
}
```
