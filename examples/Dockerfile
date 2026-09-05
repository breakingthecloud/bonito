# Bonito v0.1.0 — collector image (used by examples/docker-compose.yml).
# Packaging/Docker is formalized in BON-005; this keeps the example runnable.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 9187
ENV BONITO_PROM_PORT=9187

ENTRYPOINT ["bonito-collector"]