# Voice Agent

Endpoint objects: `POST /create-agent`, `PATCH /update-agent/{agent_id}`, `GET /get-agent/{agent_id}`.
Create requires: `response_engine`, `voice_id`. Response adds read-only: `agent_id`, `version`, `base_version`, `assigned_tags`, `is_published`, `last_modification_timestamp`.

## response_engine (required, discriminated union)

| `type` | Required sibling | Optional |
|---|---|---|
| `"retell-llm"` | `llm_id` | `version` (number \| null; null/omitted tracks latest) |
| `"conversation-flow"` | `conversation_flow_id` | `version` |
| `"custom-llm"` | `llm_websocket_url` | — |

Never pair a `type` with another type's id field.

## Voice & speech

| Field | Type / range | Notes |
|---|---|---|
| `voice_id` | string, **required** | e.g. `retell-Cimo`, `11labs-Adrian`, `cartesia-...`. Workspace voice library defines valid ids. |
| `voice_model` | enum \| null | As of 2026-07: `eleven_flash_v2`, `eleven_flash_v2_5`, `eleven_multilingual_v2`, `eleven_v3`, `sonic-3`, `sonic-3-latest`, `sonic-3.5`, `tts-1`, `gpt-4o-mini-tts`, `speech-02-turbo`, `speech-2.8-turbo`, `s1`, `s2-pro`, `s2.1-pro` (the `eleven_turbo_*` entries were replaced by Flash on 2026-07-12). Must belong to the same provider as `voice_id`. `null` clears. |
| `fallback_voice_ids` | string[] \| null | Must be from **different** TTS providers than the primary voice. Tried in order on outage. |
| `voice_temperature` | number [0,2] | Stability. Default 1. (Engine `model_temperature` is [0,1] — different field, different range.) |
| `voice_speed` | number [0.5,2] | Default 1. |
| `enable_dynamic_voice_speed` | bool | |
| `volume` | number [0,2] | Default 1. |
| `voice_emotion` | enum \| null | `calm`, `sympathetic`, `happy`, `sad`, `angry`, `fearful`, `surprised`. Cartesia/MiniMax only. |
| `pronunciation_dictionary` | array \| null | Entries `{ "word"*, "alphabet"*: "ipa"\|"cmu", "phoneme"* }`. Provider-dependent support. |

## Turn-taking & conversation dynamics

| Field | Range | Default | Notes |
|---|---|---|---|
| `responsiveness` | [0,1] | 1 | Higher = replies sooner. |
| `interruption_sensitivity` | [0,1] | 1 | 0 = never interruptible. |
| `enable_dynamic_responsiveness` | bool | false | |
| `enable_backchannel` | bool | false | |
| `backchannel_frequency` | [0,1] | 0.8 | Only with backchannel on. |
| `backchannel_words` | string[] \| null | | Test with the chosen voice. |
| `reminder_trigger_ms` | > 0 | 10000 | Nudge after user silence. |
| `reminder_max_count` | int ≥ 0 | 1 | 0 disables reminders. |
| `begin_message_delay_ms` | [0,5000] | 0 | Only when agent speaks first. |
| `ring_duration_ms` | [5000,300000] | 30000 | Outbound + transfer ring time. |

## Ambience & audio pipeline

- `ambient_sound`: `coffee-shop` | `convention-hall` | `summer-outdoor` | `mountain-outdoor` | `static-noise` | `call-center` | null. `ambient_sound_volume` [0,2].
- `stt_mode`: `fast` | `accurate` | `custom`. **`custom` requires `custom_stt_config`: `{ "provider": "azure"|"deepgram"|"soniox", "endpointing_ms": int }`** (min 100 Azure / 10 Deepgram / 500 Soniox).
- `vocab_specialization`: `general` | `medical` (English only).
- `denoising_mode`: `no-denoise` | `noise-cancellation` | `noise-and-background-speech-cancellation`.
- `boosted_keywords`: string[] | null — bias the transcriber toward brand names etc.
- DTMF input: `allow_user_dtmf` (default true), `allow_dtmf_interruption` (default false), `user_dtmf_options`: `{ "digit_limit": 1–50, "termination_key": one of 0-9 * #, "timeout_ms": 1000–15000 }`.

## Language

`language`: a single locale scalar (`"en-US"`, `"es-419"`, `"fr-CA"`, ... — 60+ supported), OR the legacy scalar `"multi"`, OR an array of concrete locales (`["en-US","es-ES"]`). Rules:
- `"multi"` is valid **only as the scalar** — never inside an array (and the scalar form is deprecated for removal 2026-07-31; prefer the array).
- Single-element arrays get normalized back to a scalar on output — don't be surprised by round-trip diffs.

