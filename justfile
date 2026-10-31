uv := "uv run --project validators --all-packages"

# List recipes
default:
    @just --list

# Run all linters and the structure check
lint:
    {{uv}} ruff check .
    {{uv}} ruff format --check .
    {{uv}} codespell
    {{uv}} yamllint .
    npx --yes markdownlint-cli2 "**/*.md" "#node_modules" "#.venv" "#validators/.venv" "#templates/*/template"
    {{uv}} pfe-check-structure .

# Auto-format Python
fmt:
    {{uv}} ruff check --fix .
    {{uv}} ruff format .

# Run validator tests
test:
    {{uv}} pytest validators
