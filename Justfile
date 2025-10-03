set shell := ["bash", "-lc"]

sync:
	uv sync
	uv pip install -e .

check:
	uv run ruff format .
	uv run ruff check .
	uv run pyright

test: check
	uv run pytest --rootdir=src
