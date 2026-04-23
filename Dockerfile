FROM python:3.10-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY semanticscholar_mcp_server ./semanticscholar_mcp_server

RUN uv sync --frozen --no-dev

CMD ["uv", "run", "semanticscholar-mcp-server"]
