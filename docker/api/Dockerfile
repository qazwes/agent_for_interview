FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# 编译工具仅留在构建阶段。
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM builder AS test
RUN uv sync --frozen --no-install-project
COPY app/ app/
COPY conf/ conf/
COPY prompts/ prompts/
COPY tests/ tests/
COPY docker/mysql/ docker/mysql/
COPY database/ database/
COPY main.py LICENSE ./
CMD ["/app/.venv/bin/python", "-m", "pytest", "tests", "-q"]

FROM python:3.14-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 agent \
    && useradd --uid 10001 --gid agent --create-home agent
COPY --from=builder --chown=agent:agent /app/.venv /app/.venv
COPY --chown=agent:agent app/ app/
COPY --chown=agent:agent conf/ conf/
COPY --chown=agent:agent prompts/ prompts/
COPY --chown=agent:agent main.py LICENSE ./
USER agent
EXPOSE 8000
CMD ["sh", "-c", "python -m app.scripts.wait_for_services && exec uvicorn main:app --host 0.0.0.0 --port 8000"]
