# Docker Deployment Guide

LoquiLex can be run in Docker containers for easy local deployment, including GPU support for WSL2 and Docker Desktop.

## Quick Start

### CPU-Only Deployment

```bash
# Build and run with CPU-only support
make docker-run

# Or manually:
docker-compose up -d
```

The application will be available at http://localhost:8000

### GPU-Enabled Deployment (WSL2/Docker Desktop)

```bash
# Build and run with GPU support  
make docker-gpu

# Or manually:
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

**Prerequisites for GPU support:**
- WSL2 with GPU drivers installed
- Docker Desktop with WSL2 backend
- NVIDIA Container Toolkit installed in WSL2
- Docker Compose version 3.8+

## Configuration

### Environment Variables

Create a `.env` file in the project root (use `.env.docker` as a template):

```bash
# Copy the template
cp .env.docker .env

# Edit configuration
nano .env
```

Key variables:
- `LX_DEVICE`: `auto`, `cpu`, or `cuda`  
- `LX_API_PORT`: FastAPI server port (default: 8000)
- `LX_ASR_MODEL`: Whisper model size (`tiny.en`, `base.en`, `small.en`, etc.)
- `LX_NLLB_MODEL`: Translation model (default: `facebook/nllb-200-distilled-600M`)
- `INSTALL_GPU_SUPPORT`: Set to `true` for GPU Docker builds

### Model Configuration

**CPU Models (recommended for lower resource usage):**
- ASR: `tiny.en`, `base.en`
- Translation: `facebook/nllb-200-distilled-600M`

**GPU Models (better quality, requires more VRAM):**
- ASR: `base.en`, `small.en`, `medium.en`  
- Translation: `facebook/nllb-200-1.3B`, `facebook/nllb-200-3.3B`

## Available Commands

### Build Commands
```bash
make docker-build      # Build CPU-only image
make docker-build-gpu  # Build GPU-enabled image
```

### Runtime Commands
```bash
make docker-run        # Start CPU-only deployment
make docker-gpu        # Start GPU-enabled deployment  
make docker-logs       # View container logs
make docker-stop       # Stop containers
make docker-clean      # Remove containers and images
make docker-shell      # Open shell in running container
```

### Manual Docker Compose

```bash
# CPU-only
docker-compose up -d

# GPU-enabled  
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## WSL2 GPU Setup

### Install NVIDIA Drivers (Windows Host)

1. Install latest NVIDIA Game Ready or Studio drivers (471.41+)
2. No additional drivers needed in WSL2

### Install Docker and NVIDIA Container Toolkit (WSL2)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install NVIDIA Container Toolkit  
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
    && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
    && curl -s -L https://nvidia.github.io/libnvidia-container/experimental/$distribution/libnvidia-container.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

### Verify GPU Access

```bash
# Test NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi

# Test LoquiLex GPU support
make docker-gpu
make docker-logs
```

## Persistent Data

Docker volumes are used for persistent storage:

- `loquilex_outputs`: Generated transcripts and translations
- `loquilex_models`: Cached Hugging Face models  
- `loquilex_whisper`: Cached Whisper models

### Accessing Output Files

Output files are available via HTTP at:
- http://localhost:8000/out/{session_id}/

Or access the volume directly:
```bash
docker volume inspect loquilex_outputs
```

## Troubleshooting

### Common Issues

**Container fails to start:**
```bash
# Check logs
make docker-logs

# Verify image built correctly
docker images | grep loquilex
```

**GPU not detected:**
```bash
# Verify NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi

# Check Docker daemon configuration
sudo cat /etc/docker/daemon.json
```

**Out of memory errors:**
```bash
# Use smaller models in .env:
LX_ASR_MODEL=tiny.en
LX_NLLB_MODEL=facebook/nllb-200-distilled-600M
```

**Network connectivity issues:**
```bash
# Verify port mapping
docker ps | grep loquilex

# Test health endpoint  
curl http://localhost:8000/healthz
```

### Performance Tuning

**For CPU-only systems:**
- Use `tiny.en` or `base.en` ASR models
- Use `facebook/nllb-200-distilled-600M` translation model  
- Increase `LX_PAUSE_FLUSH_SEC` to reduce CPU usage

**For GPU systems:**
- Use `base.en` or `small.en` ASR models
- Use `facebook/nllb-200-1.3B` translation model
- Monitor GPU memory with `nvidia-smi`

## Development

### Building Custom Images

```bash
# Development build with custom base image
docker build -f Dockerfile -t loquilex:dev .

# Multi-stage build for production
docker build -f Dockerfile --target base -t loquilex:base .
```

### Volume Mounts for Development

```bash
# Mount source code for live development
docker run -v $(pwd):/app -p 8000:8000 loquilex:dev
```

## Security Considerations

- Container runs as non-root user `loquilex`
- No sensitive data in environment variables
- Output directory isolated via volume mounts
- Health checks enabled for monitoring
- Resource limits can be set via Docker Compose

## Architecture

The Docker deployment includes:

1. **Application Container**: FastAPI server + built React UI
2. **Persistent Volumes**: Model cache and output storage  
3. **Health Checks**: Endpoint monitoring
4. **GPU Support**: NVIDIA runtime integration (optional)

The container serves both the API and UI from a single FastAPI process, eliminating the need for separate frontend/backend containers in development scenarios.