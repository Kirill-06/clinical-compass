# Клинический компас — основные команды разработки. `make help` — список.

BACKEND := backend
# PYTHONPATH дублирует editable-установку: на macOS она иногда игнорируется (скрытые .pth).
UV := cd $(BACKEND) && PYTHONPATH=src uv run
AI := cd ai_service && PYTHONPATH=src:../backend/src uv run
FLUTTER ?= flutter

.DEFAULT_GOAL := help
.PHONY: help setup lint format typecheck test test-backend test-ai test-flutter check web run migrate seed up down deploy deploy-landing

help: ## Показать команды
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[1m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Установить зависимости backend и Flutter
	cd $(BACKEND) && uv sync
	cd ai_service && uv sync
	$(FLUTTER) pub get

lint: ## Линтеры: ruff + flutter analyze
	$(UV) ruff check src tests
	$(UV) ruff format --check src tests
	$(AI) ruff check src tests
	$(AI) ruff format --check src tests
	$(FLUTTER) analyze

format: ## Автоформатирование
	$(UV) ruff format src tests
	$(UV) ruff check --fix src tests
	$(AI) ruff format src tests
	$(AI) ruff check --fix src tests
	dart format lib test

typecheck: ## mypy --strict
	$(UV) mypy src tests
	$(AI) mypy

test-backend: ## Тесты backend (pytest)
	$(UV) pytest

test-ai: ## Тесты сервиса AI-извлечения
	$(AI) pytest

test-flutter: ## Тесты Flutter (виджет-тесты поднимают настоящий backend)
	$(FLUTTER) test

test: test-backend test-ai test-flutter ## Все тесты

check: lint typecheck test ## Всё, что проверяет CI

web: ## Собрать Flutter Web в build/web
	$(FLUTTER) build web --release --no-web-resources-cdn

run: web ## Локальный стенд на http://localhost:8080 (SQLite, демо-данные)
	cd $(BACKEND) && CC_WEB_DIR=../build/web PYTHONPATH=src uv run clinical-compass serve --port 8080

migrate: ## Применить миграции к CC_DATABASE_URL
	$(UV) clinical-compass migrate

seed: ## Загрузить демо-данные в пустую базу
	$(UV) clinical-compass seed

up: ## Docker: PostgreSQL + приложение
	docker compose up --build -d
	@echo "→ http://localhost:$${APP_PORT:-8080}"

down: ## Остановить Docker-стенд
	docker compose down

deploy: ## Выкатить стенд my.onco-core.ru (веб собирается здесь, на сервере — только backend)
	./scripts/deploy.sh app

deploy-landing: ## Выкатить лендинг onco-core.ru
	./scripts/deploy.sh landing
