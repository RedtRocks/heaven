# Runs one Antigravity agent on a workstream, in its worktree, streaming output to this window and a log.
# Usage: run-agy.ps1 -Name voice [-Model gemini-3.8-flash-high]
param(
    [Parameter(Mandatory)] [string] $Name,
    [string] $Model = "gemini-3.8-flash-high"
)

$wt = Join-Path (Split-Path (Split-Path $PSScriptRoot)) "..\heaven-wt\$Name" | Resolve-Path
$logDir = Join-Path $PSScriptRoot "..\..\..\heaven-wt\logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "$Name.log"

$Host.UI.RawUI.WindowTitle = "agent: $Name ($Model)"
Set-Location $wt
Write-Host "== Agent '$Name' in $wt using $Model ==" -ForegroundColor Cyan

$prompt = "Read docs/agents/common-rules.md and docs/agents/task-$Name.md in this directory, then complete the task fully and autonomously. Commit your work on the current branch. Do not push."

agy -p $prompt --model $Model --dangerously-skip-permissions --print-timeout 0 --output-format stream-json 2>&1 |
    Tee-Object -FilePath $log

Write-Host "== Agent '$Name' finished (exit $LASTEXITCODE) ==" -ForegroundColor Green
"__DONE__ exit=$LASTEXITCODE" | Add-Content $log
