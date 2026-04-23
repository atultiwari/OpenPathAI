# Hugging Face Setup — Gated Models & Access Tokens

OpenPathAI pulls several pathology foundation models from Hugging Face. Some
are **open** (download without approval); some are **gated** (you click
"Request access", wait hours to weeks for a human to approve). This guide
gets you through both paths.

Do **both** halves of this guide:

- **Part A** — create an account, generate an access token, tell OpenPathAI
  where to find it.
- **Part B** — request access to the gated models.

Part B's approvals take time, so start them **now**, in parallel with
OpenPathAI development. Most early phases don't need the gated models; they
first become critical in Phase 13.

---

## Part A — Account & Access Token

### A.1 Create / confirm a Hugging Face account

1. Go to https://huggingface.co and sign up (or sign in).
2. **Complete your profile** — fill the "Bio" and "Affiliation" fields. Most
   gated-model reviewers check these before approving. An institutional
   email (`@vedantresearchlabs.com`, `@someuniversity.edu`, hospital domain,
   etc.) dramatically shortens review time. Personal Gmail / Outlook work
   too but approval can be slower.

### A.2 Create an access token

1. Top-right avatar → **Settings** → **Access Tokens**.
2. Click **New token**.
   - **Name:** `openpathai-local`
   - **Type:** `Read` (do not create Write tokens unless you plan to upload
     models — Read is enough for download).
   - Click **Generate token** and copy the `hf_***` string.

### A.3 Tell OpenPathAI where to find it

Three options, ordered by preference:

#### Option 1 — Hugging Face CLI login (recommended, cross-platform)

```bash
pip install --upgrade "huggingface_hub[cli]"    # or: uv tool install huggingface_hub
huggingface-cli login
# paste the hf_*** token when prompted; answer "n" to git credential helper
```

This writes the token to `~/.cache/huggingface/token`. Every HF library on
the machine will pick it up automatically.

#### Option 2 — Environment variable (for CI, servers, Colab)

```bash
export HF_TOKEN="hf_***"
# on Windows:
setx HF_TOKEN "hf_***"
```

OpenPathAI reads `HF_TOKEN` if present.

#### Option 3 — OpenPathAI GUI Settings tab (from Phase 6 onward)

Once the GUI ships, the Settings tab accepts the token and stores it in the
OS keyring (macOS Keychain / Windows Credential Manager / libsecret on
Linux) — never in plaintext.

### A.4 Verify

```bash
huggingface-cli whoami
```

Should print your username. Done.

---

## Part B — Request Access to Gated Models

**Do this step-by-step for every model you want to use.** Each needs its own
click-through. Approvals range from *immediate* to *several weeks*.

Plan for this: Phase 13 (Foundation Models) is roughly 12 weeks into the
OpenPathAI build. If you request access today, most approvals will land
before you need them.

### B.1 The gated models OpenPathAI uses

| # | Model | Purpose | HF URL | Typical wait |
|---|---|---|---|---|
| 1 | **UNI** | ViT-L feature extractor (linear probe / fine-tune) | https://huggingface.co/MahmoodLab/UNI | 1–3 days with institutional email |
| 2 | **UNI2-h** | Next-generation UNI (ViT-H) | https://huggingface.co/MahmoodLab/UNI2-h | 1–3 days |
| 3 | **CONCH** | Vision-language, zero-shot classification (**Bet 2** backbone) | https://huggingface.co/MahmoodLab/CONCH | 1–3 days |
| 4 | **Virchow2** | Paige foundation model | https://huggingface.co/paige-ai/Virchow2 | 1–2 weeks (institutional confirmation) |
| 5 | **Prov-GigaPath** | Microsoft/Providence slide-level encoder | https://huggingface.co/prov-gigapath/prov-gigapath | 1–2 weeks |
| 6 | **MedSAM2** | Medical SAM2 (**Bet 2** segmentation backbone) | https://huggingface.co/wanglab/MedSAM2 | often immediate; may be ungated |
| 7 | **MedGemma 1.5** | Google medical Gemma (local LLM for Bet 2) | https://huggingface.co/google/medgemma-1.5 *(if this slug changes upstream, search "MedGemma")* | 1–3 days |

