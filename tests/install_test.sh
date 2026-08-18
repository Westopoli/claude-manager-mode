#!/usr/bin/env bash
# Isolated integration tests for install.sh. No real client config is touched.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER="$REPO_ROOT/install.sh"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT
BASE_PATH="/usr/bin:/bin"

fail() { echo "FAIL: $*" >&2; exit 1; }
assert_exists() { [[ -e "$1" ]] || fail "expected $1"; }
assert_missing() { [[ ! -e "$1" ]] || fail "did not expect $1"; }
assert_contains() { [[ "$1" == *"$2"* ]] || fail "expected output to contain: $2"; }

run_case() {
  local name="$1" clients="$2" args="$3"
  local case_root mock_bin claude_home codex_home
  case_root="$TEST_ROOT/$name"
  mock_bin="$case_root/bin"
  claude_home="$case_root/claude"
  codex_home="$case_root/codex"
  mkdir -p "$mock_bin"
  if [[ "$clients" == *claude* ]]; then printf '#!/bin/sh\n' > "$mock_bin/claude"; chmod +x "$mock_bin/claude"; fi
  if [[ "$clients" == *codex* ]]; then printf '#!/bin/sh\n' > "$mock_bin/codex"; chmod +x "$mock_bin/codex"; fi
  CASE_CLAUDE_HOME="$claude_home" CASE_CODEX_HOME="$codex_home" \
    CASE_OUTPUT="$(HOME="$case_root/home" CLAUDE_CONFIG_DIR="$claude_home" CODEX_HOME="$codex_home" PATH="$mock_bin:$BASE_PATH" bash "$INSTALLER" $args)"
}

run_case claude_only claude ""
assert_exists "$CASE_CLAUDE_HOME/skills/manager-mode/SKILL.md"
assert_exists "$CASE_CLAUDE_HOME/skills/manager-mode-hardcore/SKILL.md"
assert_exists "$CASE_CLAUDE_HOME/skills/swarm-shared/SKILL.md"
assert_exists "$CASE_CLAUDE_HOME/skills/manager-mode/agents/openai.yaml"
assert_missing "$CASE_CODEX_HOME/skills"

run_case codex_only codex ""
assert_exists "$CASE_CODEX_HOME/skills/manager-mode/SKILL.md"
assert_exists "$CASE_CODEX_HOME/skills/manager-mode-hardcore/SKILL.md"
assert_exists "$CASE_CODEX_HOME/skills/swarm-shared/agents/openai.yaml"
assert_missing "$CASE_CLAUDE_HOME/skills"

run_case dual "claude codex" ""
assert_exists "$CASE_CLAUDE_HOME/skills/manager-mode/SKILL.md"
assert_exists "$CASE_CODEX_HOME/skills/manager-mode/SKILL.md"
assert_exists "$CASE_CLAUDE_HOME/skills/manager-mode-hardcore/SKILL.md"
assert_exists "$CASE_CODEX_HOME/skills/manager-mode-hardcore/SKILL.md"

run_case only_codex "claude codex" "--only codex"
assert_missing "$CASE_CLAUDE_HOME/skills"
assert_exists "$CASE_CODEX_HOME/skills/swarm-shared/SKILL.md"
assert_exists "$CASE_CODEX_HOME/skills/manager-mode-hardcore/SKILL.md"

run_case dry_run codex "--dry-run"
assert_contains "$CASE_OUTPUT" "Would install"
assert_missing "$CASE_CODEX_HOME/skills"

run_case list claude "--list"
assert_contains "$CASE_OUTPUT" "Claude Code: detected"
assert_missing "$CASE_CLAUDE_HOME/skills"

run_case no_client "" ""
assert_contains "$CASE_OUTPUT" "No supported clients detected"
assert_missing "$CASE_CLAUDE_HOME/skills"
assert_missing "$CASE_CODEX_HOME/skills"

# A config-home directory is itself a detection signal, even without a binary.
config_case="$TEST_ROOT/config_home"
mkdir -p "$config_case/codex"
config_output="$(HOME="$config_case/home" CLAUDE_CONFIG_DIR="$config_case/claude" CODEX_HOME="$config_case/codex" PATH="$BASE_PATH" bash "$INSTALLER")"
assert_contains "$config_output" "Installing for codex"
assert_exists "$config_case/codex/skills/manager-mode/SKILL.md"
assert_exists "$config_case/codex/skills/manager-mode-hardcore/SKILL.md"

# Updating preserves the old pair through timestamped backups.
backup_case="$TEST_ROOT/backup"
mkdir -p "$backup_case/bin"
printf '#!/bin/sh\n' > "$backup_case/bin/codex"; chmod +x "$backup_case/bin/codex"
mkdir -p "$backup_case/codex/skills/manager-mode" "$backup_case/codex/skills/manager-mode-hardcore" "$backup_case/codex/skills/swarm-shared" "$backup_case/codex/skills/swarm"
printf 'old manager\n' > "$backup_case/codex/skills/manager-mode/SKILL.md"
printf 'old hardcore\n' > "$backup_case/codex/skills/manager-mode-hardcore/SKILL.md"
printf 'old shared\n' > "$backup_case/codex/skills/swarm-shared/SKILL.md"
HOME="$backup_case/home" CLAUDE_CONFIG_DIR="$backup_case/claude" CODEX_HOME="$backup_case/codex" PATH="$backup_case/bin:$BASE_PATH" bash "$INSTALLER" >/dev/null
assert_exists "$backup_case/codex/skills/manager-mode/SKILL.md"
# Backups live NEXT TO skills/, not inside it: a client loads everything it
# finds in skills/, so an in-place backup becomes a second stale copy of the
# skill, invocable by name.
assert_exists "$backup_case/codex/skill-backups/manager-mode.bak."*
assert_exists "$backup_case/codex/skill-backups/manager-mode-hardcore.bak."*
assert_exists "$backup_case/codex/skill-backups/swarm-shared.bak."*
assert_exists "$backup_case/codex/skill-backups/swarm.bak."*
if compgen -G "$backup_case/codex/skills/*.bak.*" > /dev/null; then
  fail "no backup may remain inside skills/"
