FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SUPPORT_AGENT_ENV=dev \
    SUPPORT_AGENT_SQLITE_PATH=/app/storage/support-agent.db

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

CMD ["python", "scripts/healthcheck.py", "--env", "dev"]
