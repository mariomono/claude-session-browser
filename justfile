set shell := ["bash", "-euo", "pipefail", "-c"]

# list available commands
default:
    @just --list

# one-time setup after cloning: deps, git hooks, data dir, container images
setup:
    mkdir -p data
    cd backend && uv sync
    cd frontend && npm install
    uv run --project backend pre-commit install --install-hooks --hook-type pre-commit --hook-type commit-msg
    docker compose build

# re-sync deps and rebuild the images after code or dependency changes
update:
    cd backend && uv sync
    cd frontend && npm install
    docker compose build

# start the app in containers + the host launch agent -> http://localhost:43210
start:
    docker compose up -d
    mkdir -p data/launch
    nohup uv run --project backend python -m app.services.launch_agent >> data/launch/agent.log 2>&1 &
    @echo "Running at http://localhost:43210"

# stop and remove the containers, and stop the launch agent
stop:
    docker compose down
    [ -f data/launch/agent.pid ] && kill "$(cat data/launch/agent.pid)" 2>/dev/null || true

# tail container logs
logs:
    docker compose logs -f

# run the backend test suite
test:
    cd backend && uv run pytest

# lint, format check and type check the backend
lint:
    cd backend && uv run ruff check . && uv run ruff format --check . && uv run ty check
