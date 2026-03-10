.PHONY: format lint typecheck test test-unit test-workflow test-regression test-integration smoke-replay acceptance acceptance-gate trace-kpi ci container-smoke check validate-structure

format:
	python -m ruff format .

lint:
	python -m ruff check channel_adapters config core openclaw_adapter storage tools workflows tests scripts

typecheck:
	python -m mypy channel_adapters config core openclaw_adapter storage tools workflows tests scripts

test:
	python -m pytest

test-unit:
	python -m pytest tests/unit

test-workflow:
	python -m pytest tests/workflow

test-regression:
	python -m pytest tests/regression

test-integration:
	python -m pytest tests/integration

smoke-replay:
	python -m pytest tests/integration/test_openclaw_gateway.py -q

acceptance:
	python -m scripts.run_acceptance --env dev

acceptance-gate: acceptance trace-kpi

trace-kpi:
	python -m scripts.trace_kpi --env dev --output storage/acceptance/trace_kpi_from_log.json

ci: validate-structure lint typecheck test-unit test-workflow test-regression test-integration smoke-replay

container-smoke:
	docker compose run --rm smoke

validate-structure:
	python scripts/validate_structure.py

check: validate-structure lint typecheck test-unit test-workflow test-regression test-integration smoke-replay
