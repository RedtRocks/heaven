#!/bin/bash
# Run all Keepsake tests: backend pytest, web lint, and web build.
#
# This script runs:
# 1. Backend tests via `cd backend && uv run pytest -q`
# 2. Web linting and build (if web/package.json exists)
#
# Prints a clear pass/fail summary and exits with non-zero if any step fails.

set -e

# ANSI color codes
GREEN='\033[32m'
RED='\033[31m'
YELLOW='\033[33m'
RESET='\033[0m'

echo -e "${YELLOW}=== Keepsake Test Suite ===${RESET}\n"

# Track overall pass/fail
all_passed=true

# Helper to run a command and track success
run_step() {
    local name="$1"
    local cmd="$2"

    echo -e "${YELLOW}Running: $name${RESET}"
    if eval "$cmd"; then
        echo -e "${GREEN}✓ $name passed${RESET}\n"
    else
        echo -e "${RED}✗ $name failed${RESET}\n"
        all_passed=false
    fi
}

# Backend tests
run_step "backend pytest" "cd backend && uv run pytest -q"

# Web tests (only if web/package.json exists)
if [ -f "web/package.json" ]; then
    run_step "web lint" "cd web && pnpm lint"
    run_step "web build" "cd web && pnpm build"
else
    echo -e "${YELLOW}Skipping web tests (web/package.json not found)${RESET}\n"
fi

# Final summary
echo -e "${YELLOW}=== Test Summary ===${RESET}"
if [ "$all_passed" = true ]; then
    echo -e "${GREEN}All tests passed!${RESET}"
    exit 0
else
    echo -e "${RED}Some tests failed.${RESET}"
    exit 1
fi
