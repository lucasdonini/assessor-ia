help:
	@echo 'First, run `make prepare-environment` and create .env.app/.env.compose from their examples'
	@echo 'Now you are ready to run with `make up`'

dev: export LOG_LEVEL = DEBUG
dev: check
	uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --timeout-graceful-shutdown 10

up: export LOG_LEVEL = INFO
up: export LOG_TO_FILE = false
up:
	uv run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 10

prepare-environment:
	uv sync
	@echo 'Copy .env.example to .env and complete the blanks with your variables'

upgrade-db:
	uv run python -m alembic upgrade head

downgrade-db:
	uv run python -m alembic downgrade -1

check:
	uv run -m ruff format \
	&& uv run -m ruff check --fix \
	&& uv run -m mypy .

build-frontend:
	npm run --prefix frontend build

build: upgrade-db check
	docker compose up --build

test:
	uv run pytest -m 'integration or not integration'
