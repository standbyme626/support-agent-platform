.PHONY: format lint typecheck test check validate-structure

format:
	python -m ruff format .

lint:
	python -m ruff check .

typecheck:
	python -m mypy .

test:
	python -m pytest

validate-structure:
	python scripts/validate_structure.py

check: validate-structure lint typecheck test
