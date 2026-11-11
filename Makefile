.PHONY: sync test lint db-up db-down
sync:      ; uv sync
test:      ; uv run pytest
lint:      ; uv run ruff check . && uv run ruff format --check .
db-up:     ; docker compose up -d postgres
db-down:   ; docker compose down
