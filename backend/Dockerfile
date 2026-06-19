FROM python:3.12-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.11.17 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Path A (Codex subscription, DEC-026 / E3): the official `codex` CLI is required
# at runtime to bridge a user's subscription. Only needed when per-user Codex
# credentials are enabled; build with --build-arg INSTALL_CODEX=1 to include it.
ARG INSTALL_CODEX=0
RUN if [ "$INSTALL_CODEX" = "1" ]; then \
        apt-get update && apt-get install -y --no-install-recommends nodejs npm \
        && npm install -g @openai/codex @zed-industries/codex-acp \
        && apt-get clean && rm -rf /var/lib/apt/lists/*; \
    fi

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

EXPOSE 8000

CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000"]
