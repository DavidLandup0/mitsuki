install:
	uv sync

format:
	uv run ruff check --select I,F401 --fix .
	uv run ruff format .

test:
	uv run coverage run -m pytest .
	uv run coverage report