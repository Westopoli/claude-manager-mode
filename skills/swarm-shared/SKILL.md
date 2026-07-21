---
name: swarm-shared
description: Shared references, scripts, and templates used by /manager-mode. Not directly invocable. Do not call this skill — it exists only so the installer copies its assets into the Claude Code or Codex skills directory, where /manager-mode resolves them at runtime.
---

# swarm-shared

This is a **support skill**, not an invocable one. At runtime `/manager-mode` resolves it as `$SWARM_SHARED_DIR`: `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/swarm-shared` in Claude Code or `${CODEX_HOME:-$HOME/.codex}/skills/swarm-shared` in Codex. It carries:

- `references/playbook.md` — theory and rationale behind the cascade
- `references/brief-template.md` — canonical leaf brief shape
- `references/config.md` — config file reference
- `references/evaluation-rubric.md` — review scoring rubric
- `scripts/check_invariants.py` — invariant audit helper
- `templates/` — config templates

If you reached this file by reading it directly: nothing to do here. Invoke `/manager-mode` instead.
