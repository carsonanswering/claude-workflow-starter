#!/usr/bin/env python3
"""
validate_retell.py — offline structural validator for Retell AI agent JSON.

Usage:
    python3 validate_retell.py FILE.json [MORE.json ...] [--kind KIND]

KIND (optional, default auto): voice-agent | chat-agent | retell-llm |
conversation-flow | bundle | auto

Auto-detects each document's kind, then checks the consistency rules that
break /create-* calls and dashboard imports: discriminator pairing, required
fields per type, naming rules, referential integrity (states/edges/nodes/
tool ids), voice-vs-chat field walls, numeric ranges, enum values, and
dynamic-variable syntax.

Severity:
  ERROR — will (or is overwhelmingly likely to) be rejected by Retell.
  WARN  — suspicious/deprecated/unverifiable offline; review intentionally.

Exit code 0 if no errors (warnings allowed), 1 otherwise.
Stdlib only; no network access; nothing is sent anywhere.
"""

import argparse
import json
import re
import sys

# --------------------------------------------------------------------------
# Issue collection
# --------------------------------------------------------------------------

class Report:
    def __init__(self, filename):
        self.filename = filename
        self.issues = []  # (severity, path, message)

    def error(self, path, msg):
        self.issues.append(("ERROR", path, msg))

    def warn(self, path, msg):
        self.issues.append(("WARN", path, msg))

    @property
    def errors(self):
        return [i for i in self.issues if i[0] == "ERROR"]

    @property
    def warnings(self):
        return [i for i in self.issues if i[0] == "WARN"]


# --------------------------------------------------------------------------
# Constants distilled from Retell's OpenAPI spec (verified 2026-07).
# Model / voice-model lists rotate on Retell's deprecation schedule, so
# unknown values there are WARN, not ERROR.
# --------------------------------------------------------------------------

NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
E164_RE = re.compile(r"^\+[1-9]\d{1,14}$")
DYNVAR_RE = re.compile(r"^\{\{[a-zA-Z0-9_.-]+\}\}$")
CAMEL_RE = re.compile(r"[a-z0-9][A-Z]")

KNOWN_LLM_MODELS = {
    "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
    "gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-5.1", "gpt-5.2",
    "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.5",
    "claude-4.5-sonnet", "claude-4.6-sonnet", "claude-5-sonnet",
    "claude-4.5-haiku",
    "gemini-2.5-flash-lite", "gemini-3.0-flash", "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
}
KNOWN_S2S_MODELS = {"gpt-realtime-2", "gpt-realtime-1.5", "gpt-realtime", "gpt-realtime-mini"}
KNOWN_VOICE_MODELS = {
    "eleven_turbo_v2", "eleven_flash_v2", "eleven_turbo_v2_5", "eleven_flash_v2_5",
    "eleven_multilingual_v2", "eleven_v3",
    "sonic-3", "sonic-3-latest", "sonic-3.5",
    "tts-1", "gpt-4o-mini-tts",
    "speech-02-turbo", "speech-2.8-turbo", "s1", "s2-pro", "s2.1-pro",
}
DEPRECATED_VOICE_MODELS = {"eleven_turbo_v2", "eleven_turbo_v2_5"}  # replaced by Flash 2026-07-12

LANGUAGES = {
    "en-US", "en-IN", "en-GB", "en-AU", "en-NZ", "de-DE", "es-ES", "es-419",
    "hi-IN", "fr-FR", "fr-CA", "ja-JP", "pt-PT", "pt-BR", "zh-CN", "ru-RU",
    "it-IT", "ko-KR", "nl-NL", "nl-BE", "pl-PL", "tr-TR", "vi-VN", "ro-RO",
    "bg-BG", "ca-ES", "th-TH", "da-DK", "fi-FI", "el-GR", "hu-HU", "id-ID",
    "no-NO", "sk-SK", "sv-SE", "lt-LT", "lv-LV", "cs-CZ", "ms-MY", "af-ZA",
    "ar-SA", "az-AZ", "bs-BA", "cy-GB", "fa-IR", "fil-PH", "gl-ES", "he-IL",
    "hr-HR", "hy-AM", "is-IS", "kk-KZ", "kn-IN", "mk-MK", "mr-IN", "ne-NP",
    "sl-SI", "sr-RS", "sw-KE", "ta-IN", "ur-IN", "yue-CN", "uk-UA",
}

AMBIENT_SOUNDS = {"coffee-shop", "convention-hall", "summer-outdoor",
                  "mountain-outdoor", "static-noise", "call-center"}
VOICE_EMOTIONS = {"calm", "sympathetic", "happy", "sad", "angry", "fearful", "surprised"}
DATA_STORAGE = {"everything", "everything_except_pii", "basic_attributes_only"}
STT_MODES = {"fast", "accurate", "custom"}
ASR_PROVIDERS = {"azure", "deepgram", "soniox"}
DENOISE = {"no-denoise", "noise-cancellation", "noise-and-background-speech-cancellation"}
VOCAB = {"general", "medical"}
VOICE_WEBHOOK_EVENTS = {"call_started", "call_ended", "call_analyzed", "transcript_updated",
                        "transfer_started", "transfer_bridged", "transfer_cancelled", "transfer_ended"}
CHAT_WEBHOOK_EVENTS = {"chat_started", "chat_ended", "chat_analyzed", "transcript_updated"}
PII_CATEGORIES = {"person_name", "address", "email", "phone_number", "ssn", "passport",
                  "driver_license", "credit_card", "bank_account", "password", "pin",
                  "medical_id", "date_of_birth", "customer_account_number"}
GUARDRAIL_OUT = {"harassment", "self_harm", "sexual_exploitation", "violence",
                 "defense_and_national_security", "illicit_and_harmful_activity",
                 "gambling", "regulated_professional_advice", "child_safety_and_exploitation"}
GUARDRAIL_IN = {"platform_integrity_jailbreaking"}
VOICE_HANDBOOK = {"default_personality", "natural_filler_words", "high_empathy",
                  "echo_verification", "nato_phonetic_alphabet", "speech_normalization",
                  "smart_matching", "ai_disclosure", "scope_boundaries"}
CHAT_HANDBOOK = {"default_personality", "high_empathy", "ai_disclosure", "scope_boundaries"}

VOICE_PRESET_NAMES = {"call_summary", "call_successful", "user_sentiment"}
CHAT_PRESET_NAMES = {"chat_summary", "chat_successful", "user_sentiment"}

TOOL_TYPES = {"end_call", "transfer_call", "check_availability_cal", "book_appointment_cal",
              "agent_swap", "press_digit", "send_sms", "custom", "code",
              "extract_dynamic_variable", "bridge_transfer", "cancel_transfer", "mcp"}
FLOW_SHARED_TOOL_TYPES = {"custom", "check_availability_cal", "book_appointment_cal"}
NODE_TYPES = {"conversation", "subagent", "end", "function", "code", "transfer_call",
              "press_digit", "branch", "sms", "extract_dynamic_variables", "agent_swap",
              "mcp", "component", "bridge_transfer", "cancel_transfer"}
EQ_OPERATORS = {"==", "!=", ">", ">=", "<", "<=", "contains", "not_contains", "exists", "not_exist"}

SENTINELS = {
    "else_edge": "Else",
    "always_edge": "Always",
    "skip_response_edge": "Skip response",
    "edge": "Transfer failed",           # transfer_call / agent_swap failure edge
    "success_edge": "Sent successfully",
    "failed_edge": "Failed to send",
}

VOICE_AGENT_FIELDS = {
    "response_engine", "agent_name", "version_description", "version_title",
    "channel", "enable_expressive_mode", "expressive_emotion_tags",
    "voice_id", "voice_model",
    "fallback_voice_ids", "voice_temperature", "voice_speed", "enable_dynamic_voice_speed",
    "enable_dynamic_responsiveness", "volume", "voice_emotion", "responsiveness",
    "interruption_sensitivity", "enable_backchannel", "backchannel_frequency",
    "backchannel_words", "reminder_trigger_ms", "reminder_max_count", "ambient_sound",
    "ambient_sound_volume", "language", "webhook_url", "webhook_events", "webhook_timeout_ms",
    "boosted_keywords", "data_storage_setting", "data_storage_retention_days",
    "opt_in_signed_url", "signed_url_expiration_ms", "pronunciation_dictionary",
    "end_call_after_silence_ms", "max_call_duration_ms", "voicemail_message",
    "voicemail_detection_timeout_ms", "voicemail_option", "ivr_option",
    "call_screening_option", "post_call_analysis_data", "post_call_analysis_model",
    "analysis_successful_prompt", "analysis_summary_prompt", "analysis_user_sentiment_prompt",
    "begin_message_delay_ms", "ring_duration_ms", "stt_mode", "custom_stt_config",
    "vocab_specialization", "allow_user_dtmf", "allow_dtmf_interruption", "user_dtmf_options",
    "denoising_mode", "pii_config", "guardrail_config", "handbook_config", "timezone",
}
AGENT_READONLY_FIELDS = {"agent_id", "version", "base_version", "assigned_tags",
                         "is_published", "last_modification_timestamp"}

