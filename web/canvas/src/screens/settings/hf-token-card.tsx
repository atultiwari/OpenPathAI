// Phase 21.5 chunk C — Hugging Face token card on the Settings tab.
//
// Lets the user paste an HF token, persist it to the server's
// ~/.openpathai/secrets.json (mode 0600), test it via whoami, and
// clear it again. The card surfaces the *active* source so the user
// can tell whether settings / env / nothing is winning today.

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type { HFTokenSource, HFTokenStatus } from "../../api/types";
import { safeMessage } from "../../lib/safe-string";

const HF_TOKENS_URL = "https://huggingface.co/settings/tokens";

const SOURCE_LABEL: Record<HFTokenSource, string> = {
  settings: "Settings file (~/.openpathai/secrets.json)",
  env_hf_token: "HF_TOKEN env var",
  env_hub_token: "HUGGING_FACE_HUB_TOKEN env var",
  none: "Not configured — gated models will fall back to DINOv2",
};

type Banner = { kind: "info" | "ok" | "err"; message: string } | null;

export function HFTokenCard() {
  const { client } = useAuth();
  const [status, setStatus] = useState<HFTokenStatus | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState<Banner>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await client.getHfTokenStatus();
      setStatus(next);
    } catch (err) {
      setBanner({ kind: "err", message: safeMessage(err) });
    }
  }, [client]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onSave = useCallback(async () => {
    if (!draft.trim()) return;
    setBusy(true);
    setBanner({ kind: "info", message: "Saving token…" });
    try {
      const result = await client.setHfToken(draft.trim());
      setStatus(result.status);
      setDraft("");
      setBanner({
        kind: "ok",
        message: `Token saved to ${result.secrets_path} (mode 0600).`,
      });
    } catch (err) {
      setBanner({ kind: "err", message: safeMessage(err) });
    } finally {
      setBusy(false);
    }
  }, [client, draft]);

  const onTest = useCallback(async () => {
    setBusy(true);
    setBanner({ kind: "info", message: "Calling huggingface_hub.whoami…" });
    try {
      const result = await client.testHfToken();
      setStatus(result.status);
      if (result.ok) {
        setBanner({
          kind: "ok",
          message: result.user
            ? `Token works — authenticated as ${result.user}.`
            : "Token works.",
        });
      } else {
        setBanner({
          kind: "err",
          message: `Test failed: ${result.reason ?? "unknown reason"}.`,
        });
      }
    } catch (err) {
      setBanner({ kind: "err", message: safeMessage(err) });
    } finally {
      setBusy(false);
    }
  }, [client]);

  const onClear = useCallback(async () => {
    if (
      !window.confirm(
        "Clear the saved Hugging Face token from ~/.openpathai/secrets.json?"
      )
    ) {
      return;
    }
    setBusy(true);
    setBanner({ kind: "info", message: "Clearing token…" });
    try {
      const result = await client.clearHfToken();
      setStatus(result.status);
      setBanner({
        kind: "ok",
        message: result.cleared
          ? "Token cleared from settings file."
          : "No token was stored.",
      });
    } catch (err) {
      setBanner({ kind: "err", message: safeMessage(err) });
    } finally {
      setBusy(false);
    }
  }, [client]);

  return (
    <div className="card">
      <h3>Hugging Face</h3>
      <p className="help" style={{ marginBottom: 12 }}>
        Required for gated models (UNI, CONCH, Virchow, Prov-GigaPath …).
        Get a <strong>read</strong> token at{" "}
        <a href={HF_TOKENS_URL} target="_blank" rel="noreferrer">
          huggingface.co/settings/tokens
        </a>{" "}
        and paste it below. Saved tokens land in
        <code> ~/.openpathai/secrets.json</code> with mode 0600 — they
        never travel back to the canvas in plaintext.
      </p>

      {banner ? (
        <div
          className={
            banner.kind === "ok"
              ? "banner-ok"
              : banner.kind === "err"
              ? "banner-err"
              : "banner-warn"
          }
        >
          {banner.message}
        </div>
      ) : null}

      <div className="form-grid">
        <div className="field">
          <label htmlFor="s_hf_token">Token</label>
          <input
            id="s_hf_token"
            type="password"
            placeholder="hf_…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <div className="field">
          <label>Active source</label>
          <code>{status ? SOURCE_LABEL[status.source] : "Loading…"}</code>
        </div>
        <div className="field">
          <label>Stored token</label>
          <code>{status?.token_preview ?? "—"}</code>
        </div>
      </div>

      <div className="toolbar" style={{ marginTop: 12 }}>
        <button onClick={onSave} disabled={busy || !draft.trim()}>
          Save token
        </button>
        <button onClick={onTest} disabled={busy || !status?.present}>
          Test token
        </button>
        <button onClick={onClear} disabled={busy || status?.source !== "settings"}>
          Clear settings token
        </button>
      </div>
    </div>
  );
}
