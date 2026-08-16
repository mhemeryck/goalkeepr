# Goalkeepr Development Guidance

## Product

- Small, mobile-first Django and HTMX app for youth football scores
- Local first release: Docker Compose, Django, PostgreSQL
- Fast, resilient score entry with large phone-friendly controls
- Django built-ins before dependencies or custom abstractions
- Server-rendered templates and HTMX; no SPA or separate frontend API

## Python

- Latest stable Python and Django at scaffold time
- `uv` for dependencies and commands
- ASGI via Uvicorn
- Async, function-based Django views
- Procedural code; OOP only where Django requires it
- Full type annotations; mypy checks
- UTC timestamps

## Quality

- Focused behavior test before application changes where practical
- pytest function-based tests
- Ruff formatting and linting
- Relevant tests and checks before completion

## Iteration Workflow

- Define each iteration with the agent.
- Record the high-level iteration requirements in `docs/analysis.md` and commit them before implementation.
- Start a new agent session to implement the recorded iteration in one shot.
- The implementation session must inspect the iteration and determine the necessary work.
- When requirements leave questions open, make a fair best-effort decision and continue.

## Frontend

- Plain HTML, CSS, JavaScript, and HTMX
- Locally bundled Pico CSS
- Minimal, mobile-first interface

## Tooling

- `devenv` tooling
- Nushell configuration in `devenv.yaml`
- Nushell over Bash for commands and scripts
- No Justfile
- Automation scripts in devenv configuration

## Operations

- `docker compose` for local services
- No Kubernetes, production deployment, or external services without explicit request
