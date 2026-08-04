PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
export PYTHONPATH := packages/shared/src:services/api_gateway/src:services/news_intelligence/src:services/risk/src:services/execution/src:services/llm_reasoning/src:services/portfolio/src:services/prediction/src:services/market_data/src:services/company_announcements/src:services/macro/src:services/geopolitical/src:services/sentiment/src:services/learning/src:services/backtesting/src

.PHONY: bootstrap install test test-news lint up down logs migrate bootstrap-env run-api run-news run-market run-announcements

bootstrap-env:
	@test -f .env || cp .env.example .env

bootstrap: bootstrap-env
	@test -d .venv || python3 -m venv .venv
	$(PIP) install -U pip
	$(MAKE) install
	@echo "Bootstrap complete. Run: make test"

install:
	$(PIP) install -e packages/shared
	$(PIP) install -e services/api_gateway
	$(PIP) install -e "services/news_intelligence"
	$(PIP) install -e services/risk
	$(PIP) install -e services/execution
	$(PIP) install -e services/llm_reasoning
	$(PIP) install -e services/portfolio
	$(PIP) install -e services/prediction
	$(PIP) install -e services/market_data
	$(PIP) install -e services/company_announcements
	$(PIP) install -e services/macro
	$(PIP) install -e services/geopolitical
	$(PIP) install -e services/sentiment
	$(PIP) install -e services/learning
	$(PIP) install -e services/backtesting
	$(PIP) install pytest pytest-asyncio httpx "fastapi[standard]" slowapi email-validator celery numpy python-multipart eval_type_backport 'bcrypt<4.1'

test:
	$(PYTHON) -m pytest packages/shared/tests services/news_intelligence/tests services/api_gateway/tests services/risk/tests services/llm_reasoning/tests services/portfolio/tests services/market_data/tests services/company_announcements/tests services/macro/tests services/geopolitical/tests services/sentiment/tests services/prediction/tests services/learning/tests services/backtesting/tests services/execution/tests tests/integration -q

test-news:
	$(PYTHON) -m pytest services/news_intelligence/tests -q

lint:
	$(PYTHON) -m ruff check packages services || true

up: bootstrap-env
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f $(SVC)

migrate:
	@echo "Schema applied via docker postgres init (infra/db/migrations/001_init.sql)"

run-api:
	$(PYTHON) -m uvicorn api_gateway.main:app --reload --port 8000

run-news:
	$(PYTHON) -m uvicorn news_intelligence.api.main:app --reload --port 8001

run-market:
	$(PYTHON) -m uvicorn market_data.api.main:app --reload --port 8002

run-announcements:
	$(PYTHON) -m uvicorn company_announcements.api.main:app --reload --port 8003