## Call lifecycle

| Field | Range | Default |
|---|---|---|
| `end_call_after_silence_ms` | ≥ 10000 | 600000 |
| `max_call_duration_ms` | [60000, 7200000] | 3600000 |
| `voicemail_detection_timeout_ms` | [5000,180000] | 30000 |

`voicemail_option` (null disables): `{ "action": <VoicemailAction>, "detection_prompt"?: ≤2000 chars }` where action is one of
`{ "type": "prompt", "text": "..." }` | `{ "type": "static_text", "text": "..." }` | `{ "type": "hangup" }` | `{ "type": "bridge_transfer" }`.
(`voicemail_message` is the older simple field; prefer `voicemail_option`.)

`ivr_option` (null disables): `{ "action": { "type": "hangup" }, "detection_prompt"? }`.

`call_screening_option` (null disables): `{ "agent_identity"*: 1–100 chars, "call_purpose"*: 1–300 chars }` — both support `{{vars}}`.

## Webhooks

- `webhook_url` (string | null), `webhook_timeout_ms` (default 10000).
- `webhook_events` (voice enum): `call_started`, `call_ended`, `call_analyzed`, `transcript_updated`, `transfer_started`, `transfer_bridged`, `transfer_cancelled`, `transfer_ended`. Defaults to the first three. **Chat agents use `chat_*` events — do not copy voice events onto a chat agent.**

## Post-call analysis

- `post_call_analysis_data`: array of AnalysisData (`string`/`enum`/`boolean`/`number` — see retell-llm.md) **or** system presets `{ "type": "system-presets", "name": "call_summary"|"call_successful"|"user_sentiment", "description"?, "required"?, "conditional_prompt"? }`.
- `post_call_analysis_model`: nullable model enum (default `gpt-4.1`).
- `analysis_successful_prompt`, `analysis_summary_prompt`, `analysis_user_sentiment_prompt`: ≤ 2000 chars each, null → default prompt.

## Data governance & misc

- `data_storage_setting`: `everything` (default) | `everything_except_pii` | `basic_attributes_only`. (Replaces deprecated `opt_out_sensitive_data_storage` — do not emit the old field.)
- `data_storage_retention_days`: [1,730] | null (null/omitted = keep forever).
- `opt_in_signed_url` (bool), `signed_url_expiration_ms` (default 86400000).
- `pii_config`: `{ "mode": "post_call", "categories": [subset of person_name,address,email,phone_number,ssn,passport,driver_license,credit_card,bank_account,password,pin,medical_id,date_of_birth,customer_account_number] }` — empty categories = no scrubbing; both keys required if present.
- `guardrail_config`: `{ "output_topics"?: [...], "input_topics"?: ["platform_integrity_jailbreaking"] }` (output enum: harassment, self_harm, sexual_exploitation, violence, defense_and_national_security, illicit_and_harmful_activity, gambling, regulated_professional_advice, child_safety_and_exploitation).
- `handbook_config` (voice presets, all booleans): default_personality, natural_filler_words, high_empathy, echo_verification, nato_phonetic_alphabet, speech_normalization, smart_matching, ai_disclosure, scope_boundaries.
- `agent_name` (string | null), `version_description` (string | null), `version_title` (string | null — real voice exports carry both; dashboards now write `version_title` on voice agents too), `timezone` (IANA, default America/Los_Angeles).
- `channel` (`"voice"` — appears in dashboard exports; harmless to include, identifies agent kind).
- `enable_expressive_mode` (bool) + `expressive_emotion_tags` (string[] — e.g. `"empathetic"`, `"excited"`, `"sigh"`, `"clear throat"`, `"emphasis"`; only with voices that support expressive mode, e.g. `retell-*`).
- `post_call_analysis_model` (e.g. `"gpt-4.1"` — model used for post-call analysis).
- `opt_in_signed_url` (bool).

## Minimal valid create payload

```json
{
  "agent_name": "Ava - Dental Scheduler",
  "voice_id": "11labs-Adrian",
  "response_engine": { "type": "retell-llm", "llm_id": "llm_REPLACE_ME" },
  "language": "en-US",
  "webhook_url": "https://example.com/retell-webhook",
  "post_call_analysis_data": [
    { "type": "string", "name": "caller_name", "description": "Full name of the caller." }
  ]
}
```
