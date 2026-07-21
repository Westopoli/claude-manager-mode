#!/usr/bin/env bash
# manager-mode installer for Claude Code and Codex.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Westopoli/claude-manager-mode/main/install.sh | bash
#   ./install.sh [--only claude|codex] [--dry-run] [--list]

set -euo pipefail

REPO_URL="https://github.com/Westopoli/claude-manager-mode"
SKILLS=(manager-mode manager-mode-hardcore swarm-shared)
LEGACY=(swarm swarm-spawn swarm-review swarm-post-review swarm-merge)
ONLY=""
DRY_RUN=false
LIST=false
TMP=""

usage() {
  cat <<'EOF'
Usage: install.sh [--only claude|codex] [--dry-run] [--list]

Installs manager-mode, manager-mode-hardcore, and swarm-shared into every detected supported client.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --only)
      [[ $# -ge 2 ]] || { echo "--only requires claude or codex" >&2; exit 2; }
      ONLY="$2"
      [[ "$ONLY" == "claude" || "$ONLY" == "codex" ]] || { echo "--only must be claude or codex" >&2; exit 2; }
      shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --list) LIST=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-${HOME}/.claude}"
CODEX_CONFIG_HOME="${CODEX_HOME:-${HOME}/.codex}"

has_command() { command -v "$1" >/dev/null 2>&1; }
detect_client() {
  local client="$1" home="$2"
  has_command "$client" || [[ -d "$home" ]]
}

CLAUDE_DETECTED=false
CODEX_DETECTED=false
detect_client claude "$CLAUDE_HOME" && CLAUDE_DETECTED=true
detect_client codex "$CODEX_CONFIG_HOME" && CODEX_DETECTED=true

selected_client() { [[ -z "$ONLY" || "$ONLY" == "$1" ]]; }
print_detection() {
  printf 'Claude Code: %s (%s)\n' "$([[ "$CLAUDE_DETECTED" == true ]] && echo detected || echo not\ detected)" "$CLAUDE_HOME"
  printf 'Codex:       %s (%s)\n' "$([[ "$CODEX_DETECTED" == true ]] && echo detected || echo not\ detected)" "$CODEX_CONFIG_HOME"
}

if "$LIST"; then
  print_detection
  exit 0
fi

TARGETS=()
if selected_client claude && "$CLAUDE_DETECTED"; then TARGETS+=("claude:$CLAUDE_HOME/skills"); fi
if selected_client codex && "$CODEX_DETECTED"; then TARGETS+=("codex:$CODEX_CONFIG_HOME/skills"); fi

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  if [[ -n "$ONLY" ]]; then
    echo "Requested client '$ONLY' was not detected; nothing installed."
  else
    echo "No supported clients detected; nothing installed."
  fi
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd 2>/dev/null || pwd)"
if [[ -d "$SCRIPT_DIR/skills" ]]; then
  SRC="$SCRIPT_DIR/skills"
  SOURCE_LABEL="local checkout ($SRC)"
else
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo "Source: cloning $REPO_URL to temporary directory"
  git clone --depth 1 "$REPO_URL" "$TMP/repo" >/dev/null
  SRC="$TMP/repo/skills"
  SOURCE_LABEL="fresh clone"
fi

for skill in "${SKILLS[@]}"; do
  [[ -f "$SRC/$skill/SKILL.md" ]] || { echo "Invalid source: missing $SRC/$skill/SKILL.md" >&2; exit 1; }
done

if "$DRY_RUN"; then
  echo "Dry run: source $SOURCE_LABEL"
  for target in "${TARGETS[@]}"; do
    IFS=: read -r client destination <<<"$target"
    echo "Would install ${SKILLS[*]} for $client into $destination"
  done
  exit 0
fi

# Build a complete pair before changing any installed skill directory.
STAGE_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP" "$STAGE_ROOT"' EXIT
mkdir -p "$STAGE_ROOT/skills"
for skill in "${SKILLS[@]}"; do cp -R "$SRC/$skill" "$STAGE_ROOT/skills/$skill"; done

backup_path() {
  local path="$1" timestamp candidate suffix=0
  timestamp="$(date +%Y%m%d%H%M%S)"
  candidate="${path}.bak.${timestamp}"
  while [[ -e "$candidate" ]]; do
    suffix=$((suffix + 1))
    candidate="${path}.bak.${timestamp}.${suffix}"
  done
  printf '%s' "$candidate"
}

for target in "${TARGETS[@]}"; do
  IFS=: read -r client skills_dir <<<"$target"
  echo "Installing for $client into $skills_dir"
  mkdir -p "$skills_dir"
  for legacy in "${LEGACY[@]}"; do
    legacy_path="$skills_dir/$legacy"
    if [[ -e "$legacy_path" ]]; then
      backup="$(backup_path "$legacy_path")"
      mv "$legacy_path" "$backup"
      echo "  $legacy: backed up to $(basename "$backup")"
    fi
  done
  for skill in "${SKILLS[@]}"; do
    dest="$skills_dir/$skill"
    if [[ -e "$dest" ]]; then
      backup="$(backup_path "$dest")"
      mv "$dest" "$backup"
      echo "  $skill: backed up to $(basename "$backup")"
    fi
    cp -R "$STAGE_ROOT/skills/$skill" "$dest"
    echo "  $skill: installed"
  done
done

echo "Done. Restart or refresh each installed client, then invoke /manager-mode."
