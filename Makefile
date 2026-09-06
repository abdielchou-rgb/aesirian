# Æsirian Makefile
# Common development tasks

.PHONY: help install test migrate upgrade downgrade lint format typecheck clean run-mcp run-mcp-sse run-mcp-http

help:
	@echo "Æsirian Development Commands:"
	@echo "  make install      - Install dependencies with uv"
	@echo "  make test         - Run pytest"
	@echo "  make migrate      - Create new migration (alembic revision --autogenerate)"
	@echo "  make upgrade      - Apply migrations (alembic upgrade head)"
	@echo "  make downgrade    - Rollback last migration (alembic downgrade -1)"
	@echo "  make lint         - Run ruff"
	@echo "  make format       - Run ruff format"
	@echo "  make typecheck    - Run mypy"
	@echo "  make run-mcp      - Run MCP server via mcp_server_fast.py (stdio)"
	@echo "  make run-mcp-sse  - Run MCP server via mcp_server_fast.py (SSE on port 8765)"
	@echo "  make run-mcp-http - Run MCP server via mcp_server_fast.py (HTTP on port 8765)"
	@echo "  make clean        - Remove cache files"

install:
	uv sync --all-extras

test:
	uv run pytest tests/ -v --tb=short

migrate:
	uv run alembic revision --autogenerate -m "$(MSG)"

upgrade:
	uv run alembic upgrade head

downgrade:
	uv run alembic downgrade -1

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy core/

# 统一 MCP 入口：mcp_server_fast.py（M1-3 · 旧根目录 mcp_server.py 已 deprecated，
# 仅 tests/test_mcp_server.py 等旧引用保留兼容）
run-mcp:
	uv run python mcp_server_fast.py --transport stdio

run-mcp-sse:
	uv run python mcp_server_fast.py --transport sse --host 127.0.0.1 --port 8765

run-mcp-http:
	uv run python mcp_server_fast.py --transport http --host 127.0.0.1 --port 8765

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache 2>/dev/null || true

# Database operations
db-shell:
	sqlite3 aesirian.db

db-backup:
	cp aesirian.db aesirian.db.backup.$(date +%Y%m%d_%H%M%S)

# Development helpers
dev-setup: install
	uv run pre-commit install

check-all: lint typecheck test