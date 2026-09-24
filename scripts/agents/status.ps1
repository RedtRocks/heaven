# Live overview of every workstream: branch progress and each agent's latest activity.
# Usage: status.ps1 [-Watch]
param([switch] $Watch)

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$wtRoot = Join-Path $root "..\heaven-wt"

do {
    if ($Watch) { Clear-Host }
    Write-Host ("Keepsake agents - {0:HH:mm:ss}" -f (Get-Date)) -ForegroundColor Cyan
    foreach ($dir in Get-ChildItem $wtRoot -Directory | Where-Object Name -ne "logs") {
        $branch = git -C $dir.FullName branch --show-current
        $ahead = git -C $dir.FullName rev-list --count "main..HEAD"
        $dirty = (git -C $dir.FullName status --porcelain | Measure-Object).Count
        $last = git -C $dir.FullName log -1 --format="%cr: %s" "main..HEAD"
        $log = Join-Path $wtRoot "logs\$($dir.Name).log"
        $state = if (-not (Test-Path $log)) { "claude subagent / not started" }
                 elseif (Select-String -Path $log -Pattern "__DONE__" -Quiet) { "DONE" }
                 else { "running" }
        $report = Test-Path (Join-Path $dir.FullName "docs\agents\reports\$($branch -replace '/','-').md")
        Write-Host ("`n[{0}] {1}" -f $dir.Name, $branch) -ForegroundColor Yellow
        Write-Host ("  commits ahead: {0}   uncommitted files: {1}   report: {2}   agent: {3}" -f $ahead, $dirty, $report, $state)
        if ($last) { Write-Host "  last commit  $last" }
    }
    if ($Watch) { Start-Sleep 15 }
} while ($Watch)
