FROM python:3.11.14-slim-trixie

# Python optimizations
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv (from official image), curl, and sqlite3
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy dependency files first for cache optimization
COPY pyproject.toml uv.lock ./

# Install dependencies (without the project itself for caching)
RUN uv sync --frozen --all-extras --no-install-project

# Copy application source code
COPY . .

# Install the project (including dev dependencies for in-container pytest)
RUN uv sync --frozen --all-extras

# Ensure the data directory exists and set ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app

EXPOSE 8000

# Run as non-root user
USER appuser

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]