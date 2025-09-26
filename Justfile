set shell := ["bash", "-lc"]

sync:
	uvsync
	uv pip install -e .

test:
	uv run ruff format .
	uv run ruff check .
	uv run pyright
	uv run pytest
