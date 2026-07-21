[CmdletBinding()]
param(
    [ValidateSet("claude", "codex")]
    [string]$Only,
    [switch]$DryRun,
    [switch]$List
)

$ErrorActionPreference = "Stop"
$REPO_URL = "https://github.com/Westopoli/claude-manager-mode"
$Skills = @("manager-mode", "manager-mode-hardcore", "swarm-shared")
$Legacy = @("swarm", "swarm-spawn", "swarm-review", "swarm-post-review", "swarm-merge")
$claudeHome = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME ".claude" }
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }

function Test-Client([string]$CommandName, [string]$ConfigHome) {
    return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue) -or (Test-Path -Path $ConfigHome -PathType Container)
}
function Show-Detection {
    $claudeState = if ($claudeDetected) { "detected" } else { "not detected" }
    $codexState = if ($codexDetected) { "detected" } else { "not detected" }
    Write-Output "Claude Code: $claudeState ($claudeHome)"
    Write-Output "Codex:       $codexState ($codexHome)"
}
function Get-BackupPath([string]$Path) {
    $timestamp = Get-Date -Format "yyyyMMddHHmmss"
    $candidate = "${Path}.bak.$timestamp"
    $suffix = 0
    while (Test-Path -LiteralPath $candidate) {
        $suffix++
        $candidate = "${Path}.bak.$timestamp.$suffix"
    }
    return $candidate
}

$claudeDetected = Test-Client "claude" $claudeHome
$codexDetected = Test-Client "codex" $codexHome
if ($List) { Show-Detection; exit 0 }

$targets = @()
if ((-not $Only -or $Only -eq "claude") -and $claudeDetected) { $targets += @{ Name = "claude"; SkillsDir = (Join-Path $claudeHome "skills") } }
if ((-not $Only -or $Only -eq "codex") -and $codexDetected) { $targets += @{ Name = "codex"; SkillsDir = (Join-Path $codexHome "skills") } }
if ($targets.Count -eq 0) {
    if ($Only) { Write-Output "Requested client '$Only' was not detected; nothing installed." }
    else { Write-Output "No supported clients detected; nothing installed." }
    exit 0
}

$tmp = $null
$stageRoot = $null
try {
    if ($MyInvocation.MyCommand.CommandType -eq 'ExternalScript') { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition }
    else { $scriptDir = $null }
    if ($scriptDir -and (Test-Path (Join-Path $scriptDir "skills"))) {
        $src = Join-Path $scriptDir "skills"
        $sourceLabel = "local checkout ($src)"
    } else {
        $tmp = Join-Path ([System.IO.Path]::GetTempPath()) "manager-mode-install-$([System.IO.Path]::GetRandomFileName())"
        Write-Output "Source: cloning $REPO_URL to temporary directory"
        git clone --depth 1 $REPO_URL $tmp | Out-Null
        $src = Join-Path $tmp "skills"
        $sourceLabel = "fresh clone"
    }
    foreach ($skill in $Skills) {
        if (-not (Test-Path (Join-Path $src "$skill\SKILL.md") -PathType Leaf)) { throw "Invalid source: missing $src\$skill\SKILL.md" }
    }
    if ($DryRun) {
        Write-Output "Dry run: source $sourceLabel"
        foreach ($target in $targets) { Write-Output "Would install $($Skills -join ', ') for $($target.Name) into $($target.SkillsDir)" }
        exit 0
    }
    $stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) "manager-mode-stage-$([System.IO.Path]::GetRandomFileName())"
    $stageSkills = Join-Path $stageRoot "skills"
    New-Item -ItemType Directory -Force -Path $stageSkills | Out-Null
    foreach ($skill in $Skills) { Copy-Item -Recurse -Path (Join-Path $src $skill) -Destination (Join-Path $stageSkills $skill) }
    foreach ($target in $targets) {
        Write-Output "Installing for $($target.Name) into $($target.SkillsDir)"
        New-Item -ItemType Directory -Force -Path $target.SkillsDir | Out-Null
        foreach ($legacy in $Legacy) {
            $legacyPath = Join-Path $target.SkillsDir $legacy
            if (Test-Path -LiteralPath $legacyPath) {
                $backup = Get-BackupPath $legacyPath
                Move-Item -LiteralPath $legacyPath -Destination $backup
                Write-Output "  $legacy: backed up to $(Split-Path -Leaf $backup)"
            }
        }
        foreach ($skill in $Skills) {
            $dest = Join-Path $target.SkillsDir $skill
            if (Test-Path -LiteralPath $dest) {
                $backup = Get-BackupPath $dest
                Move-Item -LiteralPath $dest -Destination $backup
                Write-Output "  $skill: backed up to $(Split-Path -Leaf $backup)"
            }
            Copy-Item -Recurse -Path (Join-Path $stageSkills $skill) -Destination $dest
            Write-Output "  $skill: installed"
        }
    }
    Write-Output "Done. Restart or refresh each installed client, then invoke /manager-mode."
} finally {
    if ($stageRoot) { Remove-Item -Recurse -Force $stageRoot -ErrorAction SilentlyContinue }
    if ($tmp) { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
}
