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
assert_exists "$backup_case/codex/skills/manager-mode.bak."*
assert_exists "$backup_case/codex/skills/manager-mode-hardcore.bak."*
assert_exists "$backup_case/codex/skills/swarm-shared.bak."*
assert_exists "$backup_case/codex/skills/swarm.bak."*

echo "install.sh tests: PASS"
