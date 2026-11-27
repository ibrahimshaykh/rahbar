#!/usr/bin/env bash
# Runs the Assignment 03 test suite. Usage: bash scripts/test03_03.sh [pytest args]
if [ -x .venv/Scripts/python ]; then PY=.venv/Scripts/python; SEP=";"; else PY=.venv/bin/python; SEP=":"; fi
PYTHONPATH="tests_03${SEP}api${SEP}indexer${SEP}." exec "$PY" -m pytest -q -c tests_03/pytest_03.ini "$@"
