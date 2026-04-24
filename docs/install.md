# Install

Three install paths, three hardware tiers. Pick the row that
matches yours.

| Tier | Hardware | Recommended path | Extras |
| --- | --- | --- | --- |
| **T1** | Laptop, CPU only | `pipx install "openpathai[gui,safety,audit]"` | no torch |
| **T2** | Workstation with a recent discrete GPU | `pipx install "openpathai[gui,train,explain,safety,audit,mlflow]"` | torch (CUDA or MPS) |
| **T3** | CUDA-capable server | Docker: `docker run --gpus all ghcr.io/atultiwari/openpathai:gpu-latest` | torch + foundation + NL |

---

## From source (what you have now)

Clone + sync with the extras you want:

```bash
git clone https://github.com/atultiwari/OpenPathAI.git
cd OpenPathAI

# Light install — CLI + GUI + safety, no torch:
uv sync --extra dev --extra gui --extra safety --extra audit

# Heavy install — add torch + explain + MLflow + notebook:
uv sync --extra dev --extra train --extra gui --extra safety --extra audit \
         --extra explain --extra mlflow --extra notebook

# Run from source:
uv run openpathai --version
uv run openpathai gui
```

`uv` handles the Python-version + wheel-resolver details
automatically (including the macOS-ARM / Windows / Linux
matrix).

---

## `pipx install`

Once the wheel is published (Phase 18 ships the
`pipx install` path end-to-end; the PyPI release is a
follow-up):

```bash
# Minimal GUI install:
pipx install "openpathai[gui]"

# Full feature set:
pipx install "openpathai[gui,train,explain,safety,audit,mlflow]"

# Verify:
openpathai --version
openpathai llm status
openpathai foundation resolve dinov2_vits14
openpathai gui    # http://127.0.0.1:7860
```

`pipx` installs OpenPathAI into an isolated virtualenv + puts
the `openpathai` binary on your `$PATH` — no conflicts with
your system Python.

**Windows note:** Python 3.12 from the Microsoft Store and
Python 3.12 from python.org behave slightly differently under
`pipx`. If `openpathai --version` isn't found after install,
run `pipx ensurepath` + restart your terminal.

---

## Docker

See [`docker/README.md`](https://github.com/atultiwari/OpenPathAI/blob/main/docker/README.md)
for the full story. Short form:

```bash
# CPU, ~350 MB:
docker pull ghcr.io/atultiwari/openpathai:cpu-latest
docker run --rm -p 7860:7860 \
    -v "$HOME/.openpathai:/home/openpathai/.openpathai" \
    ghcr.io/atultiwari/openpathai:cpu-latest gui --host 0.0.0.0

# GPU, ~6-8 GB, needs nvidia-container-toolkit:
docker pull ghcr.io/atultiwari/openpathai:gpu-latest
docker run --rm --gpus all -p 7860:7860 \
    -v "$HOME/.openpathai:/home/openpathai/.openpathai" \
    ghcr.io/atultiwari/openpathai:gpu-latest gui --host 0.0.0.0
```

---

## Optional user-side setup

### Hugging Face gated access

Foundation backbones (UNI, CONCH, Virchow2, MedSAM2, …) and
some datasets are gated behind HF access requests. Without it
the fallback resolvers substitute open alternatives (DINOv2,
SyntheticClickSegmenter). To turn on the real adapters:

```bash
# Request access at each model's HF page, then:
export HUGGINGFACE_HUB_TOKEN=hf_...
openpathai foundation resolve uni   # reason should become "ok"
```

Full walkthrough: [`setup/huggingface.md`](setup/huggingface.md).

### Local LLM backend

`openpathai nl draft` and `openpathai methods write` call a
local LLM (Ollama or LM Studio). Install + pull once:

```bash
# Ollama (recommended — single binary):
curl -fsSL https://ollama.com/install.sh | sh
ollama pull medgemma:1.5

# Confirm:
openpathai llm status
```

Full walkthrough: [`setup/llm-backend.md`](setup/llm-backend.md).

Both setups take ~an hour of wall-clock including downloads.
Everything else in OpenPathAI works without either.

---

## Verifying an install

```bash
openpathai --version                # prints the package version
openpathai hello                    # smoke greet
openpathai llm status               # local LLM probe
openpathai foundation list          # 8 backbones registered
openpathai detection list           # 5 detectors
openpathai segmentation list        # 11 segmenters
openpathai mil list                 # 5 MIL aggregators
```

If any of those commands fail with an `ImportError`, re-run
`pipx install "openpathai[<extra>]"` with the extra the error
message named.

---

## Uninstall

```bash
pipx uninstall openpathai
# If installed from source:
rm -rf "$HOME/.openpathai"   # caches + audit DB + keys
```

Docker images can be removed with `docker rmi ghcr.io/atultiwari/openpathai:cpu-latest`.
