# Import & Export

There are two distinct transport formats. Confusing them is a common source of "import failed" reports.

## Path A — Dashboard export/import (single bundle file)

The Retell dashboard's agent **Export** produces one JSON file that bundles the agent's fields together with an embedded copy of its response engine payload (LLM or conversation-flow data), so the agent can be re-imported into another workspace/organization in one drag-and-drop. Import is the mirror operation on the agent list page.

Critical facts about this format:
- **It is not formally documented and has changed across dashboard versions.** Confirmed against real July-2026 exports: the bundle is the **agent object at the top level** (including read-only fields like `agent_id` — sometimes an empty string — `version`, `is_published`, `last_modification_timestamp`, and a `channel` field) with the engine payload embedded under a **camelCase wrapper key**: `conversationFlow` for conversation-flow engines (the LLM analogue follows the same camelCase convention). `response_engine` on the agent still carries the id + `version` referencing that embedded payload. Do not invent other wrapper keys from memory.
- The reliable procedure when composing or repairing a bundle: **export a minimal fresh agent of the same kind (voice/chat, same engine type) from the *target* workspace's dashboard, and use that file's exact key layout as the template.** Fill your content into that shape. When repairing a user's failing import, diff their file against such a fresh export — extra/missing/renamed top-level keys will jump out.
- Inside the bundle, the engine payload and agent payload follow the same field rules as the API schemas in the other reference files — the validator checks embedded engine/agent objects wherever it can find them.
- Import failures with no useful error usually mean: malformed JSON (validate first!), a wrapper-shape mismatch from an old/hand-built file, or an engine payload violating a schema rule (dangling edge, bad discriminator, illegal enum).

## Path B — API round-trip (two documents)

Programmatic export = `GET /get-agent/{id}` (or `/get-chat-agent/{id}`) **plus** `GET /get-retell-llm/{llm_id}` or `GET /get-conversation-flow/{id}`. Programmatic import = recreate in dependency order:

1. `POST /create-retell-llm` or `POST /create-conversation-flow` with the cleaned engine document → capture the **new** `llm_id` / `conversation_flow_id`.
2. Rewrite the agent document's `response_engine` to point at the new id.
3. `POST /create-agent` or `POST /create-chat-agent` with the cleaned agent document.
4. (Optional) `POST /publish-agent` to publish; rebind phone numbers/widgets separately.

### Read-only fields to strip before any create call

| Document | Strip |
|---|---|
| Agent (voice/chat) | `agent_id`, `version`, `base_version`, `assigned_tags`, `is_published`, `last_modification_timestamp` |
| Retell LLM | `llm_id`, `version`, `is_published`, `last_modification_timestamp` |
| Conversation flow | `conversation_flow_id`, `version` |

Also in `response_engine`: replace the old id with the new one, and drop/null the `version` pin unless you specifically copied that exact engine version (a stale pin silently freezes the agent on an old engine version — or fails if that version number doesn't exist in the target workspace).

## Cross-workspace / cross-org migration checklist

Ids are **workspace-scoped**. After any migration, these will be dangling until re-provisioned in the target workspace — enumerate them for the user:

- `knowledge_base_ids` (engine-level, flow node-level) → recreate KBs, swap ids.
- `component` nodes whose `component_id` matches no embedded `components[]` entry (or with `component_type: "shared"`) → the node references an **org-library component that does not travel with the export**; recreate or re-link it in the target workspace.
- `mcps[]` entries and `mcp_id` references in tools/nodes.
- `agent_swap` tools/nodes → `agent_id` (+ `agent_version`) of *other* agents; migrate dependencies first or re-point after.
- `agentic_transfer_config.transfer_agent.agent_id`.
- `custom_on_hold_music_asset_id` (uploaded audio assets).
- `voice_id` for cloned/custom/community voices not present in the target voice library (platform voices like `11labs-Adrian` generally exist everywhere).
- Phone numbers, widget embeds, environment tags, and A/B splits never travel with the agent — rebind manually.

## Secrets travel in plaintext — scrub before sharing

Exports and GET responses embed literal secrets wherever the user configured them:
- `cal_api_key` on calendar tools
- `headers.Authorization` (and any custom header) on custom tools and MCP configs
- `query_params` values that carry keys/tokens
- occasionally webhook URLs containing signing tokens

Before a user shares an export publicly, posts it for debugging, or commits it to a repo, replace these with placeholders (`"cal_api_key": "REPLACE_ME"`). When *composing* files for a user, always emit placeholders and tell them which fields to fill privately.

## Environment portability pattern

For agents intended to move between dev/staging/prod workspaces, prefer `{{dynamic_variables}}` over hardcoded values wherever the schema allows them (transfer numbers, Cal event ids, timezones, prompt facts like `{{company_name}}`), and put per-environment values in `default_dynamic_variables` or supply them per-call. That turns a migration into an id-swap + variable-table update instead of a prompt-surgery exercise.

## Simulation test cases

Test cases (Simulation tab) export/import as their own JSON files, separate from agent bundles, and are auto-copied when duplicating an agent in-dashboard. Their schema is undocumented; use the same fresh-export-as-template technique.