> **Heads-up:** HF slugs occasionally move between org names. If any link
> 404s, search `https://huggingface.co/models?search=<model name>`; the
> author org is usually `MahmoodLab`, `paige-ai`, `prov-gigapath`, `wanglab`,
> or `google`.

### B.2 What the request form asks (typical)

Most forms ask:
- **Your name + affiliation** — answer truthfully with your institution /
  company. This is what reviewers check.
- **Intended use** — be specific. Template you can adapt:
  > *"Research use in computational pathology for tile-level classification,
  > zero-shot annotation, and promptable segmentation. Integrated into
  > OpenPathAI (https://github.com/atultiwari/OpenPathAI), an open-source
  > MIT-licensed research workflow environment. No diagnostic / clinical
  > use."*
- **Licence agreement** — tick the boxes; each model has its own research
  licence you agree to.

### B.3 After you request

- Hugging Face emails you when a request is approved or rejected.
- Approved requests show a green **"Access granted"** banner on the model
  page when you're logged in.
- Rejected requests usually tell you why (missing affiliation, etc.) — fix
  and resubmit.

### B.4 Open (no-approval) models we also use

These download with the same token, no approval step:

| Model | Purpose | HF URL |
|---|---|---|
| **DINOv2** | Open baseline feature extractor | https://huggingface.co/facebook/dinov2-base |
| **CTransPath** | Swin-based pathology baseline | https://huggingface.co/hrlblab/CTransPath |
| **Hibou** | Open pathology foundation model | https://huggingface.co/histai/hibou-b |
| **SAM2** | Meta SAM2 (general promptable segmentation) | https://huggingface.co/facebook/sam2-hiera-large |
| **RT-DETRv2** | Real-time detection transformer | https://huggingface.co/PekingU/rtdetr_v2_r50vd |

OpenPathAI falls back to these automatically when a gated counterpart is
unavailable, and the run manifest logs which model was actually used.

---

## C. Quick-answers the tooling needs

Once you've done the above, OpenPathAI needs **nothing else** from you
concerning Hugging Face for local development. Specifically:

- **You do not share the token with me (Claude).** The token stays on your
  machine. OpenPathAI reads it from `HF_TOKEN` / `~/.cache/huggingface/token`
  at run-time.
- **You do not paste the token into the repo.** `.gitignore` excludes
  `.env` files and the HF cache directory by default.
- **For Colab**, paste the token once into Colab's **Secrets** panel
  (🔑 icon on the left), name it `HF_TOKEN`. OpenPathAI's exported Colab
  notebook reads it via `google.colab.userdata.get("HF_TOKEN")`.
- **For GitHub Actions**, if/when CI needs to download a gated model,
  add `HF_TOKEN` as a **repository secret** (Settings → Secrets and
  variables → Actions). OpenPathAI's CI reads `secrets.HF_TOKEN`. For
  Phases 0–12 this isn't needed.

---

## D. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `huggingface-cli login` prints `403 Forbidden` | Network / proxy | Check your corporate proxy; try from home network. |
| `401 Unauthorized` when downloading a gated model | Token is Read-only but not yet approved for this specific model | Check the model's page — look for "Access granted". |
| `Cannot access gated repo` even after approval | Token cached before approval | Log out + back in: `huggingface-cli logout && huggingface-cli login`. |
| `HF_TOKEN` set but not picked up | Terminal hasn't reloaded env vars | Restart the terminal / IDE. |
| Approval request pending for > 2 weeks | Affiliation field missing or unclear | Edit your HF profile, add a clear institutional affiliation, email the author org if still stuck. |

---

## E. Summary for the impatient

1. Make a Hugging Face account with your institutional affiliation filled in.
2. Generate a Read access token.
3. `huggingface-cli login` → paste token.
4. Open each gated-model page in §B.1 and click "Request access"; use the
   template in §B.2 for the "Intended use" field.
5. Forget about it for a week. Most approvals arrive before you need them.

That's the whole job on the user side. OpenPathAI takes over from there.
