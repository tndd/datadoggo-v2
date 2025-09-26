set shell := ["bash", "-lc"]

fmt:
	uv run ruff format .

check:
	uv run ruff check .

pyright:
	uv run pyright

pytest:
	uv run pytest

test: fmt check pyright pytest
