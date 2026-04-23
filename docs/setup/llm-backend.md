# Local LLM Backend — MedGemma 1.5 via Ollama or LM Studio

OpenPathAI's **Bet 2** (natural-language workflows, zero-shot classification,
auto-generated Methods sections) is orchestrated by a local LLM running
alongside the GUI. By default this is **MedGemma 1.5**, Google's
medical-domain Gemma variant, served via **Ollama** (recommended) or **LM
Studio** (alternative). Both expose an OpenAI-compatible HTTP API that
OpenPathAI talks to over `http://localhost`.

**Privacy property:** no pathology data and no prompts leave the machine in
the default configuration. Any opt-in cloud backend is surfaced in the run
manifest.

This guide is needed before **Phase 15** (around week 14 of the build).
Nothing stops you setting it up on day one.

---

## A. Pick a Backend

| | Ollama | LM Studio |
|---|---|---|
| Interface | CLI + REST API | GUI + REST API |
| Installation | `brew install ollama` / `.exe` / `.deb` | Download `.dmg` / `.exe` |
| Model management | `ollama pull <model>` | Search + click Download |
| Default port | `11434` | `1234` |
| Cross-platform | macOS / Windows / Linux | macOS / Windows / Linux |
| OpenAI-compat API | Yes (`/v1/chat/completions`) | Yes (`/v1/chat/completions`) |
| OpenPathAI preset name | `ollama` | `lmstudio` |

**Recommendation:** start with **Ollama**. It's fewer moving pieces and the
model IDs are simpler to reference in config. LM Studio is a comfortable
second option if you prefer a GUI for model management.

You can have **both** installed; OpenPathAI Settings lets you switch
backends per-run.

---

## B. Ollama — Primary Path

### B.1 Install

**macOS**
```bash
brew install ollama
# or download the .dmg from https://ollama.com/download
```

**Windows**
Download the `.exe` installer from https://ollama.com/download and run it.

**Linux**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### B.2 Start the server

**macOS / Linux**
```bash
ollama serve &        # runs in background; logs at ~/.ollama/logs/
```

**Windows**
Ollama auto-registers as a background service and starts on boot. Check
from PowerShell:
```powershell
Get-Service Ollama
```

### B.3 Pull MedGemma 1.5

```bash
ollama pull medgemma1.5:4b
```

Confirmed working on macOS Apple Silicon (M4) — model tag
``medgemma1.5:4b``, ~3.3 GB.

If that slug is not yet in the Ollama model library on your machine, two
fallbacks:

1. **Pull the HF variant through Ollama's GGUF import**:
   ```bash
   # Download the GGUF file once from Hugging Face:
   #   https://huggingface.co/google/medgemma-1.5-gguf  (or similar slug)
   # Then create an Ollama modelfile:
   cat > Modelfile <<'EOF'
   FROM ./medgemma-1.5-Q4_K_M.gguf
   TEMPLATE """{{ .Prompt }}"""
   EOF
   ollama create medgemma1.5:4b -f Modelfile
   ```
2. **Use a closely-compatible model** while waiting: `ollama pull gemma2:9b-instruct`
   works as a temporary stand-in. Update the config when MedGemma 1.5 lands.

Verify:
```bash
ollama list              # MedGemma should appear
ollama run medgemma1.5:4b "Summarise H&E staining in one sentence."
```

### B.4 Configure OpenPathAI (Phase 15+)

```bash
openpathai settings set llm.backend   ollama
openpathai settings set llm.model     medgemma1.5:4b
openpathai settings set llm.endpoint  http://localhost:11434
```

Until Phase 15 ships, the same values live in
`~/.openpathai/settings.yaml`:

```yaml
llm:
  backend: ollama
  model: medgemma1.5:4b
  endpoint: http://localhost:11434
  request_timeout_s: 120
```

### B.5 Smoke test the integration (from Phase 15 onward)

```bash
openpathai nl echo "Write a Methods paragraph placeholder."
```

Should print a MedGemma response. If you get a connection-refused error,
`ollama serve` isn't running.

---

## C. LM Studio — Alternative Path

### C.1 Install

Download from https://lmstudio.ai/ and run the installer. LM Studio has
**macOS (Apple Silicon & Intel)**, **Windows**, and **Linux** builds.

### C.2 Download MedGemma 1.5

1. Launch LM Studio.
2. Left sidebar → **Search**.
3. Search `MedGemma 1.5`. If that exact release is unavailable, search
   `MedGemma` and pick the most recent instruct-tuned variant.
