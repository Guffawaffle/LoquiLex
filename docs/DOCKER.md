# Docker notes for LoquiLex

This file documents minimal Docker usage notes, GPU prerequisites, and recommended persistent-volume patterns.

**Prerequisites (GPU mode)**

- Linux: Install the NVIDIA Container Toolkit (https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) so containers can access GPUs via `--gpus` or Compose `deploy.resources.reservations.devices` with `capabilities: [gpu]`.
- Windows / macOS (Docker Desktop): Ensure Docker Desktop is updated and GPU support is enabled in Docker Desktop settings.
- Compose GPU usage often reserves a GPU with something like:

```yaml
# Example Compose snippet (GPU override file)
services:
  loquilex-app:
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
```

Multi-GPU users may need `count: all` or explicit `device_ids` depending on their Compose/runtime version.

**Healthcheck**

The production Dockerfile includes a healthcheck that probes the FastAPI settings endpoint:

```
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
  CMD curl -fsS "http://localhost:${LX_API_PORT:-8000}/settings" || exit 1
```

This allows orchestrators to detect when the app is ready.

**Persistent model/cache volume (recommended)**

Large models and artifacts should be persisted on the host to avoid re-downloading across container runs. Example pattern:

- Host directory: `./models`
- Container mount: `/app/models`
- Example `docker run`:

```bash
mkdir -p ./models
docker run -v "${PWD}/models:/app/models" -e LX_MODELS_DIR=/app/models -p 8000:8000 loquilex:latest
```

If your deployment uses Compose, add a bind mount under the service's `volumes:` section. If the app is not wired to `LX_MODELS_DIR`, you can still store model files in a known host directory and mount them into the container at the location the model loader expects.

**Notes**

- The repo's CI Dockerfile is `Dockerfile.ci` and is used for CI-parity builds. The production image should follow the same pattern of copying only runtime requirements to keep cache-friendly layers.
- This document intentionally avoids changing runtime wiring; it provides operational guidance only.