fi

# A backup an older installer already left inside skills/ gets relocated.
stray_case="$TEST_ROOT/stray"
mkdir -p "$stray_case/codex/skills/manager-mode.bak.20200101000000"
printf 'stale\n' > "$stray_case/codex/skills/manager-mode.bak.20200101000000/SKILL.md"
HOME="$stray_case/home" CLAUDE_CONFIG_DIR="$stray_case/claude" \
  CODEX_HOME="$stray_case/codex" PATH="$BASE_PATH" bash "$INSTALLER" >/dev/null
assert_exists "$stray_case/codex/skill-backups/manager-mode.bak.20200101000000/SKILL.md"
if compgen -G "$stray_case/codex/skills/*.bak.*" > /dev/null; then
  fail "a pre-existing in-skills backup should be relocated on install"
fi

# --- multi-account coverage -------------------------------------------------
# The drift this closes was real: install.sh only ever knew CLAUDE_CONFIG_DIR,
# so a machine with several accounts kept stale skills in all but one of them
# and nothing reported it.
accounts_case="$TEST_ROOT/accounts"
mkdir -p "$accounts_case/home/claude-accounts/secondary/.claude" \
         "$accounts_case/home/claude-accounts/tertiary/.claude" \
         "$accounts_case/primary"
HOME="$accounts_case/home" CLAUDE_CONFIG_DIR="$accounts_case/primary" \
  CODEX_HOME="$accounts_case/nocodex" PATH="$BASE_PATH" bash "$INSTALLER" >/dev/null
assert_exists "$accounts_case/primary/skills/manager-mode/SKILL.md"
assert_exists "$accounts_case/home/claude-accounts/secondary/.claude/skills/manager-mode/SKILL.md"
assert_exists "$accounts_case/home/claude-accounts/tertiary/.claude/skills/manager-mode/SKILL.md"
assert_missing "$accounts_case/nocodex/skills"

# --no-accounts stays single-target for anyone who wants that.
solo_case="$TEST_ROOT/solo"
mkdir -p "$solo_case/home/claude-accounts/secondary/.claude" "$solo_case/primary"
HOME="$solo_case/home" CLAUDE_CONFIG_DIR="$solo_case/primary" \
  CODEX_HOME="$solo_case/nocodex" PATH="$BASE_PATH" bash "$INSTALLER" --no-accounts >/dev/null
assert_exists "$solo_case/primary/skills/manager-mode/SKILL.md"
assert_missing "$solo_case/home/claude-accounts/secondary/.claude/skills"

# --accounts-root relocates the search.
altroot_case="$TEST_ROOT/altroot"
mkdir -p "$altroot_case/elsewhere/acct/.claude" "$altroot_case/primary"
HOME="$altroot_case/home" CLAUDE_CONFIG_DIR="$altroot_case/primary" \
  CODEX_HOME="$altroot_case/nocodex" PATH="$BASE_PATH" bash "$INSTALLER" \
  --accounts-root "$altroot_case/elsewhere" >/dev/null
assert_exists "$altroot_case/elsewhere/acct/.claude/skills/manager-mode/SKILL.md"

# --- drift detection --------------------------------------------------------
check_case="$TEST_ROOT/check"
mkdir -p "$check_case/primary"
check_env=(HOME="$check_case/home" CLAUDE_CONFIG_DIR="$check_case/primary"
           CODEX_HOME="$check_case/nocodex" PATH="$BASE_PATH")

# Nothing installed yet: drift, non-zero exit.
if env "${check_env[@]}" bash "$INSTALLER" --check >/dev/null 2>&1; then
  fail "--check should exit non-zero before anything is installed"
fi

env "${check_env[@]}" bash "$INSTALLER" >/dev/null
assert_exists "$check_case/primary/skills/manager-mode/VERSION"
check_clean="$(env "${check_env[@]}" bash "$INSTALLER" --check)" \
  || fail "--check should exit 0 immediately after a successful install"
assert_contains "$check_clean" "All targets match source"

# A stale VERSION is exactly the Aug-7-vs-Aug-15 case that went unnoticed.
printf 'deadbee 1999-01-01\n' > "$check_case/primary/skills/manager-mode/VERSION"
if check_drift="$(env "${check_env[@]}" bash "$INSTALLER" --check 2>&1)"; then
  fail "--check should exit non-zero when an installed VERSION is stale"
fi
assert_contains "$check_drift" "DRIFT"

echo "install.sh tests: PASS"
