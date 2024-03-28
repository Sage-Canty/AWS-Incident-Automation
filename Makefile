.PHONY: install lint test triage health

ENV    ?= dev
REGION ?= us-east-1

install:
	pip install -r requirements.txt -r requirements-dev.txt

lint:
	flake8 src/ tests/ --max-line-length=100
	black --check src/ tests/

test:
	pytest

triage:
	python -m src.cli --env $(ENV) --region $(REGION) triage --service $(SERVICE)

health:
	python -m src.cli --env $(ENV) --region $(REGION) health

logs:
	python -m src.cli --env $(ENV) --region $(REGION) logs --service $(SERVICE)
