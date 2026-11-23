#!/usr/bin/env bash
# Runs the Assignment 03 test suite. Usage: bash scripts/test03_03.sh [pytest args]
PY="${PY:-.venv/Scripts/python}"; [ -x "$PY" ] || PY=".venv/bin/python"
PYTHONPATH=tests_03 exec "$PY" -m pytest -q -c tests_03/pytest_03.ini "$@"
