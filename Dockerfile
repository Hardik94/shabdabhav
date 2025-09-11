# Use official slim Python image
FROM python:3.11-slim

# Install system dependencies needed for audio and building packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only the pyproject.toml and lock files first to leverage Docker layer caching
# COPY pyproject.toml uv.lock* ./
COPY pyproject.toml ./

# Install uv and sync dependencies based on lock file, installs packages into system Python env
RUN pip install --no-cache-dir uv \
    && uv pip install --system .
    # && uv sync --locked

# Copy the rest of the application code
COPY api/ ./api/
COPY setup.py ./
# Expose server port as usual
EXPOSE 8000

# Ensure logs are streamed immediately
ENV PYTHONUNBUFFERED=1

# Optional: set pytorch cache dir for repeatability and speed
ENV TORCH_HOME=/app/.cache/torch

# Launch the app using uv CLI, matching the script in pyproject.toml
# CMD ["uv", "run", "fastapi", "start"]
CMD ["uv", "run", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
# uv run uvicorn api.app:app --host 0.0.0.0 --port 8000
