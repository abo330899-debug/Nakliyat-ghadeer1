#!/bin/bash
set -e

uv sync --no-interactive 2>/dev/null || true

npm install --no-fund --no-audit 2>/dev/null || true
