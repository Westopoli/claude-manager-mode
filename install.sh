#!/usr/bin/env bash
# manager-mode installer for Claude Code and Codex.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Westopoli/claude-manager-mode/main/install.sh | bash
#   ./install.sh [--only claude|codex] [--dry-run] [--list] [--check]
#                [--accounts-root DIR] [--no-accounts]

set -euo pipefail

REPO_URL="https://github.com/Westopoli/claude-manager-mode"
SKILLS=(manager-mode manager-mode-hardcore swarm-shared)
LEGACY=(swarm swarm-spawn swarm-review swarm-post-review swarm-merge)
ONLY=""
DRY_RUN=false
LIST=false
CHECK=false
NO_ACCOUNTS=false
ACCOUNTS_ROOT="${CLAUDE_ACCOUNTS_ROOT:-${HOME}/claude-accounts}"
TMP=""

usage() {
  cat <<'EOF'
Usage: install.sh [--only claude|codex] [--dry-run] [--list] [--check]
                  [--accounts-root DIR] [--no-accounts]

Installs manager-mode, manager-mode-hardcore, and swarm-shared into every
detected supported client, on this machine, for every account.

Targets:
  $CLAUDE_CONFIG_DIR (or ~/.claude)   primary Claude Code config
  ~/claude-accounts/*/.claude         additional Claude Code accounts
  $CODEX_HOME (or ~/.codex)           Codex

Options:
  --list           show detected targets and their installed versions, then exit
  --check          compare each target against this source; exit 1 on drift
  --dry-run        show what would be installed, change nothing
  --only C         restrict to claude or codex
  --accounts-root  where to look for additional accounts (default ~/claude-accounts)
  --no-accounts    primary config dir only; skip additional accounts
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
    --check) CHECK=true; shift ;;
    --no-accounts) NO_ACCOUNTS=true; shift ;;
    --accounts-root)
      [[ $# -ge 2 ]] || { echo "--accounts-root requires a directory" >&2; exit 2; }
      ACCOUNTS_ROOT="$2"; shift 2 ;;
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

# Every Claude config dir on this machine. The primary one, plus any account
# under ACCOUNTS_ROOT. Multi-account setups are why a single install used to be
# impossible: the installer only ever knew about CLAUDE_CONFIG_DIR, so the other
# accounts silently kept whatever version they were last given.
CLAUDE_HOMES=()
add_claude_home() {
  local dir="$1" resolved existing
  [[ -d "$dir" ]] || return 0
  resolved="$(cd "$dir" && pwd)"
  for existing in ${CLAUDE_HOMES[@]+"${CLAUDE_HOMES[@]}"}; do
    [[ "$existing" == "$resolved" ]] && return 0
  done
  CLAUDE_HOMES+=("$resolved")
}
collect_claude_homes() {
  # CLAUDE_CONFIG_DIR points at whichever account is active right now, so it
  # alone is never the whole machine. Always include the default ~/.claude as
  # well, then every account dir — the point of this command is that one run
  # covers everything, with no "which account am I in?" to remember.
  add_claude_home "$CLAUDE_HOME"
  add_claude_home "${HOME}/.claude"
  "$NO_ACCOUNTS" && return 0
  [[ -d "$ACCOUNTS_ROOT" ]] || return 0
  local candidate
  for candidate in "$ACCOUNTS_ROOT"/*/.claude; do
    add_claude_home "$candidate"
  done
  return 0
}
collect_claude_homes

