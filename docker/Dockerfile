FROM python:3.14-bookworm

RUN apt-get update && apt-get install -y \
    cron \
    figlet

# set local timezone (for cron)
RUN ln -sf /usr/share/zoneinfo/Europe/Amsterdam /etc/localtime

# ensure sufficient resource limits (prevents 'Too many open files' for cron jobs)
COPY docker/limits_mods.conf .
RUN cat ./limits_mods.conf >> /etc/security/limits.conf

# install uv (https://docs.astral.sh/uv/guides/integration/docker/)
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/

WORKDIR /app

# install into the system environment so console scripts (rezervo, alembic,
# playwright) are available on PATH for the entrypoint and cron jobs
# https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# optimizations
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# install dependencies in a separate, cache-friendly layer from the project,
# so they are only reinstalled when pyproject.toml/uv.lock change
# https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY rezervo rezervo
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# install Playwright browser and required deps
RUN playwright install --with-deps firefox

COPY docker/entrypoint.sh .
RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
