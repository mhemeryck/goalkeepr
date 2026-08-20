# Goalkeepr

Goalkeepr is a small, mobile-first score recorder for youth football matches.

## Docker Compose

Start the application and PostgreSQL:

```console
docker compose up --build
```

Create the initial household account in another terminal:

```console
docker compose exec app python manage.py createsuperuser
```

Open <http://localhost:8000> and log in with that account.

The PostgreSQL data is retained in the `postgres-data` Docker volume.
The household team defaults to `K.F.C. Sparta Kolmont`.
Set `TEAM_NAME` before starting Compose to override it.

## Container Development

Start the application and PostgreSQL with Docker Compose:

```console
docker compose up --build
```

The Compose setup is useful for verifying the application container together
with its external PostgreSQL dependency.

## Devenv Development

Start PostgreSQL, apply migrations, and launch the ASGI development server:

```console
devenv up -d server
```

Stop the PostgreSQL service when finished:

```console
devenv down
```

Run the quality checks:

```console
test
lint
typecheck
```

The devenv development server uses the devenv-managed PostgreSQL service.
PostgreSQL data is retained in devenv's state directory.

Run Django management commands through the database-configured wrapper:

```console
devenv shell -- manage createsuperuser
devenv shell -- manage shell
```

## License

Goalkeepr is available under the MIT License.
