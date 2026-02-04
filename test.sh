#!/bin/bash
# Run unit tests for the API (FastAPI/Python)

set -e

echo "🔧 Ruff: lint + fix..."
.venv/bin/ruff check --fix .
.venv/bin/ruff format .

echo ""
echo "🧪 Running API unit tests..."
.venv/bin/python -m pytest tests/ -v

echo ""
echo "✅ All tests passed!"
