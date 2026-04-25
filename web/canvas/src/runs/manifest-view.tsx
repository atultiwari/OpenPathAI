import { useEffect, useState } from "react";
import { useAuth } from "../api/auth-context";
import { redactPayload } from "../lib/redact";
import { safeMessage } from "../lib/safe-string";

type Props = {
  runId: string;
  onClose: () => void;
};

export function ManifestView({ runId, onClose }: Props) {
  const { client } = useAuth();
  const [payload, setPayload] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    client
      .getRunManifest(runId)
      .then((m) => {
        if (!cancelled) setPayload(redactPayload(m));
      })
      .catch((err) => {
        if (!cancelled) setError(safeMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [client, runId]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-card"
        style={{ width: "min(720px, 92vw)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2>Manifest — {runId.slice(0, 12)}</h2>
        {error ? (
          <p style={{ color: "var(--color-error)" }}>{error}</p>
        ) : payload ? (
          <pre className="json-pre">{JSON.stringify(payload, null, 2)}</pre>
        ) : (
          <p>Loading…</p>
        )}
        <div className="token-form actions">
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
