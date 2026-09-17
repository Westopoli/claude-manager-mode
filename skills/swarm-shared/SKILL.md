---
name: swarm-shared
description: Shared references, scripts, and templates used by /manager-mode. Not directly invocable. Do not call this skill — it exists only so the installer copies its assets into the Claude Code, Codex, or Antigravity skills directory, where /manager-mode resolves them at runtime.
---

# swarm-shared

This is a **support skill**, not an invocable one. At runtime `/manager-mode` resolves it as `$SWARM_SHARED_DIR`: `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/swarm-shared` in Claude Code, `${CODEX_HOME:-$HOME/.codex}/skills/swarm-shared` in Codex, or `${GEMINI_CONFIG_DIR:-$HOME/.gemini}/config/skills/swarm-shared` in Antigravity. It carries:

- `references/playbook.md` — theory and rationale behind the cascade
- `references/brief-template.md` — canonical leaf brief shape
- `references/config.md` — config file reference
- `references/evaluation-rubric.md` — review scoring rubric
- `scripts/check_invariants.py` — invariant audit helper
- `scripts/cascade_metrics.py` — records a cascade's token cost + outcome (Phase 7.2); `rates.json` beside it holds USD/MTok per model
- `agents/antigravity/swarm-leaf.md` — Antigravity subagent definition every leaf dispatch routes through (Claude Code and Codex use their own native delegation instead; see `manager-mode/SKILL.md`'s client delegation adapter)
- `templates/` — config templates

If you reached this file by reading it directly: nothing to do here. Invoke `/manager-mode` instead.
