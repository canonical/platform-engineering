.PHONY: lint fmt test

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run codespell
	uv run yamllint .
	npx --yes markdownlint-cli2 "**/*.md" "#node_modules" "#.venv" "#templates/*/template"
	uv run pfe-check-structure .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest
