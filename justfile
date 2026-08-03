install:
    uv sync

test:
    uv run pytest

lint:
    uv run ruff check .

run:
    @echo "No server entrypoint yet — see docs/adr/ for design decisions made so far."
