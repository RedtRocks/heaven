#!/usr/bin/env pwsh
<#
.SYNOPSIS
Run all Keepsake tests: backend pytest, web lint, and web build.

.DESCRIPTION
This script runs:
1. Backend tests via `cd backend && uv run pytest -q`
2. Web linting and build (if web/package.json exists)

Prints a clear pass/fail summary and exits with non-zero if any step fails.

.EXAMPLE
PS> .\scripts\test.ps1
#>

$ErrorActionPreference = "Stop"

# ANSI color codes for output
$GREEN = "`e[32m"
$RED = "`e[31m"
$YELLOW = "`e[33m"
$RESET = "`e[0m"

Write-Host "${YELLOW}=== Keepsake Test Suite ===${RESET}`n"

# Helper to run a command and track success
function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )
    Write-Host "${YELLOW}Running: $Name${RESET}"
    try {
        & $Command
        Write-Host "${GREEN}✓ $Name passed${RESET}`n"
        return $true
    }
    catch {
        Write-Host "${RED}✗ $Name failed${RESET}`n"
        Write-Error $_
        return $false
    }
}

$all_passed = $true

# Backend tests
$backend_passed = Run-Step "backend pytest" {
    Push-Location backend
    try {
        uv run pytest -q
    }
    finally {
        Pop-Location
    }
}
$all_passed = $all_passed -and $backend_passed

# Web tests (only if web/package.json exists)
if (Test-Path "web/package.json") {
    $lint_passed = Run-Step "web lint" {
        Push-Location web
        try {
            pnpm lint
        }
        finally {
            Pop-Location
        }
    }
    $all_passed = $all_passed -and $lint_passed

    $build_passed = Run-Step "web build" {
        Push-Location web
        try {
            pnpm build
        }
        finally {
            Pop-Location
        }
    }
    $all_passed = $all_passed -and $build_passed
}
else {
    Write-Host "${YELLOW}Skipping web tests (web/package.json not found)${RESET}`n"
}

# Final summary
Write-Host "${YELLOW}=== Test Summary ===${RESET}"
if ($all_passed) {
    Write-Host "${GREEN}All tests passed!${RESET}"
    exit 0
}
else {
    Write-Host "${RED}Some tests failed.${RESET}"
    exit 1
}
