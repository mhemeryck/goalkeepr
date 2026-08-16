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

## Development

Enter the reproducible development environment:

```console
devenv shell
```

Apply migrations and start the ASGI development server:

```console
migrate
server
```

Run the quality checks:

```console
test
lint
typecheck
```

The development server uses SQLite unless `POSTGRES_HOST` is set.

## License

Goalkeepr is available under the MIT License.
