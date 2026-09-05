# bonito-mcp — image (BON-004). Talks to bonito-api over HTTP.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8840

CMD ["bonito-mcp", "--transport", "sse", "--sse-port", "8840"]