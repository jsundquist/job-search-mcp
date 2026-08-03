install:
    uv sync

test:
    uv run pytest

lint:
    uv run ruff check .

run:
    uv run job-search-mcp
