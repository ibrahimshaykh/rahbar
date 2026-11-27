SHELL := /bin/bash
PY ?= .venv/Scripts/python
.PHONY: test03 lint03 check03 compliance03
test03:
	bash scripts/test03_03.sh
lint03:
	$(PY) -m ruff check api/*_03.py indexer/*_03.py indexer/pipeline/*_03.py eval/*_03.py scripts/*_03.py tests_03
check03:
	$(PY) scripts/check_submission.py | grep -c FAIL || true
compliance03:
	bash scripts/compliance_check_03.sh
