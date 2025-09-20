# LoquiLex Production Runtime
# Supports CPU-only and GPU acceleration (CUDA) when available  
# Optimized for WSL2 and Docker Desktop with GPU passthrough
# 
# NOTE: This Dockerfile expects the UI to be pre-built (ui/app/dist exists)
#       Run `make ui-build` before building the Docker image

FROM python:3.12-slim

# Build arguments for flexibility
ARG INSTALL_GPU_SUPPORT=false

# Environment setup
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# System dependencies (minimal set)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first for better caching
COPY requirements.txt requirements-ci.txt requirements-dev.txt requirements-ml-cpu.txt requirements-ml-gpu.txt ./

# Install base dependencies
RUN pip install -r requirements.txt

# Conditionally install GPU or CPU ML dependencies  
RUN if [ "$INSTALL_GPU_SUPPORT" = "true" ] ; then \
        echo "Installing GPU ML dependencies..." && \
        pip install -r requirements-ml-gpu.txt; \
    else \
        echo "Installing CPU-only ML dependencies..." && \
        pip install -r requirements-ml-cpu.txt; \
    fi

# Copy source code (includes pre-built UI if available)
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash loquilex
RUN chown -R loquilex:loquilex /app

# Switch to non-root user
USER loquilex

# Set environment defaults for runtime
ENV LX_API_PORT=8000 \
    LX_UI_PORT=5173 \
    LX_DEVICE=auto \
    LX_OUT_DIR=/app/outputs \
    PYTHONPATH=/app

# Create output directory
RUN mkdir -p /app/outputs

# Expose API port
EXPOSE ${LX_API_PORT}

# Default command: start FastAPI server serving both API and built UI
CMD ["python", "-m", "loquilex.api.server"]