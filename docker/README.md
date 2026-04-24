# OpenPathAI — Docker images (Phase 18)

Two Dockerfiles for two use cases:

| File | Base | Size | Best for |
| --- | --- | --- | --- |
| `Dockerfile.cpu` | `python:3.12-slim-bookworm` | ~ 350 MB | Laptops, CI, classroom demos, Gradio GUI |
| `Dockerfile.gpu` | `nvidia/cuda:12.3.2-runtime-ubuntu22.04` | ~ 6-8 GB | CUDA training runs + MedSAM2 / MedGemma inference |

Both images ship the `openpathai` CLI as the entrypoint. The
CPU image installs `.[gui,safety,audit]`; the GPU image adds
`[train,explain,mlflow]` so `torch` (CUDA), calibration,
Grad-CAM, and the MLflow sink all work.

---

## Build

```bash
# CPU (fast, small):
docker build -f docker/Dockerfile.cpu -t openpathai:cpu-local .

# GPU (needs nvidia-container-toolkit on the host):
docker build -f docker/Dockerfile.gpu -t openpathai:gpu-local .
```

First build pulls the base image + pipx chain; subsequent
builds use Docker's layer cache.

---

## Run

```bash
# Quick help — both images:
docker run --rm openpathai:cpu-local --help
docker run --rm --gpus all openpathai:gpu-local --help

# Gradio GUI exposed on :7860, with a volume mount so every
# run persists across container restarts:
docker run --rm -p 7860:7860 \
    -v "$HOME/.openpathai:/home/openpathai/.openpathai" \
    openpathai:cpu-local gui --host 0.0.0.0

# Full pipeline run on GPU:
docker run --rm --gpus all \
    -v "$HOME/.openpathai:/home/openpathai/.openpathai" \
    -v "$PWD/pipelines:/home/openpathai/pipelines" \
    openpathai:gpu-local \
    run /home/openpathai/pipelines/supervised_synthetic.yaml
```

The container runs as an unprivileged user (uid 1000) so the
bind-mounted `~/.openpathai` folder gets predictable
permissions. Change the `-v` source to anywhere you want
pipeline outputs to land.

---

## Quick GPU smoke test

```bash
docker run --rm --gpus all openpathai:gpu-local \
    -c "import torch; print(torch.cuda.is_available())"
```

If this prints `True`, the container has access to your GPU
and training + inference will use it automatically (Phase 3
adapters auto-detect CUDA).

---

## GHCR images (once the workflow ships)

CI builds both images on every push to `main` and tags them
`ghcr.io/atultiwari/openpathai:{cpu,gpu}-$SHORT_SHA` +
`:{cpu,gpu}-latest`. When a `GHCR_TOKEN` secret is configured
on the repo, the workflow pushes them automatically:

```bash
docker pull ghcr.io/atultiwari/openpathai:cpu-latest
docker pull ghcr.io/atultiwari/openpathai:gpu-latest
```

Forks / PRs without the secret build the images but skip the
push step — no configuration noise for casual contributors.

---

## Size-cutting knobs

The GPU image is intentionally full-featured. If you only need
the training path and not the GUI / audit / MLflow surfaces,
edit the last `pipx install` line in `Dockerfile.gpu` to drop
the extras you don't need. Dropping `[gui]` saves ~ 200 MB;
dropping `[explain]` saves ~ 100 MB. `[train]` is the only
non-negotiable extra on that image.
