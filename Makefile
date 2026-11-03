.PHONY: install run test lint format typecheck clean

PYTHON = .venv/bin/python
PIP = .venv/bin/pip

install:
	python3.12 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

run:
	$(PYTHON) -m uvicorn app.main:app --reload

test:
	$(PYTHON) -m pytest -v

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

typecheck:
	$(PYTHON) -m mypy app

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf build dist *.egg-info