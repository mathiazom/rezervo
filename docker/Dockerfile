FROM python:3.10.9-bullseye

RUN apt update && apt -y install cron

# Set local timezone (for cron)
RUN ln -sf /usr/share/zoneinfo/Europe/Amsterdam /etc/localtime

WORKDIR /app

RUN curl -sSL https://install.python-poetry.org | python3 - -y --version 1.3.1

RUN /root/.local/bin/poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock README.md ./

COPY sit_rezervo sit_rezervo

RUN /root/.local/bin/poetry install --only main

COPY docker/entrypoint.sh .
RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
CMD ["--host", "0.0.0.0", "--port", "8000"]