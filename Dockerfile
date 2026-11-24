FROM python:3.12-slim

LABEL io.modelcontextprotocol.server.name="io.github.FrankXLT/agy-nexus-mcp"
LABEL org.opencontainers.image.source="https://github.com/FrankXLT/agy-nexus-mcp"
LABEL org.opencontainers.image.description="Dual-doorway MCP server for Antigravity IDE telemetry, session handoffs, and Quiet UI studio."
LABEL org.opencontainers.image.licenses="AGPL-3.0-or-later"

RUN apt-get update \
    && apt-get install -y --no-install-recommends git grep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1

EXPOSE 8765

ENTRYPOINT ["agy-nexus-mcp"]
