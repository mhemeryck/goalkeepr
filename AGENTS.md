# Goalkeepr Development Guidance

## Product Specification

- [Product specification](docs/spec.md) as the source of truth for current behaviour, domain rules, and intended direction
- GitHub issues for implementation tracking without silent specification changes
- GitHub issue #13 as an idea inbox rather than committed scope
- Git history for superseded requirements and previous iterations

## Development Workflow

- Start from the [product specification](docs/spec.md) and one focused GitHub issue
- Treat issue #13 as idea intake only
- Promote an idea from issue #13 only after agreement on scope
- Request explicit approval before creating or restructuring GitHub issues or milestones
- Keep each issue independently deliverable with clear acceptance criteria
- Link the relevant specification section from the issue when applicable
- Update the specification only when current or intended product behaviour changes
- Add a focused behaviour test before application changes where practical
- Implement on a dedicated branch
- Run relevant tests, Ruff, and mypy before completion
- Open a pull request linked to the issue
- Use `Closes #<issue>` only when the pull request fully satisfies the issue
- Merge through the protected default branch after required checks
- Continue with the next unblocked issue in dependency order

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

## Markdown

- Concise fragments instead of full sentences
- No terminal periods for headings, list items, or short prose
- One statement per physical line
- No hard wrapping
- Markdown links for repository files and documentation

## Repository Layout

- Organization by product responsibility rather than implementation technology
- Self-contained deployable repository including application code, container build, application-specific infrastructure, Kubernetes resources, and CI/CD pipeline

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
