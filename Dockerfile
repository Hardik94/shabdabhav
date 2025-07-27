# Use official slim Python image
FROM python:3.11-slim

# System dependencies for audio/model support
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy only the relevant files first for caching dependencies
COPY pyproject.toml ./
COPY tts_server/ ./tts_server/

# Install astral-uv and project dependencies in one step (no cache for minimal layer size)
RUN pip install --no-cache-dir astral-uv \
 && uv pip install --system .

# Expose port (match your FastAPI server)
EXPOSE 8000

# Ensure Python output is unbuffered
ENV PYTHONUNBUFFERED=1

# More efficient pytorch cache (optional)
ENV TORCH_HOME=/app/.cache/torch

# Launch with astral-uv in production mode (fastest)
CMD ["uv", "run", "fastapi", "start"]

