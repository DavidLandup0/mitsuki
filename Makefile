install:
	uv sync

format:
	uv run ruff check --select I,F401 --fix .
	uv run ruff format .

test:
	coverage run -m pytest --cov=mitsuki .