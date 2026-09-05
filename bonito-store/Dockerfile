# bonito-store — image (BON-002).
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV BONITO_STORE_PORT=8000
EXPOSE 8000

CMD ["bonito-store", "serve"]