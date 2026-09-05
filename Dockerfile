# bonito-collector — image (BON-001).
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV BONITO_PROM_PORT=9187
EXPOSE 9187

ENTRYPOINT ["bonito-collector"]