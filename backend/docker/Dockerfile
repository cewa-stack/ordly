FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev || uv sync

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

VOLUME ["/app/data", "/app/logs", "/app/backups"]

CMD ["uv", "run", "sh", "-c", "alembic upgrade head && python -m app.main"]
