# syntax=docker/dockerfile:1
# Lambda container image for the API (spec 0001). Build from the repo root:
#   make build-api
# Stage 1 installs the engine and API into a virtual environment with uv.
# It then generates the seeded synthetic market (spec 0006) into /data.

FROM --platform=linux/amd64 python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, for layer caching.
COPY pyproject.toml uv.lock .python-version ./
COPY engine/pyproject.toml engine/pyproject.toml
COPY services/api/pyproject.toml services/api/pyproject.toml
RUN uv sync --frozen --no-dev --no-install-workspace --package swing-api

# Then the workspace packages themselves, installed as regular (non editable) packages.
COPY engine engine
COPY services/api services/api
RUN uv sync --frozen --no-dev --no-editable --package swing-api

# The synthetic market, generated at build time and never committed (doc 02 §3, spec 0006).
RUN /app/.venv/bin/python -m engine.synthetic --seed 42 --out /data

# Stage 2: slim runtime with the pinned Lambda Web Adapter.
FROM --platform=linux/amd64 python:3.12-slim
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter
COPY --from=build /app/.venv /app/.venv
COPY --from=build /data /data
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DATA_MODE=synthetic \
    SYNTHETIC_DATA_DIR=/data \
    AWS_LWA_PORT=8000 \
    AWS_LWA_READINESS_CHECK_PATH=/api/v1/health
WORKDIR /app
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
