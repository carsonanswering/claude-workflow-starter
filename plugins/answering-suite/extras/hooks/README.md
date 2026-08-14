# Optional hooks & statusline (Answering kit)

Nothing in `extras/` auto-loads — wire these only if you want them.

What's here: `auto-session-title.sh` (names each session from your first prompt), `usage-dashboard.sh` (regenerates a Max-plan savings dashboard), `session-obsidian-log.py` and `session-self-improve.py` (SessionEnd journaling + lesson extraction — both write into Carson's Obsidian vault paths, so retarget before use), and `../statusline/caveman-statusline.sh`.

To enable: copy the scripts into `~/.claude/hooks/`, then merge `settings-snippet.json` into `~/.claude/settings.json`.

Note: the snippet here is a repaired version of the original. The original declared the `"UserPromptSubmit"` key twice, which valid-JSON parsers resolve by keeping only the last entry — silently dropping the auto-session-title hook. This copy merges both commands into one `UserPromptSubmit` array so both actually run.