4. Choose a quant (`Q4_K_M` for speed on CPU / MPS; `Q8` or FP16 if you
   have a GPU with enough VRAM).
5. Click **Download**.

### C.3 Start the local server

1. Left sidebar → **Developer** → **Local Server**.
2. Select the MedGemma model in the dropdown.
3. Click **Start Server**. Default endpoint: `http://localhost:1234/v1`.

### C.4 Configure OpenPathAI

```bash
openpathai settings set llm.backend   lmstudio
openpathai settings set llm.model     medgemma-1.5-instruct      # exact name LM Studio shows
openpathai settings set llm.endpoint  http://localhost:1234/v1
```

Or in `~/.openpathai/settings.yaml`:

```yaml
llm:
  backend: lmstudio
  model: medgemma-1.5-instruct
  endpoint: http://localhost:1234/v1
  request_timeout_s: 120
```

### C.5 Smoke test

Same command:
```bash
openpathai nl echo "Test LM Studio backend."
```

---

## D. Hardware Expectations

MedGemma 1.5 in Q4_K_M (typical default) needs roughly:

| Machine | Expected speed | Notes |
|---|---|---|
| MacBook Air M2 / M3 (16 GB RAM) | ~15–25 tok/s | Metal acceleration via Ollama/LM Studio automatic. |
| MacBook Pro M-series (32 GB+) | ~30–60 tok/s | Comfortable for interactive use. |
| Windows / Linux laptop **without GPU** | ~3–8 tok/s | Usable for auto-Methods, slow for interactive chat. |
| Windows / Linux with NVIDIA 8 GB+ | ~40–80 tok/s | Fastest local option. |
| Colab T4 (15 GB VRAM) | ~60–100 tok/s | Used only when the exported notebook needs NL features. |

A heavier quant (Q8 / FP16) roughly halves speed and doubles quality — most
users should stay on Q4_K_M.

---

## E. Opt-in Cloud Backends (future)

OpenPathAI's LLM layer speaks the OpenAI chat-completions spec, so **any**
OpenAI-compatible endpoint slots in with a config change:

```yaml
llm:
  backend: openai_compatible
  endpoint: https://<provider>/v1
  model: <provider-model-id>
  api_key_env: MY_PROVIDER_API_KEY
  cloud: true                    # << triggers the manifest flag
  opt_in_confirmed_by: "user@example.com"
```

When `cloud: true`, the run manifest's `environment.llm.backend` records the
provider, and the GUI shows a yellow banner on every analysis. This is
deliberately friction-laden — if your data is sensitive, keep the default
local-only setup.

---

## F. What You Need to Give Claude

Concrete short list of what to do before Phase 15:

1. Install **Ollama** (or LM Studio).
2. Pull (or import via GGUF) **MedGemma 1.5**.
3. Note the endpoint (`http://localhost:11434` for Ollama, `http://localhost:1234/v1` for LM Studio).
4. **You do not share any API key with Claude or paste one in code.** The
   backend is local; there is nothing secret to share.

If you later opt into a cloud backend, put its API key in a `.env` file
(already in `.gitignore`) and reference it via `api_key_env` in the settings.

---

## G. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Connection refused` on port 11434 | `ollama serve` not running | Start it: `ollama serve &` (macOS/Linux) or start the Ollama app (Windows). |
| Model `medgemma1.5:4b` not found | Slug not in Ollama library yet | Use the GGUF import path (§B.3) or fall back to `gemma2:9b-instruct` temporarily. |
| Extremely slow generation on Mac | Quant too large | Pull a smaller quant: `ollama pull medgemma1.5:4b-q4_K_M`. |
| "CUDA out of memory" on Windows GPU | Quant too large or context too long | Pull `q4_K_M`; lower context via settings (`llm.max_context_tokens: 4096`). |
| LM Studio server refuses requests | Forgot to click **Start Server** | Developer tab → Local Server → **Start**. |
| Responses contain refusal language ("I cannot help…") | Wrong base model (e.g., Gemma-base instead of instruct) | Ensure you pulled the *instruct* variant. |

---

## H. Summary for the impatient

1. `brew install ollama && ollama serve &`
2. `ollama pull medgemma1.5:4b`
3. Once Phase 15 lands:
   `openpathai settings set llm.backend ollama && openpathai settings set llm.model medgemma1.5:4b`
4. Done. No secret to share with Claude — the backend is local.