# A config dir that does not exist yet is not a target — creating one would
# install into an account the user does not have.
[[ ${#CLAUDE_HOMES[@]} -eq 0 ]] && CLAUDE_HOMES=()

CLAUDE_DETECTED=false
CODEX_DETECTED=false
# An account dir that exists is itself the evidence — the `claude` binary is
# shared across accounts, so per-account command detection says nothing.
[[ ${#CLAUDE_HOMES[@]} -gt 0 ]] && CLAUDE_DETECTED=true
if [[ ${#CLAUDE_HOMES[@]} -eq 0 ]] && detect_client claude "$CLAUDE_HOME"; then
  # `claude` on PATH but no config dir yet: first install, use the default.
  CLAUDE_HOMES=("$CLAUDE_HOME")
  CLAUDE_DETECTED=true
fi
detect_client codex "$CODEX_CONFIG_HOME" && CODEX_DETECTED=true

# ---- version stamping ----
# Each installed skill dir carries a VERSION file so drift is detectable
# instead of being discovered months later by a cascade running rules that
# were removed from source long ago.
source_version() {
  local sha date_stamp
  if command -v git >/dev/null 2>&1 && git -C "$SRC/.." rev-parse --short HEAD >/dev/null 2>&1; then
    sha="$(git -C "$SRC/.." rev-parse --short HEAD)"
  else
    sha="nogit"
  fi
  date_stamp="$(date -u +%Y-%m-%d)"
  printf '%s %s\n' "$sha" "$date_stamp"
}

installed_version() {
  local dir="$1"
  if [[ -f "$dir/VERSION" ]]; then cat "$dir/VERSION"; else echo "unstamped"; fi
}

selected_client() { [[ -z "$ONLY" || "$ONLY" == "$1" ]]; }
print_detection() {
  printf 'Claude Code: %s (%s)\n' \
    "$([[ "$CLAUDE_DETECTED" == true ]] && echo detected || echo not\ detected)" \
    "$([[ ${#CLAUDE_HOMES[@]} -gt 0 ]] && printf '%s' "${CLAUDE_HOMES[*]}" || printf '%s' "$CLAUDE_HOME")"
  printf 'Codex:       %s (%s)\n' \
    "$([[ "$CODEX_DETECTED" == true ]] && echo detected || echo not\ detected)" "$CODEX_CONFIG_HOME"
}

TARGETS=()
if selected_client claude && "$CLAUDE_DETECTED"; then
  for home in "${CLAUDE_HOMES[@]}"; do TARGETS+=("claude:$home/skills"); done
fi
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

SRC_VERSION="$(source_version)"

report_targets() {
  local drifted=0 target client skills_dir skill dest have
  printf 'Source:  %s\n' "$SOURCE_LABEL"
  printf 'Version: %s\n\n' "$SRC_VERSION"
  for target in "${TARGETS[@]}"; do
    IFS=: read -r client skills_dir <<<"$target"
    printf '%s: %s\n' "$client" "$skills_dir"
    for skill in "${SKILLS[@]}"; do
      dest="$skills_dir/$skill"
      if [[ ! -d "$dest" ]]; then
        printf '  %-22s not installed\n' "$skill"
        drifted=1
      else
        have="$(installed_version "$dest")"
        if [[ "$have" == "$SRC_VERSION" ]]; then
          printf '  %-22s %s\n' "$skill" "$have"
        else
          printf '  %-22s %s  <- DRIFT (source: %s)\n' "$skill" "$have" "$SRC_VERSION"
          drifted=1
        fi
      fi
    done
  done
  return "$drifted"
}

if "$LIST"; then
  print_detection
  echo
  report_targets || true
  exit 0
fi

if "$CHECK"; then
  if report_targets; then
    echo
    echo "All targets match source."
    exit 0
  fi
  echo
  echo "Drift found. Run ./install.sh to bring every target up to source." >&2
  exit 1
fi

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
for skill in "${SKILLS[@]}"; do
  cp -R "$SRC/$skill" "$STAGE_ROOT/skills/$skill"
  printf '%s\n' "$SRC_VERSION" > "$STAGE_ROOT/skills/$skill/VERSION"
done

# Backups go NEXT TO skills/, never inside it. A client scans its skills dir
# and loads whatever it finds, so a backup left in place registers as a second,
# stale, invocable copy of the skill it was meant to preserve — the exact
# confusion an upgrade is supposed to remove.
backup_root_for() {
  printf '%s/skill-backups' "$(dirname "$1")"
}

backup_path() {
  local skills_dir="$1" name="$2" timestamp root candidate suffix=0
  root="$(backup_root_for "$skills_dir")"
  mkdir -p "$root"
  timestamp="$(date +%Y%m%d%H%M%S)"
  candidate="${root}/${name}.bak.${timestamp}"
  while [[ -e "$candidate" ]]; do
    suffix=$((suffix + 1))
    candidate="${root}/${name}.bak.${timestamp}.${suffix}"
  done
  printf '%s' "$candidate"
}

# Any backup a previous version left inside skills/ is still being loaded as a
# skill. Relocate on sight rather than waiting for the user to notice.
relocate_stray_backups() {
  local skills_dir="$1" stray root
  root="$(backup_root_for "$skills_dir")"
  for stray in "$skills_dir"/*.bak.*; do
    [[ -e "$stray" ]] || continue
    mkdir -p "$root"
    mv "$stray" "$root/$(basename "$stray")"
    echo "  $(basename "$stray"): moved out of skills/ into skill-backups/"
  done
}

for target in "${TARGETS[@]}"; do
  IFS=: read -r client skills_dir <<<"$target"
  echo "Installing for $client into $skills_dir"
  mkdir -p "$skills_dir"
  relocate_stray_backups "$skills_dir"
  for legacy in "${LEGACY[@]}"; do
    legacy_path="$skills_dir/$legacy"
    if [[ -e "$legacy_path" ]]; then
      backup="$(backup_path "$skills_dir" "$legacy")"
      mv "$legacy_path" "$backup"
      echo "  $legacy: backed up to skill-backups/$(basename "$backup")"
    fi
  done
  for skill in "${SKILLS[@]}"; do
    dest="$skills_dir/$skill"
    if [[ -e "$dest" ]]; then
      backup="$(backup_path "$skills_dir" "$skill")"
      mv "$dest" "$backup"
      echo "  $skill: backed up to skill-backups/$(basename "$backup")"
    fi
    cp -R "$STAGE_ROOT/skills/$skill" "$dest"
    echo "  $skill: installed"
  done
done

echo
echo "Installed version $SRC_VERSION to ${#TARGETS[@]} target(s)."
echo "Verify any time with: ./install.sh --check"
echo "Restart or refresh each installed client, then invoke /manager-mode."