CHAT_AGENT_FIELDS = {
    "response_engine", "agent_name", "version_title", "channel", "auto_close_message",
    "end_chat_after_silence_ms", "language", "webhook_url", "webhook_events",
    "webhook_timeout_ms", "data_storage_setting", "data_storage_retention_days",
    "opt_in_signed_url", "signed_url_expiration_ms", "post_chat_analysis_data",
    "post_chat_analysis_model", "pii_config", "guardrail_config", "handbook_config",
    "timezone",
}
VOICE_ONLY_FIELDS = (VOICE_AGENT_FIELDS - CHAT_AGENT_FIELDS)
HANDLED_IN_COMMON = {"opt_out_sensitive_data_storage"}
CHAT_ONLY_FIELDS = (CHAT_AGENT_FIELDS - VOICE_AGENT_FIELDS)

LLM_FIELDS = {
    "model", "s2s_model", "model_temperature", "model_high_priority",
    "tool_call_strict_mode", "knowledge_base_ids", "kb_config", "start_speaker",
    "begin_after_user_silence_ms", "begin_message", "general_prompt", "general_tools",
    "states", "starting_state", "default_dynamic_variables", "mcps",
}
LLM_READONLY = {"llm_id", "version", "is_published", "last_modification_timestamp"}

FLOW_FIELDS = {
    "model_choice", "model_temperature", "tool_call_strict_mode", "knowledge_base_ids",
    "kb_config", "start_speaker", "begin_after_user_silence_ms", "global_prompt",
    "flex_mode", "tools", "components", "start_node_id", "default_dynamic_variables",
    "begin_tag_display_position", "notes", "mcps", "is_transfer_llm", "is_transfer_cf",
    "nodes", "kb_instruction",
}
FLOW_READONLY = {"conversation_flow_id", "version", "is_published", "last_modification_timestamp"}

RENAME_HINTS = {  # wrong-kind field -> hint
    "version_description": "chat agents use `version_title`",
    "post_call_analysis_data": "chat agents use `post_chat_analysis_data` (presets chat_summary / chat_successful)",
    "post_chat_analysis_data": "voice agents use `post_call_analysis_data` (presets call_summary / call_successful)",
    "post_call_analysis_model": "chat agents use `post_chat_analysis_model`",
    "post_chat_analysis_model": "voice agents use `post_call_analysis_model`",
    "end_call_after_silence_ms": "chat agents use `end_chat_after_silence_ms` (range 120000-259200000)",
    "end_chat_after_silence_ms": "voice agents use `end_call_after_silence_ms` (min 10000)",
    "opt_out_sensitive_data_storage": "deprecated; use `data_storage_setting`",
}


# --------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------

def is_dynvar(value):
    return isinstance(value, str) and DYNVAR_RE.match(value.strip()) is not None


def check_range(rep, obj, key, lo, hi, path, integer=False):
    if key not in obj or obj[key] is None:
        return
    v = obj[key]
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        rep.error(f"{path}.{key}", f"must be a number, got {type(v).__name__}")
        return
    if integer and not isinstance(v, int):
        rep.error(f"{path}.{key}", f"must be an integer, got {v!r}")
        return
    if lo is not None and v < lo:
        rep.error(f"{path}.{key}", f"{v} is below minimum {lo}")
    if hi is not None and v > hi:
        rep.error(f"{path}.{key}", f"{v} is above maximum {hi}")


def check_enum(rep, obj, key, allowed, path, severity="error", nullable=True):
    if key not in obj:
        return
    v = obj[key]
    if v is None:
        if not nullable:
            rep.error(f"{path}.{key}", "null is not allowed here")
        return
    if v not in allowed:
        msg = f"{v!r} is not one of {sorted(allowed)}"
        (rep.error if severity == "error" else rep.warn)(f"{path}.{key}", msg)


def check_bool(rep, obj, key, path):
    if key in obj and obj[key] is not None and not isinstance(obj[key], bool):
        rep.error(f"{path}.{key}", f"must be a boolean, got {obj[key]!r}")


def check_string(rep, obj, key, path, required=False, minlen=0, maxlen=None):
    if key not in obj or obj[key] is None:
        if required:
            rep.error(path, f"missing required field `{key}`")
        return
    v = obj[key]
    if not isinstance(v, str):
        rep.error(f"{path}.{key}", f"must be a string, got {type(v).__name__}")
        return
    if len(v) < minlen:
        rep.error(f"{path}.{key}", f"must be at least {minlen} character(s)")
    if maxlen is not None and len(v) > maxlen:
        rep.error(f"{path}.{key}", f"exceeds max length {maxlen} ({len(v)} chars)")


