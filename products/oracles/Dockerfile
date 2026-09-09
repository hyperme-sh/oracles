FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY core/lib/controlplane-db ./core/lib/controlplane-db
COPY core/events ./core/events
COPY core/lib/controlplane-core ./core/lib/controlplane-core
COPY products/oracles ./products/oracles
RUN uv sync --frozen --no-dev --package oracles-service
ENV PYTHONPATH=/app/core/lib/controlplane-core/src:/app/core/lib/controlplane-db/src:/app/core/events/src:/app/products/oracles/src
WORKDIR /app/products/oracles
CMD ["uv", "run", "--project", "/app/products/oracles", "python", "-m", "oracles_service.main"]
