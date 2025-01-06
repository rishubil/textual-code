FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY --from=builder --chown=1000:1000 /app /app
RUN addgroup --system --gid 1000 appuser \
    && adduser --home /home/appuser --system --uid 1000 --gid 1000 appuser
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["python", "src/run.py"]
# CMD ["fastapi", "dev", "--host", "0.0.0.0", "/app/src/uv_docker_example"]