def scan_dynamic_vars(rep, node, path):
    """Recursively scan every string for malformed {{dynamic_variable}} syntax."""
    if isinstance(node, dict):
        for k, v in node.items():
            scan_dynamic_vars(rep, v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            scan_dynamic_vars(rep, v, f"{path}[{i}]")
    elif isinstance(node, str):
        opens, closes = node.count("{{"), node.count("}}")
        if opens != closes:
            rep.warn(path, f"unbalanced dynamic-variable braces ({opens} '{{{{' vs {closes} '}}}}')")
        for m in re.finditer(r"\{\{(.*?)\}\}", node):
            inner = m.group(1)
            if inner.strip() == "":
                rep.warn(path, "empty dynamic variable `{{}}`")
            elif inner != inner.strip() or " " in inner.strip():
                rep.warn(path, f"dynamic variable `{{{{{inner}}}}}` contains spaces; use `{{{{{inner.strip().replace(' ', '_')}}}}}`")


def check_camelcase_keys(rep, obj, known_fields, path):
    """Flag camelCase keys; return the set of keys flagged (to suppress double reports)."""
    flagged = set()
    if not isinstance(obj, dict):
        return flagged
    snake_map = {}
    for f in known_fields:
        parts = f.split("_")
        camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
        if camel != f:
            snake_map[camel] = f
    for k in obj:
        if k in snake_map:
            rep.error(f"{path}.{k}", f"camelCase key; the API field is `{snake_map[k]}`")
            flagged.add(k)
        elif isinstance(k, str) and CAMEL_RE.search(k):
            rep.warn(f"{path}.{k}", "camelCase key; Retell API fields are snake_case")
            flagged.add(k)
    return flagged


def check_default_dynamic_variables(rep, obj, path):
    ddv = obj.get("default_dynamic_variables")
    if ddv is None:
        return
    if not isinstance(ddv, dict):
        rep.error(f"{path}.default_dynamic_variables", "must be an object of string values")
        return
    for k, v in ddv.items():
        if not isinstance(v, str):
            rep.error(f"{path}.default_dynamic_variables.{k}",
                      f"value must be a string (got {type(v).__name__} {v!r}); write it as \"{v}\"")


def check_kb_config(rep, obj, path):
    kb = obj.get("kb_config")
    if kb is None:
        return
    if not isinstance(kb, dict):
        rep.error(f"{path}.kb_config", "must be an object")
        return
    check_range(rep, kb, "top_k", 1, 10, f"{path}.kb_config", integer=True)
    check_range(rep, kb, "filter_score", 0, 1, f"{path}.kb_config")


# --------------------------------------------------------------------------
# Shared sub-schemas
# --------------------------------------------------------------------------

def validate_tool_parameters(rep, params, path):
    if params is None:
        return
    if not isinstance(params, dict):
        rep.error(path, "`parameters` must be a JSON Schema object")
        return
    if params.get("type") != "object":
        rep.error(f"{path}.type", "must be exactly \"object\" for tool parameters")
    props = params.get("properties")
    if not isinstance(props, dict):
        rep.error(f"{path}.properties", "missing/invalid `properties` object (required)")
        props = {}
    req = params.get("required")
    if req is not None:
        if not isinstance(req, list):
            rep.error(f"{path}.required", "`required` must be an array of property names")
        else:
            for r in req:
                if r not in props:
                    rep.error(f"{path}.required",
                              f"`{r}` listed in required but absent from properties")


def validate_analysis_data(rep, item, path, presets=None, preset_type_label=""):
    if not isinstance(item, dict):
        rep.error(path, "analysis item must be an object")
        return
    t = item.get("type")
    if t == "system-presets":
        if presets is None:
            rep.error(f"{path}.type", "system-presets not valid in this context")
            return
        name = item.get("name")
        if name not in presets:
            rep.error(f"{path}.name",
                      f"{name!r} is not a valid {preset_type_label} preset {sorted(presets)}")
        return
    if t not in {"string", "enum", "boolean", "number"}:
        rep.error(f"{path}.type", f"invalid analysis-data type {t!r} "
                  "(string|enum|boolean|number" + ("|system-presets" if presets else "") + ")")
        return
    check_string(rep, item, "name", path, required=True, minlen=1)
    check_string(rep, item, "description", path, required=True)
    if t == "enum":
        ch = item.get("choices")
        if not isinstance(ch, list) or len(ch) == 0:
            rep.error(f"{path}.choices", "enum analysis data requires a non-empty `choices` array")
        elif not all(isinstance(c, str) for c in ch):
            rep.error(f"{path}.choices", "all choices must be strings")


def validate_transfer_destination(rep, dest, path):
    if not isinstance(dest, dict):
        rep.error(path, "transfer_destination must be an object")
        return
    t = dest.get("type")
    if t == "predefined":
        num = dest.get("number")
        if not isinstance(num, str) or not num:
            rep.error(f"{path}.number", "predefined destination requires `number`")
        elif not (E164_RE.match(num) or is_dynvar(num)):
            rep.error(f"{path}.number",
                      f"{num!r} is neither E.164 (+16175551212) nor a {{{{dynamic_variable}}}}")
        ext = dest.get("extension")
        if ext is not None and not (isinstance(ext, str) and (is_dynvar(ext) or re.match(r"^[0-9*#]+$", ext))):
            rep.error(f"{path}.extension", "extension allows digits, '*', '#', or a {{dynamic_variable}}")
    elif t == "inferred":
        check_string(rep, dest, "prompt", path, required=True)
    else:
        rep.error(f"{path}.type", f"invalid transfer_destination type {t!r} (predefined|inferred)")


def validate_transfer_option(rep, opt, path):
    if not isinstance(opt, dict):
        rep.error(path, "transfer_option must be an object")
        return
    t = opt.get("type")
    if t == "cold_transfer":
        check_enum(rep, opt, "cold_transfer_mode", {"sip_refer", "sip_invite"}, path)
        check_range(rep, opt, "transfer_ring_duration_ms", 5000, 90000, path, integer=True)
        if opt.get("show_transferee_as_caller") and opt.get("cold_transfer_mode") == "sip_refer":
            rep.warn(f"{path}.show_transferee_as_caller",
                     "has no effect with cold_transfer_mode=sip_refer (only sip_invite)")
    elif t in {"warm_transfer", "agentic_warm_transfer"}:
        check_range(rep, opt, "transfer_ring_duration_ms", 5000, 90000, path, integer=True)
        check_enum(rep, opt, "on_hold_music",
                   {"none", "relaxing_sound", "uplifting_beats", "ringtone", "custom"}, path)
        if opt.get("on_hold_music") == "custom" and not opt.get("custom_on_hold_music_asset_id"):
            rep.error(f"{path}.custom_on_hold_music_asset_id",
                      "required when on_hold_music is \"custom\"")
        for ho in ("public_handoff_option", "private_handoff_option"):
            h = opt.get(ho)
            if h is not None:
                ht = h.get("type") if isinstance(h, dict) else None
                if ht == "prompt":
                    check_string(rep, h, "prompt", f"{path}.{ho}", required=True)
                elif ht == "static_message":
                    check_string(rep, h, "message", f"{path}.{ho}", required=True)
                else:
                    rep.error(f"{path}.{ho}.type", f"invalid handoff type {ht!r} (prompt|static_message)")
        if t == "agentic_warm_transfer":
            cfg = opt.get("agentic_transfer_config")
            if not isinstance(cfg, dict):
                rep.error(f"{path}.agentic_transfer_config",
                          "required for agentic_warm_transfer")
            else:
                ta = cfg.get("transfer_agent")
                if not isinstance(ta, dict) or not ta.get("agent_id") or "agent_version" not in ta:
                    rep.error(f"{path}.agentic_transfer_config.transfer_agent",
                              "requires `agent_id` and `agent_version`")
                check_enum(rep, cfg, "action_on_timeout",
                           {"bridge_transfer", "cancel_transfer"}, f"{path}.agentic_transfer_config")
    else:
        rep.error(f"{path}.type",
                  f"invalid transfer_option type {t!r} (cold_transfer|warm_transfer|agentic_warm_transfer)")


def validate_sms_content(rep, sms, path):
    if not isinstance(sms, dict):
        rep.error(path, "sms_content must be an object")
        return
    t = sms.get("type")
    if t == "predefined":
        check_string(rep, sms, "content", path, required=True)
    elif t == "inferred":
        check_string(rep, sms, "prompt", path, required=True)
    elif t == "template":
        check_enum(rep, sms, "template", {"info_collection"}, path)
        if "template" not in sms:
            rep.error(f"{path}.template", "template sms_content requires `template`")
    else:
        rep.error(f"{path}.type", f"invalid sms_content type {t!r} (predefined|inferred|template)")


def validate_tool(rep, tool, path, allowed_types=TOOL_TYPES):
    """Validate one Tool union member (retell-llm tools / subagent tools / flow shared tools)."""
    if not isinstance(tool, dict):
        rep.error(path, "tool must be an object")
        return None
    t = tool.get("type")
    if t not in allowed_types:
        if t in TOOL_TYPES:
            rep.error(f"{path}.type",
                      f"tool type {t!r} is not allowed in this context (allowed: {sorted(allowed_types)})")
        else:
            rep.error(f"{path}.type", f"unknown tool type {t!r}")
        return tool.get("name")
    name = tool.get("name")
    if not isinstance(name, str) or not name:
        rep.error(path, "tool missing required `name`")
    elif not NAME_RE.match(name):
        rep.error(f"{path}.name",
                  f"{name!r} violates ^[a-zA-Z0-9_-]{{1,64}}$ (no spaces/dots, max 64)")
    check_enum(rep, tool, "execution_message_type", {"prompt", "static_text"}, path)

    if t == "transfer_call":
        if "transfer_destination" not in tool:
            rep.error(path, "transfer_call requires `transfer_destination`")
        else:
            validate_transfer_destination(rep, tool["transfer_destination"], f"{path}.transfer_destination")
        if "transfer_option" not in tool:
            rep.error(path, "transfer_call requires `transfer_option`")
        else:
            validate_transfer_option(rep, tool["transfer_option"], f"{path}.transfer_option")
    elif t in {"check_availability_cal", "book_appointment_cal"}:
        check_string(rep, tool, "cal_api_key", path, required=True)
        if "event_type_id" not in tool:
            rep.error(path, f"{t} requires `event_type_id`")
        elif not isinstance(tool["event_type_id"], (int, float, str)):
            rep.error(f"{path}.event_type_id", "must be a number or {{dynamic_variable}} string")
    elif t == "agent_swap":
        check_string(rep, tool, "agent_id", path, required=True, minlen=1)
        if "post_call_analysis_setting" not in tool:
            rep.error(path, "agent_swap requires `post_call_analysis_setting`")
        check_enum(rep, tool, "post_call_analysis_setting",
                   {"both_agents", "only_destination_agent"}, path)
        check_enum(rep, tool, "webhook_setting",
                   {"both_agents", "only_destination_agent", "only_source_agent"}, path)
    elif t == "press_digit":
        check_range(rep, tool, "delay_ms", 0, 5000, path, integer=True)
    elif t == "send_sms":
        if "sms_content" not in tool:
            rep.error(path, "send_sms requires `sms_content`")
        else:
            validate_sms_content(rep, tool["sms_content"], f"{path}.sms_content")
    elif t == "custom":
        check_string(rep, tool, "url", path, required=True)
        u = tool.get("url")
        if isinstance(u, str) and u and not re.match(r"^https?://", u) and not is_dynvar(u):
            rep.warn(f"{path}.url", f"{u!r} does not look like an http(s) URL")
        check_enum(rep, tool, "method", {"GET", "POST", "PUT", "PATCH", "DELETE"}, path)
        validate_tool_parameters(rep, tool.get("parameters"), f"{path}.parameters")
        check_range(rep, tool, "timeout_ms", 1000, 600000, path, integer=True)
        check_enum(rep, tool, "parameter_type", {"json", "form"}, path)
    elif t == "code":
        code = tool.get("code")
        if not isinstance(code, str) or not code:
            rep.error(path, "code tool requires non-empty `code`")
        elif len(code) > 20000:
            rep.error(f"{path}.code", f"code exceeds 20000-char limit ({len(code)})")
        check_range(rep, tool, "timeout_ms", 5000, 60000, path, integer=True)
    elif t == "extract_dynamic_variable":
        check_string(rep, tool, "description", path, required=True)
        vs = tool.get("variables")
        if not isinstance(vs, list) or not vs:
            rep.error(path, "extract_dynamic_variable requires non-empty `variables`")
        else:
            for i, v in enumerate(vs):
                validate_analysis_data(rep, v, f"{path}.variables[{i}]")
    elif t == "mcp":
        check_string(rep, tool, "description", path, required=True)
    return name


def validate_mcps(rep, mcps, path):
    if mcps is None:
        return
    if not isinstance(mcps, list):
        rep.error(path, "`mcps` must be an array")
        return
    for i, m in enumerate(mcps):
        p = f"{path}[{i}]"
        if not isinstance(m, dict):
            rep.error(p, "MCP entry must be an object")
            continue
        check_string(rep, m, "name", p, required=True)
        check_string(rep, m, "url", p, required=True)


def validate_language(rep, obj, path):
    if "language" not in obj or obj["language"] is None:
        return
    lang = obj["language"]
    if isinstance(lang, str):
        if lang == "multi":
            rep.warn(f"{path}.language",
                     "scalar \"multi\" is legacy (removal announced 2026-07-31); "
                     "use an explicit locale array instead")
        elif lang not in LANGUAGES:
            rep.warn(f"{path}.language", f"{lang!r} not in the known locale list; verify against docs")
    elif isinstance(lang, list):
        if not lang:
            rep.error(f"{path}.language", "language array must not be empty")
        for i, item in enumerate(lang):
            if item == "multi":
                rep.error(f"{path}.language[{i}]",
                          "\"multi\" is invalid inside an array (scalar-only legacy value)")
            elif item not in LANGUAGES:
                rep.warn(f"{path}.language[{i}]", f"{item!r} not in the known locale list")
    else:
        rep.error(f"{path}.language", "must be a locale string or array of locales")


def validate_response_engine(rep, re_obj, path):
    if not isinstance(re_obj, dict):
        rep.error(path, "`response_engine` must be an object")
        return
    t = re_obj.get("type")
    pairing = {"retell-llm": "llm_id",
               "conversation-flow": "conversation_flow_id",
               "custom-llm": "llm_websocket_url"}
    if t not in pairing:
        rep.error(f"{path}.type",
                  f"invalid response_engine type {t!r} (retell-llm|conversation-flow|custom-llm)")
        return
    needed = pairing[t]
    if not re_obj.get(needed):
        rep.error(path, f"response_engine type \"{t}\" requires `{needed}`")
    for other in set(pairing.values()) - {needed}:
        if other in re_obj:
            rep.error(f"{path}.{other}",
                      f"`{other}` does not belong with type \"{t}\" (expected `{needed}`)")


def validate_pii_guardrail_handbook(rep, obj, path, handbook_allowed):
    pii = obj.get("pii_config")
    if pii is not None:
        if not isinstance(pii, dict):
            rep.error(f"{path}.pii_config", "must be an object")
        else:
            if pii.get("mode") != "post_call":
                rep.error(f"{path}.pii_config.mode", "must be \"post_call\"")
            cats = pii.get("categories")
            if not isinstance(cats, list):
                rep.error(f"{path}.pii_config.categories", "required array (may be empty)")
            else:
                for i, c in enumerate(cats):
                    if c not in PII_CATEGORIES:
                        rep.warn(f"{path}.pii_config.categories[{i}]", f"unknown category {c!r}")
    gr = obj.get("guardrail_config")
    if gr is not None and isinstance(gr, dict):
        for i, c in enumerate(gr.get("output_topics") or []):
            if c not in GUARDRAIL_OUT:
                rep.warn(f"{path}.guardrail_config.output_topics[{i}]", f"unknown topic {c!r}")
        for i, c in enumerate(gr.get("input_topics") or []):
            if c not in GUARDRAIL_IN:
                rep.warn(f"{path}.guardrail_config.input_topics[{i}]", f"unknown topic {c!r}")
    hb = obj.get("handbook_config")
    if hb is not None:
        if not isinstance(hb, dict):
            rep.error(f"{path}.handbook_config", "must be an object of booleans")
        else:
            for k, v in hb.items():
                if k not in handbook_allowed:
                    if k in VOICE_HANDBOOK:
                        rep.error(f"{path}.handbook_config.{k}",
                                  "voice-only handbook preset; invalid on a chat agent")
                    else:
                        rep.warn(f"{path}.handbook_config.{k}", f"unknown handbook preset {k!r}")
                if not isinstance(v, bool):
                    rep.error(f"{path}.handbook_config.{k}", "handbook preset values must be booleans")


# --------------------------------------------------------------------------
# Document validators
# --------------------------------------------------------------------------

def validate_retell_llm(rep, doc, path="$", strict_unknown=True):
    camel = check_camelcase_keys(rep, doc, LLM_FIELDS | LLM_READONLY, path)

    if "start_speaker" not in doc:
        rep.error(path, "missing required `start_speaker` (\"user\" or \"agent\")")
    else:
        check_enum(rep, doc, "start_speaker", {"user", "agent"}, path, nullable=False)

    if doc.get("model") is not None and doc.get("s2s_model") is not None:
        rep.error(path, "`model` and `s2s_model` are mutually exclusive — set exactly one")
    if doc.get("model") is not None and doc["model"] not in KNOWN_LLM_MODELS:
        rep.warn(f"{path}.model",
                 f"{doc['model']!r} not in the known model list (list rotates; verify at docs.retellai.com)")
    if doc.get("s2s_model") is not None and doc["s2s_model"] not in KNOWN_S2S_MODELS:
        rep.warn(f"{path}.s2s_model", f"{doc['s2s_model']!r} not in the known s2s model list")

    check_range(rep, doc, "model_temperature", 0, 1, path)
    check_bool(rep, doc, "model_high_priority", path)
    check_bool(rep, doc, "tool_call_strict_mode", path)
    check_kb_config(rep, doc, path)
    check_default_dynamic_variables(rep, doc, path)
    validate_mcps(rep, doc.get("mcps"), f"{path}.mcps")

    # general tools
    general_names = []
    gt = doc.get("general_tools")
    if gt is not None:
        if not isinstance(gt, list):
            rep.error(f"{path}.general_tools", "must be an array of tools")
        else:
            for i, tool in enumerate(gt):
                n = validate_tool(rep, tool, f"{path}.general_tools[{i}]")
                if n:
                    general_names.append(n)
            dups = {n for n in general_names if general_names.count(n) > 1}
            for d in dups:
                rep.error(f"{path}.general_tools", f"duplicate tool name {d!r}")

    # states
    states = doc.get("states")
    starting = doc.get("starting_state")
    if states is not None and not isinstance(states, list):
        rep.error(f"{path}.states", "must be an array")
        states = None
    if states:
        names = []
        for i, st in enumerate(states):
            sp = f"{path}.states[{i}]"
            if not isinstance(st, dict):
                rep.error(sp, "state must be an object")
                continue
            nm = st.get("name")
            if not isinstance(nm, str) or not nm:
                rep.error(sp, "state missing required `name`")
                nm = None
            elif not NAME_RE.match(nm):
                rep.error(f"{sp}.name", f"{nm!r} violates ^[a-zA-Z0-9_-]{{1,64}}$")
            if nm:
                if nm in names:
                    rep.error(f"{sp}.name", f"duplicate state name {nm!r}")
                names.append(nm)
        if not starting:
            rep.error(path, "`starting_state` is required when `states` is non-empty")
        elif starting not in names:
            rep.error(f"{path}.starting_state",
                      f"{starting!r} does not match any state name {names}")
        # per-state edges + tool scope
        reachable = {starting} if starting in names else set()
        frontier = list(reachable)
        adjacency = {}
        for i, st in enumerate(states):
            if not isinstance(st, dict):
                continue
            sp = f"{path}.states[{i}]"
            nm = st.get("name")
            state_tool_names = list(general_names)
            for j, tool in enumerate(st.get("tools") or []):
                tn = validate_tool(rep, tool, f"{sp}.tools[{j}]")
                if tn:
                    state_tool_names.append(tn)
            dests = []
            for j, edge in enumerate(st.get("edges") or []):
                ep = f"{sp}.edges[{j}]"
                if not isinstance(edge, dict):
                    rep.error(ep, "edge must be an object")
                    continue
                d = edge.get("destination_state_name")
                if not d:
                    rep.error(ep, "edge missing required `destination_state_name`")
                elif d not in names:
                    rep.error(f"{ep}.destination_state_name",
                              f"{d!r} does not match any state name")
                else:
                    dests.append(d)
                    state_tool_names.append(f"transition_to_{d}")
                if not edge.get("description"):
                    rep.error(ep, "edge missing required `description`")
                validate_tool_parameters(rep, edge.get("parameters"), f"{ep}.parameters")
            adjacency[nm] = dests
            dups = {n for n in state_tool_names if state_tool_names.count(n) > 1}
            for d in dups:
                rep.error(f"{sp}", f"tool name {d!r} collides within state scope "
                          "(general tools + state tools + transition_to_* names must be unique)")
        if starting in names:  # only meaningful when a valid entry point exists
            while frontier:
                cur = frontier.pop()
                for d in adjacency.get(cur, []):
                    if d not in reachable:
                        reachable.add(d)
                        frontier.append(d)
            for nm in sorted(set(names) - reachable):
                rep.warn(f"{path}.states",
                         f"state {nm!r} is unreachable from starting_state {starting!r}")
    elif starting:
        rep.warn(f"{path}.starting_state", "set but `states` is empty/missing")

    if strict_unknown:
        for k in doc:
            if k in camel:
                continue
            if k not in LLM_FIELDS and k not in LLM_READONLY and k in RENAME_HINTS:
                rep.error(f"{path}.{k}", f"does not belong on a Retell LLM — {RENAME_HINTS[k]}")
            elif k not in LLM_FIELDS and k not in LLM_READONLY:
                rep.warn(f"{path}.{k}", "unknown field for a Retell LLM (extra fields may be rejected)")
        for k in LLM_READONLY & set(doc):
            rep.warn(f"{path}.{k}",
                     "read-only/server-assigned field; strip before POST /create-retell-llm")

    scan_dynamic_vars(rep, doc, path)


# ---- conversation flow -----------------------------------------------------

def _edge_ok(rep, edge, path, node_ids, sentinel=None, require_dest=True):
    """Validate one edge object; return destination id or None."""
    if not isinstance(edge, dict):
        rep.error(path, "edge must be an object")
        return None
    if not edge.get("id"):
        rep.error(path, "edge missing required `id`")
    tc = edge.get("transition_condition")
    if not isinstance(tc, dict):
        rep.error(path, "edge missing required `transition_condition`")
    else:
        t = tc.get("type")
        if sentinel is not None:
            if t != "prompt" or tc.get("prompt") != sentinel:
                rep.error(f"{path}.transition_condition",
                          f"this edge slot requires the exact prompt string \"{sentinel}\" "
                          f"(got type={t!r}, prompt={tc.get('prompt')!r})")
        elif t == "prompt":
            if not tc.get("prompt"):
                rep.error(f"{path}.transition_condition.prompt", "prompt condition needs non-empty `prompt`")
        elif t == "equation":
            eqs = tc.get("equations")
            if not isinstance(eqs, list) or not eqs:
                rep.error(f"{path}.transition_condition.equations", "equation condition needs equations[]")
            elif len(eqs) > 50:
                rep.error(f"{path}.transition_condition.equations", "max 50 equations")
            else:
                for i, eq in enumerate(eqs):
                    qp = f"{path}.transition_condition.equations[{i}]"
                    if not isinstance(eq, dict):
                        rep.error(qp, "equation must be an object")
                        continue
                    if not eq.get("left"):
                        rep.error(qp, "equation missing `left`")
                    op = eq.get("operator")
                    if op not in EQ_OPERATORS:
                        rep.error(f"{qp}.operator", f"invalid operator {op!r}")
                    elif op not in {"exists", "not_exist"} and "right" not in eq:
                        rep.error(qp, f"operator {op!r} requires `right`")
            if tc.get("operator") not in {"||", "&&"}:
                rep.error(f"{path}.transition_condition.operator",
                          "equation condition requires operator \"||\" or \"&&\"")
        else:
            rep.error(f"{path}.transition_condition.type",
                      f"invalid condition type {t!r} (prompt|equation)")
    dest = edge.get("destination_node_id")
    if dest is not None and dest not in node_ids:
        rep.error(f"{path}.destination_node_id",
                  f"{dest!r} does not match any node id — dangling edge")
        return None
    if dest is None and require_dest:
        rep.warn(f"{path}", "edge has no `destination_node_id` (dead-end edge)")
    return dest


def validate_conversation_flow(rep, doc, path="$", strict_unknown=True):
    camel = check_camelcase_keys(rep, doc, FLOW_FIELDS | FLOW_READONLY, path)

    if "start_speaker" not in doc:
        rep.error(path, "missing required `start_speaker`")
    else:
        check_enum(rep, doc, "start_speaker", {"user", "agent"}, path, nullable=False)

    mc = doc.get("model_choice")
    if mc is None:
        rep.error(path, "missing required `model_choice` "
                  "({\"type\": \"cascading\", \"model\": \"...\"})")
    elif not isinstance(mc, dict):
        rep.error(f"{path}.model_choice", "must be an object")
    else:
        if mc.get("type") != "cascading":
            rep.error(f"{path}.model_choice.type", "must be \"cascading\"")
        if not mc.get("model"):
            rep.error(f"{path}.model_choice", "requires `model`")
        elif mc["model"] not in KNOWN_LLM_MODELS:
            rep.warn(f"{path}.model_choice.model",
                     f"{mc['model']!r} not in the known model list (list rotates; verify at docs.retellai.com)")

    check_range(rep, doc, "model_temperature", 0, 1, path)
    check_kb_config(rep, doc, path)
    check_default_dynamic_variables(rep, doc, path)
    validate_mcps(rep, doc.get("mcps"), f"{path}.mcps")

    # shared tool library
    shared_tool_ids = set()
    tools = doc.get("tools")
    if tools is not None:
        if not isinstance(tools, list):
            rep.error(f"{path}.tools", "must be an array")
        else:
            for i, tool in enumerate(tools):
                tp = f"{path}.tools[{i}]"
                validate_tool(rep, tool, tp, allowed_types=FLOW_SHARED_TOOL_TYPES)
                tid = tool.get("tool_id") if isinstance(tool, dict) else None
                if not tid:
                    rep.error(tp, "flow-level tools each require a `tool_id`")
                elif tid in shared_tool_ids:
                    rep.error(f"{tp}.tool_id", f"duplicate tool_id {tid!r}")
                else:
                    shared_tool_ids.add(tid)

    # components (validated as mini-flows for node structure)
    local_components = set()
    comps = doc.get("components")
    if comps is not None:
        if not isinstance(comps, list):
            rep.error(f"{path}.components", "must be an array")
        else:
            for i, comp in enumerate(comps):
                cp = f"{path}.components[{i}]"
                if not isinstance(comp, dict):
                    rep.error(cp, "component must be an object")
                    continue
                if not comp.get("name"):
                    rep.error(cp, "component missing required `name`")
                else:
                    local_components.add(comp["name"])
                # real exports carry conversation_flow_component_id and component nodes
                # reference it via `component_id` — accept it as the primary key
                if comp.get("conversation_flow_component_id"):
                    local_components.add(comp["conversation_flow_component_id"])
                comp_tool_ids = set(shared_tool_ids)
                for j, tool in enumerate(comp.get("tools") or []):
                    tid = tool.get("tool_id") if isinstance(tool, dict) else None
                    if tid:
                        comp_tool_ids.add(tid)
                    validate_tool(rep, tool, f"{cp}.tools[{j}]",
                                  allowed_types=FLOW_SHARED_TOOL_TYPES)
                if not isinstance(comp.get("nodes"), list):
                    rep.error(cp, "component missing required `nodes` array")
                else:
                    _validate_flow_nodes(rep, comp, cp, comp_tool_ids, local_components,
                                         is_component=True)

    if not isinstance(doc.get("nodes"), list):
        rep.error(path, "missing required `nodes` array")
    else:
        _validate_flow_nodes(rep, doc, path, shared_tool_ids, local_components,
                             is_component=False)

    if strict_unknown:
        for k in doc:
            if k in camel:
                continue
            if k not in FLOW_FIELDS and k not in FLOW_READONLY:
                rep.warn(f"{path}.{k}", "unknown field for a conversation flow")
        for k in FLOW_READONLY & set(doc):
            rep.warn(f"{path}.{k}",
                     "read-only/server-assigned field; strip before POST /create-conversation-flow")

    scan_dynamic_vars(rep, doc, path)


def _validate_instruction(rep, node, path, prompt_only=False, allow_template=False, required=True):
    inst = node.get("instruction")
    if inst is None:
        if required:
            rep.error(path, "missing required `instruction`")
        return
    if not isinstance(inst, dict):
        rep.error(f"{path}.instruction", "must be an object")
        return
    t = inst.get("type")
    if allow_template and t == "template":
        check_enum(rep, inst, "template", {"info_collection"}, f"{path}.instruction")
        return
    allowed = {"prompt"} if prompt_only else {"prompt", "static_text"}
    if t not in allowed:
        rep.error(f"{path}.instruction.type",
                  f"invalid instruction type {t!r} (allowed here: {sorted(allowed)})")
        return
    if not isinstance(inst.get("text"), str) or not inst["text"]:
        rep.error(f"{path}.instruction.text", "instruction requires non-empty `text`")


def _validate_flow_nodes(rep, container, path, tool_ids, local_components, is_component):
    nodes = container.get("nodes") or []
    node_ids = []
    for i, n in enumerate(nodes):
        if isinstance(n, dict) and n.get("id"):
            if n["id"] in node_ids:
                rep.error(f"{path}.nodes[{i}].id", f"duplicate node id {n['id']!r}")
            node_ids.append(n["id"])
    node_id_set = set(node_ids)

    start = container.get("start_node_id")
    if start is None:
        if not is_component and nodes:
            rep.warn(path, "no `start_node_id` — the flow has no entry point")
    elif start not in node_id_set:
        rep.error(f"{path}.start_node_id", f"{start!r} does not match any node id")

    reachable = set()
    frontier = [start] if start in node_id_set else []
    edges_out = {}

    for i, node in enumerate(nodes):
        np_ = f"{path}.nodes[{i}]"
        if not isinstance(node, dict):
            rep.error(np_, "node must be an object")
            continue
        nid = node.get("id")
        if not nid:
            rep.error(np_, "node missing required `id`")
        t = node.get("type")
        if t not in NODE_TYPES:
            rep.error(f"{np_}.type", f"unknown node type {t!r}")
            continue
        dests = []

        def std_edges(require_else=False):
            for j, e in enumerate(node.get("edges") or []):
                d = _edge_ok(rep, e, f"{np_}.edges[{j}]", node_id_set)
                if d:
                    dests.append(d)
            if node.get("else_edge") is not None:
                d = _edge_ok(rep, node["else_edge"], f"{np_}.else_edge", node_id_set,
                             sentinel="Else")
                if d:
                    dests.append(d)
            elif require_else:
                rep.error(np_, f"{t} node requires `else_edge`")

        if t in {"conversation", "subagent"}:
            _validate_instruction(rep, node, np_, prompt_only=(t == "subagent"))
            std_edges()
            for slot, sentinel in (("skip_response_edge", "Skip response"),
                                   ("always_edge", "Always")):
                if node.get(slot) is not None:
                    d = _edge_ok(rep, node[slot], f"{np_}.{slot}", node_id_set, sentinel=sentinel)
                    if d:
                        dests.append(d)
            if t == "conversation" and ("tools" in node or "tool_ids" in node):
                rep.error(np_, "`tools`/`tool_ids` on conversation nodes were deprecated "
                          "2026-04-18 — move them to a `subagent` node")
            if t == "subagent":
                for j, tid in enumerate(node.get("tool_ids") or []):
                    if tid not in tool_ids:
                        rep.error(f"{np_}.tool_ids[{j}]",
                                  f"{tid!r} not found in the flow's tools[] tool_id set")
                sub_names = []
                for j, tool in enumerate(node.get("tools") or []):
                    n2 = validate_tool(rep, tool, f"{np_}.tools[{j}]")
                    if n2:
                        sub_names.append(n2)
                for d in {n2 for n2 in sub_names if sub_names.count(n2) > 1}:
                    rep.error(f"{np_}.tools", f"duplicate tool name {d!r} in subagent node")
        elif t == "end":
            if node.get("speak_during_execution"):
                _validate_instruction(rep, node, np_, required=False)
        elif t == "function":
            for req in ("tool_id", "tool_type", "wait_for_result"):
                if req not in node:
                    rep.error(np_, f"function node missing required `{req}`")
            check_enum(rep, node, "tool_type", {"local", "shared"}, np_, nullable=False)
            if node.get("tool_type") == "local" and node.get("tool_id") not in tool_ids:
                rep.error(f"{np_}.tool_id",
                          f"{node.get('tool_id')!r} (tool_type=local) not found in tools[]")
            std_edges()
        elif t == "code":
            code = node.get("code")
            if not isinstance(code, str) or not code:
                if "code" in node and isinstance(node.get("code"), str):
                    rep.warn(np_, "code node has empty `code` — fine as a parked editor node, but it will do nothing if reached")
                else:
                    rep.error(np_, "code node requires a `code` string")
            elif len(code) > 20000:
                rep.error(f"{np_}.code", f"exceeds 20000-char limit ({len(code)})")
            if "wait_for_result" not in node:
                rep.error(np_, "code node missing required `wait_for_result`")
            check_range(rep, node, "timeout_ms", 5000, 60000, np_, integer=True)
            std_edges()
        elif t == "transfer_call":
            if "transfer_destination" not in node:
                rep.error(np_, "transfer_call node requires `transfer_destination`")
            else:
                validate_transfer_destination(rep, node["transfer_destination"],
                                              f"{np_}.transfer_destination")
            if "transfer_option" not in node:
                rep.error(np_, "transfer_call node requires `transfer_option`")
            else:
                validate_transfer_option(rep, node["transfer_option"], f"{np_}.transfer_option")
            if node.get("edge") is None:
                rep.error(np_, "transfer_call node requires failure `edge` (\"Transfer failed\")")
            else:
                d = _edge_ok(rep, node["edge"], f"{np_}.edge", node_id_set,
                             sentinel="Transfer failed")
                if d:
                    dests.append(d)
        elif t == "press_digit":
            _validate_instruction(rep, node, np_, prompt_only=True)
            check_range(rep, node, "delay_ms", 0, 5000, np_, integer=True)
            std_edges()
        elif t == "branch":
            std_edges(require_else=True)
        elif t == "sms":
            _validate_instruction(rep, node, np_, allow_template=True)
            for slot, sentinel in (("success_edge", "Sent successfully"),
                                   ("failed_edge", "Failed to send")):
                if node.get(slot) is None:
                    rep.error(np_, f"sms node requires `{slot}`")
                else:
                    d = _edge_ok(rep, node[slot], f"{np_}.{slot}", node_id_set, sentinel=sentinel)
                    if d:
                        dests.append(d)
        elif t == "extract_dynamic_variables":
            vs = node.get("variables")
            if not isinstance(vs, list) or not vs:
                rep.error(np_, "extract_dynamic_variables node requires non-empty `variables`")
            else:
                for j, v in enumerate(vs):
                    validate_analysis_data(rep, v, f"{np_}.variables[{j}]")
            std_edges()
        elif t == "agent_swap":
            check_string(rep, node, "agent_id", np_, required=True, minlen=1)
            if "post_call_analysis_setting" not in node:
                rep.error(np_, "agent_swap node requires `post_call_analysis_setting`")
            check_enum(rep, node, "post_call_analysis_setting",
                       {"both_agents", "only_destination_agent"}, np_)
            if node.get("edge") is None:
                rep.error(np_, "agent_swap node requires failure `edge` (\"Transfer failed\")")
            else:
                d = _edge_ok(rep, node["edge"], f"{np_}.edge", node_id_set,
                             sentinel="Transfer failed")
                if d:
                    dests.append(d)
        elif t == "mcp":
            for req in ("mcp_id", "mcp_tool_name", "wait_for_result"):
                if req not in node:
                    rep.error(np_, f"mcp node missing required `{req}`")
            if not container.get("mcps"):
                rep.warn(np_, "mcp node present but the flow declares no `mcps[]` servers")
            std_edges()
        elif t == "component":
            for req in ("component_id", "component_type"):
                if req not in node:
                    rep.error(np_, f"component node missing required `{req}`")
            check_enum(rep, node, "component_type", {"local", "shared"}, np_, nullable=False)
            if (node.get("component_type") == "local" and local_components
                    and node.get("component_id") not in local_components):
                rep.warn(f"{np_}.component_id",
                         f"{node.get('component_id')!r} does not match any local component "
                         "(by conversation_flow_component_id or name) — dangling reference "
                         "if this is meant to be a local component")
            std_edges(require_else=True)
        elif t in {"bridge_transfer", "cancel_transfer"}:
            if not container.get("is_transfer_llm"):
                rep.warn(np_, f"{t} node is only meaningful on transfer flows "
                         "(is_transfer_llm: true)")

        # global node settings
        gns = node.get("global_node_setting")
        if gns is not None:
            gp = f"{np_}.global_node_setting"
            if not isinstance(gns, dict) or not gns.get("condition"):
                rep.error(gp, "global_node_setting requires non-empty `condition`")
            else:
                if "cool_down" in gns:
                    check_range(rep, gns, "cool_down", 1, None, gp)
                for j, gb in enumerate(gns.get("go_back_conditions") or []):
                    if isinstance(gb, dict) and gb.get("destination_node_id"):
                        rep.error(f"{gp}.go_back_conditions[{j}]",
                                  "go-back edges must not have a destination_node_id")
                    _edge_ok(rep, gb, f"{gp}.go_back_conditions[{j}]", node_id_set,
                             require_dest=False)
            if nid:
                reachable.add(nid)  # global nodes are reachable by definition

        if nid:
            edges_out[nid] = dests

    # reachability
    while frontier:
        cur = frontier.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        frontier.extend(edges_out.get(cur, []))
    for nid in node_id_set - reachable:
        if start in node_id_set:
            rep.warn(f"{path}.nodes", f"node {nid!r} is unreachable from start_node_id and is not global")


# ---- agents ----------------------------------------------------------------

def _validate_agent_common(rep, doc, path):
    if "response_engine" not in doc:
        rep.error(path, "missing required `response_engine`")
    else:
        validate_response_engine(rep, doc["response_engine"], f"{path}.response_engine")
    validate_language(rep, doc, path)
    check_range(rep, doc, "webhook_timeout_ms", 1, None, path, integer=True)
    check_enum(rep, doc, "data_storage_setting", DATA_STORAGE, path)
    check_range(rep, doc, "data_storage_retention_days", 1, 730, path, integer=True)
    if "opt_out_sensitive_data_storage" in doc:
        rep.error(f"{path}.opt_out_sensitive_data_storage",
                  "deprecated field — use `data_storage_setting`")
    scan_dynamic_vars(rep, doc, path)


def validate_voice_agent(rep, doc, path="$", strict_unknown=True):
    camel = check_camelcase_keys(rep, doc, VOICE_AGENT_FIELDS | AGENT_READONLY_FIELDS, path)
    _validate_agent_common(rep, doc, path)

    if not doc.get("voice_id"):
        rep.error(path, "voice agent missing required `voice_id`")
    if doc.get("voice_model") is not None:
        if doc["voice_model"] not in KNOWN_VOICE_MODELS:
            rep.warn(f"{path}.voice_model", f"{doc['voice_model']!r} not in the known voice-model "
                     "list (rotates; verify at docs.retellai.com)")
        elif doc["voice_model"] in DEPRECATED_VOICE_MODELS:
            rep.warn(f"{path}.voice_model",
                     f"{doc['voice_model']!r} was replaced by its Flash equivalent on 2026-07-12")

    check_range(rep, doc, "voice_temperature", 0, 2, path)
    check_range(rep, doc, "voice_speed", 0.5, 2, path)
    check_range(rep, doc, "volume", 0, 2, path)
    check_range(rep, doc, "responsiveness", 0, 1, path)
    check_range(rep, doc, "interruption_sensitivity", 0, 1, path)
    check_range(rep, doc, "backchannel_frequency", 0, 1, path)
    check_range(rep, doc, "ambient_sound_volume", 0, 2, path)
    check_range(rep, doc, "reminder_trigger_ms", 1, None, path)
    check_range(rep, doc, "reminder_max_count", 0, None, path, integer=True)
    check_range(rep, doc, "begin_message_delay_ms", 0, 5000, path, integer=True)
    check_range(rep, doc, "ring_duration_ms", 5000, 300000, path, integer=True)
    check_range(rep, doc, "end_call_after_silence_ms", 10000, None, path, integer=True)
    check_range(rep, doc, "max_call_duration_ms", 60000, 7200000, path, integer=True)
    check_range(rep, doc, "voicemail_detection_timeout_ms", 5000, 180000, path, integer=True)

    check_enum(rep, doc, "ambient_sound", AMBIENT_SOUNDS, path)
    check_enum(rep, doc, "voice_emotion", VOICE_EMOTIONS, path)
    check_enum(rep, doc, "stt_mode", STT_MODES, path)
    check_enum(rep, doc, "vocab_specialization", VOCAB, path)
    check_enum(rep, doc, "denoising_mode", DENOISE, path)

    if doc.get("stt_mode") == "custom":
        cfg = doc.get("custom_stt_config")
        if not isinstance(cfg, dict):
            rep.error(path, "stt_mode=custom requires `custom_stt_config`")
        else:
            check_enum(rep, cfg, "provider", ASR_PROVIDERS, f"{path}.custom_stt_config", nullable=False)
            if "endpointing_ms" not in cfg:
                rep.error(f"{path}.custom_stt_config", "requires `endpointing_ms`")
    elif doc.get("custom_stt_config") not in (None,) and doc.get("stt_mode") != "custom":
        rep.warn(f"{path}.custom_stt_config", "only used when stt_mode is \"custom\"")

    we = doc.get("webhook_events")
    if isinstance(we, list):
        for i, e in enumerate(we):
            if e in CHAT_WEBHOOK_EVENTS - VOICE_WEBHOOK_EVENTS:
                rep.error(f"{path}.webhook_events[{i}]",
                          f"{e!r} is a chat event; voice agents use call_*/transfer_* events")
            elif e not in VOICE_WEBHOOK_EVENTS:
                rep.error(f"{path}.webhook_events[{i}]", f"unknown voice webhook event {e!r}")

    pd = doc.get("pronunciation_dictionary")
    if isinstance(pd, list):
        for i, entry in enumerate(pd):
            ep = f"{path}.pronunciation_dictionary[{i}]"
            if not isinstance(entry, dict):
                rep.error(ep, "entry must be an object")
                continue
            for req in ("word", "alphabet", "phoneme"):
                if not entry.get(req):
                    rep.error(ep, f"missing required `{req}`")
            check_enum(rep, entry, "alphabet", {"ipa", "cmu"}, ep, nullable=False)

    vm = doc.get("voicemail_option")
    if isinstance(vm, dict):
        act = vm.get("action")
        if not isinstance(act, dict):
            rep.error(f"{path}.voicemail_option", "requires `action`")
        else:
            at = act.get("type")
            if at in {"prompt", "static_text"}:
                check_string(rep, act, "text", f"{path}.voicemail_option.action", required=True)
            elif at not in {"hangup", "bridge_transfer"}:
                rep.error(f"{path}.voicemail_option.action.type",
                          f"invalid action type {at!r} (prompt|static_text|hangup|bridge_transfer)")
        check_string(rep, vm, "detection_prompt", f"{path}.voicemail_option", maxlen=2000)
    ivr = doc.get("ivr_option")
    if isinstance(ivr, dict):
        act = ivr.get("action")
        if not isinstance(act, dict) or act.get("type") != "hangup":
            rep.error(f"{path}.ivr_option.action", "ivr_option action currently supports only {\"type\": \"hangup\"}")
    cs = doc.get("call_screening_option")
    if isinstance(cs, dict):
        check_string(rep, cs, "agent_identity", f"{path}.call_screening_option",
                     required=True, minlen=1, maxlen=100)
        check_string(rep, cs, "call_purpose", f"{path}.call_screening_option",
                     required=True, minlen=1, maxlen=300)

    dtmf = doc.get("user_dtmf_options")
    if isinstance(dtmf, dict):
        check_range(rep, dtmf, "digit_limit", 1, 50, f"{path}.user_dtmf_options")
        check_range(rep, dtmf, "timeout_ms", 1000, 15000, f"{path}.user_dtmf_options", integer=True)
        tk = dtmf.get("termination_key")
        if tk is not None and (not isinstance(tk, str) or not re.match(r"^[0-9*#]$", tk)):
            rep.error(f"{path}.user_dtmf_options.termination_key",
                      "must be a single digit, '*', or '#'")

    pcad = doc.get("post_call_analysis_data")
    if isinstance(pcad, list):
        for i, item in enumerate(pcad):
            p = f"{path}.post_call_analysis_data[{i}]"
            if isinstance(item, dict) and item.get("type") == "system-presets" and \
                    item.get("name") in {"chat_summary", "chat_successful"}:
                rep.error(f"{p}.name",
                          f"{item['name']!r} is a chat preset; voice uses call_summary/call_successful")
            else:
                validate_analysis_data(rep, item, p, presets=VOICE_PRESET_NAMES,
                                       preset_type_label="voice")
    if doc.get("post_call_analysis_model") is not None and \
            doc["post_call_analysis_model"] not in KNOWN_LLM_MODELS:
        rep.warn(f"{path}.post_call_analysis_model",
                 f"{doc['post_call_analysis_model']!r} not in the known model list")
    for f in ("analysis_successful_prompt", "analysis_summary_prompt",
              "analysis_user_sentiment_prompt"):
        check_string(rep, doc, f, path, maxlen=2000)

    validate_pii_guardrail_handbook(rep, doc, path, VOICE_HANDBOOK)

    if strict_unknown:
        for k in doc:
            if k in camel or k in VOICE_AGENT_FIELDS or k in AGENT_READONLY_FIELDS \
                    or k in HANDLED_IN_COMMON:
                continue
            if k in CHAT_ONLY_FIELDS:
                hint = RENAME_HINTS.get(k, "chat-agent-only field")
                rep.error(f"{path}.{k}", f"does not belong on a voice agent — {hint}")
            elif k in RENAME_HINTS:
                rep.error(f"{path}.{k}", RENAME_HINTS[k])
            else:
                rep.warn(f"{path}.{k}", "unknown field for a voice agent")
        for k in AGENT_READONLY_FIELDS & set(doc):
            rep.warn(f"{path}.{k}", "read-only/server-assigned field; strip before POST /create-agent")


def validate_chat_agent(rep, doc, path="$", strict_unknown=True):
    camel = check_camelcase_keys(rep, doc, CHAT_AGENT_FIELDS | AGENT_READONLY_FIELDS, path)
    _validate_agent_common(rep, doc, path)
    check_range(rep, doc, "end_chat_after_silence_ms", 120000, 259200000, path, integer=True)

    we = doc.get("webhook_events")
    if isinstance(we, list):
        for i, e in enumerate(we):
            if e in VOICE_WEBHOOK_EVENTS - CHAT_WEBHOOK_EVENTS:
                rep.error(f"{path}.webhook_events[{i}]",
                          f"{e!r} is a voice event; chat agents use chat_started/chat_ended/"
                          "chat_analyzed/transcript_updated")
            elif e not in CHAT_WEBHOOK_EVENTS:
                rep.error(f"{path}.webhook_events[{i}]", f"unknown chat webhook event {e!r}")

    pcad = doc.get("post_chat_analysis_data")
    if isinstance(pcad, list):
        for i, item in enumerate(pcad):
            p = f"{path}.post_chat_analysis_data[{i}]"
            if isinstance(item, dict) and item.get("type") == "system-presets" and \
                    item.get("name") in {"call_summary", "call_successful"}:
                rep.error(f"{p}.name",
                          f"{item['name']!r} is a voice preset; chat uses chat_summary/chat_successful")
            else:
                validate_analysis_data(rep, item, p, presets=CHAT_PRESET_NAMES,
                                       preset_type_label="chat")
    if doc.get("post_chat_analysis_model") is not None and \
            doc["post_chat_analysis_model"] not in KNOWN_LLM_MODELS:
        rep.warn(f"{path}.post_chat_analysis_model",
                 f"{doc['post_chat_analysis_model']!r} not in the known model list")

    validate_pii_guardrail_handbook(rep, doc, path, CHAT_HANDBOOK)

    if strict_unknown:
        for k in doc:
            if k in camel or k in CHAT_AGENT_FIELDS or k in AGENT_READONLY_FIELDS \
                    or k in HANDLED_IN_COMMON:
                continue
            if k in VOICE_ONLY_FIELDS:
                hint = RENAME_HINTS.get(k, "voice-agent-only field — remove it")
                rep.error(f"{path}.{k}", f"does not belong on a chat agent — {hint}")
            elif k in RENAME_HINTS:
                rep.error(f"{path}.{k}", RENAME_HINTS[k])
            else:
                rep.warn(f"{path}.{k}", "unknown field for a chat agent")
        for k in AGENT_READONLY_FIELDS & set(doc):
            rep.warn(f"{path}.{k}",
                     "read-only/server-assigned field; strip before POST /create-chat-agent")


# --------------------------------------------------------------------------
# Kind detection & bundles
# --------------------------------------------------------------------------

def looks_like_flow(d):
    return isinstance(d, dict) and isinstance(d.get("nodes"), list) and (
        "model_choice" in d or "start_node_id" in d or "conversation_flow_id" in d
        or "global_prompt" in d or "start_speaker" in d)


def looks_like_llm(d):
    # A bare {type, llm_id} response_engine reference must NOT qualify —
    # require actual LLM content fields.
    return isinstance(d, dict) and not looks_like_flow(d) and any(
        k in d for k in ("general_prompt", "general_tools", "states", "starting_state",
                         "begin_message")) and "response_engine" not in d


def looks_like_agent(d):
    return isinstance(d, dict) and ("response_engine" in d or "voice_id" in d)


def agent_kind(d):
    """Return (kind, mixed_note). Majority vote when contaminated with both kinds' fields."""
    voice_sig = set(d) & VOICE_ONLY_FIELDS
    chat_sig = set(d) & CHAT_ONLY_FIELDS
    if voice_sig and chat_sig:
        kind = "voice-agent" if len(voice_sig) >= len(chat_sig) else "chat-agent"
        note = (f"document mixes voice-only fields {sorted(voice_sig)} with chat-only fields "
                f"{sorted(chat_sig)} — validating as {kind} by majority signal; "
                "pass --kind to override")
        return kind, note
    if voice_sig:
        return "voice-agent", None
    if chat_sig:
        return "chat-agent", None
    return None, None  # ambiguous


def detect_kind(doc):
    if not isinstance(doc, dict):
        return None
    # explicit bundle wrappers seen in dashboard exports over time
    engine_child = None
    agent_child = None
    for k, v in doc.items():
        if k == "response_engine":
            continue  # id reference, not an embedded engine payload
        if isinstance(v, dict):
            if looks_like_flow(v) or looks_like_llm(v):
                engine_child = engine_child or (k, v)
            elif looks_like_agent(v):
                agent_child = agent_child or (k, v)
    if engine_child and (agent_child or looks_like_agent(doc)):
        return "bundle"
    if looks_like_agent(doc) and engine_child:
        return "bundle"
    if looks_like_flow(doc):
        return "conversation-flow"
    if looks_like_llm(doc):
        return "retell-llm"
    if looks_like_agent(doc):
        kind, _ = agent_kind(doc)
        return kind or "agent-ambiguous"
    return None


def validate_bundle(rep, doc, path="$"):
    rep.warn(path, "detected a dashboard-style export bundle; the wrapper format is "
             "undocumented and version-dependent — validating recognizable parts. "
             "For import repair, diff against a fresh export from the target dashboard "
             "(see references/import-export.md).")
    validated_any = False
    wrapper_keys = {k for k, v in doc.items()
                    if k != "response_engine" and isinstance(v, dict)
                    and (looks_like_flow(v) or looks_like_llm(v) or looks_like_agent(v))}
    # agent portion: top-level itself, or a child
    if looks_like_agent(doc):
        kind, note = agent_kind(doc)
        kind = kind or "voice-agent"
        if note:
            rep.warn(path, note)
        (validate_voice_agent if kind == "voice-agent" else validate_chat_agent)(
            rep, doc, path, strict_unknown=False)
        validated_any = True
    for k, v in doc.items():
        if not isinstance(v, dict) or k == "response_engine":
            continue
        p = f"{path}.{k}"
        if looks_like_flow(v):
            validate_conversation_flow(rep, v, p, strict_unknown=False)
            validated_any = True
        elif looks_like_llm(v):
            validate_retell_llm(rep, v, p, strict_unknown=False)
            validated_any = True
        elif looks_like_agent(v):
            kind, note = agent_kind(v)
            kind = kind or "voice-agent"
            if note:
                rep.warn(p, note)
            (validate_voice_agent if kind == "voice-agent" else validate_chat_agent)(
                rep, v, p, strict_unknown=False)
            validated_any = True
    # consistency: engine type vs embedded payload
    agent_obj = doc if looks_like_agent(doc) else next(
        (v for v in doc.values() if looks_like_agent(v)), None)
    if isinstance(agent_obj, dict):
        ret = (agent_obj.get("response_engine") or {}).get("type")
        has_flow = looks_like_flow(doc) or any(looks_like_flow(v) for v in doc.values()
                                               if isinstance(v, dict))
        has_llm = any(looks_like_llm(v) for v in doc.values() if isinstance(v, dict))
        if ret == "retell-llm" and has_flow and not has_llm:
            rep.error(path, "response_engine.type is retell-llm but the bundle embeds "
                      "conversation-flow data")
        if ret == "conversation-flow" and has_llm and not has_flow:
            rep.error(path, "response_engine.type is conversation-flow but the bundle embeds "
                      "retell-llm data")
    if not validated_any:
        rep.warn(path, "could not identify agent/engine payloads inside the bundle")
    # engine wrapper keys in dashboard exports are legitimately camelCase — drop that noise
    rep.issues = [(s, p, m) for (s, p, m) in rep.issues
                  if not (m.startswith("camelCase key") and
                          any(p == f"{path}.{wk}" for wk in wrapper_keys))]


# --------------------------------------------------------------------------
# Entry
# --------------------------------------------------------------------------

def dup_key_hook(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError(f"duplicate key {k!r} in the same object")
        seen[k] = v
    return seen


def validate_file(filename, kind):
    rep = Report(filename)
    try:
        with open(filename, "r", encoding="utf-8-sig") as f:
            raw = f.read()
    except OSError as e:
        rep.error("$", f"cannot read file: {e}")
        return rep
    try:
        doc = json.loads(raw, object_pairs_hook=dup_key_hook)
    except ValueError as e:
        if isinstance(e, json.JSONDecodeError):
            rep.error("$", f"invalid JSON at line {e.lineno} col {e.colno}: {e.msg} "
                      "(check trailing commas, comments, unquoted keys, smart quotes)")
        else:
            rep.error("$", f"invalid JSON: {e}")
        return rep

    if kind == "auto":
        kind = detect_kind(doc)
        if kind is None:
            rep.error("$", "could not detect document kind (not a Retell agent/LLM/flow/bundle); "
                      "pass --kind explicitly")
            return rep
        if kind == "agent-ambiguous":
            rep.warn("$", "agent kind ambiguous (no voice_id and no kind-specific fields); "
                     "validating as chat agent — pass --kind voice-agent if this is a voice agent")
            kind = "chat-agent"
        elif kind in ("voice-agent", "chat-agent"):
            _, note = agent_kind(doc)
            if note:
                rep.warn("$", note)
        print(f"  detected kind: {kind}")

    if kind == "voice-agent":
        validate_voice_agent(rep, doc)
    elif kind == "chat-agent":
        validate_chat_agent(rep, doc)
    elif kind == "retell-llm":
        validate_retell_llm(rep, doc)
    elif kind == "conversation-flow":
        validate_conversation_flow(rep, doc)
    elif kind == "bundle":
        validate_bundle(rep, doc)
    return rep


def main():
    ap = argparse.ArgumentParser(description="Offline validator for Retell agent JSON.")
    ap.add_argument("files", nargs="+", help="JSON file(s) to validate")
    ap.add_argument("--kind", default="auto",
                    choices=["auto", "voice-agent", "chat-agent", "retell-llm",
                             "conversation-flow", "bundle"])
    args = ap.parse_args()

    total_errors = 0
    for fn in args.files:
        print(f"\n=== {fn} ===")
        rep = validate_file(fn, args.kind)
        for sev, path, msg in rep.issues:
            print(f"  [{sev}] {path}: {msg}")
        e, w = len(rep.errors), len(rep.warnings)
        total_errors += e
        print(f"  -> {e} error(s), {w} warning(s)" + ("  ✔ structurally valid" if e == 0 else ""))
    sys.exit(1 if total_errors else 0)


if __name__ == "__main__":
    main()
