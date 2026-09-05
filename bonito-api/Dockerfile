# bonito-api — image (BON-003). Installs bonito-store from PyPI as a dependency.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV BONITO_API_PORT=8100
EXPOSE 8100

CMD ["bonito-api", "serve"]