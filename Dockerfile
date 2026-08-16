FROM ghcr.io/astral-sh/uv:0.9.26 AS uv

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-group dev --no-install-project

COPY . .
RUN uv sync --frozen --no-group dev && \
    .venv/bin/python manage.py collectstatic --noinput && \
    useradd --create-home --uid 10001 app && \
    chown -R app:app /app

USER app
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "goalkeepr.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
