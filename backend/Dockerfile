FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-group research --no-install-project
COPY app ./app
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
