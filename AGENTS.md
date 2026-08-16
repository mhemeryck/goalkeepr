# Goalkeepr Development Guidance

Goalkeepr is a small, mobile-first Django and HTMX application for recording youth football match scores.

Keep the first release local and runnable through Docker Compose with Django and PostgreSQL.

Use Django's built-in facilities before adding dependencies or custom abstractions.

Use server-rendered templates and HTMX interactions instead of SPA tooling or a separate frontend API.

Keep score entry resilient and easy to use on a phone with large, clear controls.

Write or update a focused test before changing application behavior when the behavior can be cleanly tested.

Run the relevant test suite and formatting or linting checks before declaring work complete.

Use `uv` for Python dependencies and commands.

Use `docker compose` for local services.

Do not introduce Kubernetes manifests, production deployment configuration, or external services unless explicitly requested.

Do not hand-write mocks.

Run `just generate` when generated mocks are required by an existing interface.

Do not create, amend, or push Git commits without explicit user approval.
