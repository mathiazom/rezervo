FROM python:3.10-bookworm

RUN apt-get update && apt-get install -y \
    cron \
    figlet

# set local timezone (for cron)
RUN ln -sf /usr/share/zoneinfo/Europe/Amsterdam /etc/localtime

# ensure sufficient resource limits (prevents 'Too many open files' for cron jobs)
COPY docker/limits_mods.conf .
RUN cat ./limits_mods.conf >> /etc/security/limits.conf

WORKDIR /app

ENV POETRY_HOME=/opt/poetry

RUN python3 -m venv $POETRY_HOME

ENV PATH="$POETRY_HOME/bin:$PATH"

RUN pip install poetry==1.3.1

RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock README.md ./

COPY rezervo rezervo

RUN poetry install --only main

# install Playwright browser and required deps
RUN playwright install --with-deps firefox

COPY docker/entrypoint.sh .
RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "8000"]