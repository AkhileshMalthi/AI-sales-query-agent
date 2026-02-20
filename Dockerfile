FROM python:3.11-slim

# Install uv (from official image), curl, and sqlite3
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first for cache optimization
COPY pyproject.toml uv.lock ./

# Install dependencies (without the project itself for caching)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source code
COPY . .

# Install the project
RUN uv sync --frozen --no-dev

# Ensure the data directory exists
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]