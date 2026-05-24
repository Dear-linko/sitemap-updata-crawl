PYTHON ?= .venv/bin/python
CONFIG ?= ./config.yaml
BASELINE ?= ./data/baseline.json
REPORTS_DIR ?= ./data/reports
HTML_DIR ?= ./.gh-pages

.PHONY: help venv install doctor init-state run-once html-rebuild test

help:
	@echo "Available targets:"
	@echo "  make venv        - Create virtual environment (.venv)"
	@echo "  make install     - Install project and dev dependencies"
	@echo "  make doctor      - Check interpreter and required packages"
	@echo "  make init-state  - Initialize baseline and reports directory"
	@echo "  make run-once    - Run one monitoring cycle"
	@echo "  make html-rebuild - Rebuild HTML reports from daily JSON files"
	@echo "  make test        - Run tests"

venv:
	python3 -m venv .venv

install: venv
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e '.[dev]'

doctor:
	@echo "PYTHON=$(PYTHON)"
	@$(PYTHON) -c "import sys; print(sys.executable)"
	@$(PYTHON) -c "import yaml, pydantic, httpx; print('deps ok')"

init-state:
	$(PYTHON) -m monitor init-state --baseline $(BASELINE) --reports-dir $(REPORTS_DIR)

run-once:
	$(PYTHON) -m monitor run-once --config $(CONFIG) --baseline $(BASELINE) --reports-dir $(REPORTS_DIR)

html-rebuild:
	$(PYTHON) -m monitor html-rebuild --reports-dir $(REPORTS_DIR) --output-dir $(HTML_DIR)

test:
	$(PYTHON) -m pytest -q
