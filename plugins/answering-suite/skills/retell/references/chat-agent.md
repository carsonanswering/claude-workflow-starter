# Chat Agent

Endpoint objects: `POST /create-chat-agent`, `PATCH /update-chat-agent/{agent_id}`, `GET /get-chat-agent/{agent_id}`.
Create requires: `response_engine` only. Response adds read-only: `agent_id`, `version`, `base_version`, `assigned_tags`, `is_published`, `last_modification_timestamp`.

Chat agents power web chat widgets, SMS conversations (`/create-sms-chat`), and the chat completion API. They reuse the same response engines as voice agents (`retell-llm`, `conversation-flow`, `custom-llm` — same union rules as voice-agent.md), but the **agent-level field set is a small, distinct subset**. The most common chat-agent JSON bug is a voice field pasted in.

## The complete allowed field set

| Field | Type | Notes |
|---|---|---|
| `response_engine` | union, **required** | Same discriminator rules as voice. |
| `agent_name` | string \| null | |
| `version_title` | string \| null | The chat name for this concept. (`version_title` also appears on modern voice exports, but `version_description` is voice-only — never put it on a chat agent.) |
| `language` | scalar \| array | Same rules as voice (see voice-agent.md): `"multi"` scalar-only and deprecated; arrays of concrete locales. |
| `auto_close_message` | string \| null | Shown when the chat auto-closes. |
| `end_chat_after_silence_ms` | int \| null | **[120000, 259200000]** (2 min – 72 h). Default 3600000. Note the floor is 2 minutes, much higher than the voice silence floor. |
| `webhook_url` | string \| null | |
| `webhook_events` | array \| null | **Chat enum**: `chat_started`, `chat_ended`, `chat_analyzed`, `transcript_updated`. `call_*` and `transfer_*` values are invalid here. |
| `webhook_timeout_ms` | int | Default 10000. |
| `data_storage_setting` | enum \| null | `everything` \| `everything_except_pii` \| `basic_attributes_only`. |
| `data_storage_retention_days` | int \| null | [1,730]. |
| `opt_in_signed_url` | bool | |
| `signed_url_expiration_ms` | int \| null | Default 86400000. |
| `post_chat_analysis_data` | array \| null | AnalysisData items **or** chat presets `{ "type": "system-presets", "name": "chat_summary"\|"chat_successful"\|"user_sentiment", ... }`. Voice preset names (`call_summary`, `call_successful`) are invalid here. |
| `post_chat_analysis_model` | enum \| null | Default `gpt-4.1`. |
| `pii_config` | object | Same shape as voice. |
| `guardrail_config` | object | Same shape as voice. |
| `handbook_config` | object | **Chat subset only**: `default_personality`, `high_empathy`, `ai_disclosure`, `scope_boundaries`. Voice-only presets (`natural_filler_words`, `echo_verification`, `nato_phonetic_alphabet`, `speech_normalization`, `smart_matching`) are invalid. |
| `timezone` | string \| null | IANA. |

Anything not in this table does not belong on a chat agent.

## Voice-only fields — never on a chat agent

`voice_id`, `voice_model`, `fallback_voice_ids`, `voice_temperature`, `voice_speed`, `enable_dynamic_voice_speed`, `enable_dynamic_responsiveness`, `volume`, `voice_emotion`, `responsiveness`, `interruption_sensitivity`, `enable_backchannel`, `backchannel_frequency`, `backchannel_words`, `reminder_trigger_ms`, `reminder_max_count`, `ambient_sound`, `ambient_sound_volume`, `boosted_keywords`, `pronunciation_dictionary`, `end_call_after_silence_ms`, `max_call_duration_ms`, `voicemail_message`, `voicemail_detection_timeout_ms`, `voicemail_option`, `ivr_option`, `call_screening_option`, `begin_message_delay_ms`, `ring_duration_ms`, `stt_mode`, `custom_stt_config`, `vocab_specialization`, `allow_user_dtmf`, `allow_dtmf_interruption`, `user_dtmf_options`, `denoising_mode`, `post_call_analysis_data`, `post_call_analysis_model`, `analysis_successful_prompt`, `analysis_summary_prompt`, `analysis_user_sentiment_prompt`, `version_description`.

## Voice ⇄ chat conversion map

When adapting one agent kind into the other:

| Voice | Chat | Action |
|---|---|---|
| `version_description` | `version_title` | rename |
| `post_call_analysis_data` (presets `call_summary`, `call_successful`, `user_sentiment`) | `post_chat_analysis_data` (presets `chat_summary`, `chat_successful`, `user_sentiment`) | rename field + rename summary/success presets (`user_sentiment` keeps its name) |
| `post_call_analysis_model` | `post_chat_analysis_model` | rename |
| `webhook_events: call_*` / `transfer_*` | `webhook_events: chat_*` | remap (`call_started`→`chat_started`, etc.; drop `transfer_*`) |
| `end_call_after_silence_ms` | `end_chat_after_silence_ms` | rename **and re-range** (chat floor 120000) |
| all other voice-only fields | — | drop |
| — | `auto_close_message` | optionally add |

The engine usually transfers unchanged; note that engine speech-only behaviors (`speak_during_execution`, backchannel-ish prompt language, `press_digit` tools, transfer tools) are meaningless or invalid in a pure chat context — review engine tools when converting.

## Minimal valid create payload

```json
{
  "agent_name": "Ava - Web Chat",
  "response_engine": { "type": "retell-llm", "llm_id": "llm_REPLACE_ME" },
  "language": "en-US",
  "end_chat_after_silence_ms": 1800000,
  "post_chat_analysis_data": [
    { "type": "system-presets", "name": "chat_summary" }
  ]
}
```
