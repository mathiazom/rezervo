FROM python:3.10.9-bullseye

RUN apt-get update && apt-get install -y \
    cron \
    figlet

# Set local timezone (for cron)
RUN ln -sf /usr/share/zoneinfo/Europe/Amsterdam /etc/localtime

# Ensure sufficient resource limits (prevents 'Too many open files' for cron jobs)
COPY docker/limits_mods.conf .
RUN cat ./limits_mods.conf >> /etc/security/limits.conf

WORKDIR /app

RUN curl -sSL https://install.python-poetry.org | python3 - -y --version 1.3.1

RUN /root/.local/bin/poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock README.md ./

COPY rezervo rezervo

RUN /root/.local/bin/poetry install --only main

COPY docker/entrypoint.sh .
RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "8000"]