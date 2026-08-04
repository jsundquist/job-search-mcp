install:
    uv sync

test:
    uv run pytest

test-cov:
    uv run pytest --cov=src/job_search_mcp --cov-report=term-missing

lint:
    uv run ruff check .

run:
    uv run job-search-mcp
