FROM python:3.13-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY app ./app
COPY scripts ./scripts
USER app

FROM base AS test
USER root
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY pyproject.toml .
COPY tests ./tests
USER app
CMD ["pytest", "-q", "-p", "no:cacheprovider"]
# This is test task done by Roman Nadkernychnyi. For recruitment purposes only. 

FROM base AS runtime
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
