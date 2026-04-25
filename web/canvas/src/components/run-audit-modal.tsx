// Phase 21 — modal that resolves a `run_id` to its full audit envelope:
// audit-DB row, runtime job record, Phase-17 manifest, signature info.

import { useEffect, useState } from "react";
import type { ApiClient } from "../api/client";
import { redactPayload } from "../lib/redact";
import type { RunAuditDetail } from "../api/types";

interface RunAuditModalProps {
  api: ApiClient;
  runId: string;
  onClose: () => void;
}

export function RunAuditModal({ api, runId, onClose }: RunAuditModalProps) {
  const [detail, setDetail] = useState<RunAuditDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getFullAudit(runId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : "failed to load audit";
        setError(message);
      });
    return () => {
      cancelled = true;
    };
  }, [api, runId]);

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-card" style={{ maxWidth: "min(90vw, 900px)" }}>
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "1rem",
          }}
        >
          <h2 style={{ margin: 0 }}>
            Run audit · <code>{runId}</code>
          </h2>
          <button type="button" onClick={onClose} aria-label="close">
            ✕
          </button>
        </header>
        {error ? (
          <p className="banner-err">Failed: {error}</p>
        ) : detail === null ? (
          <p className="inspector-empty">Loading audit envelope…</p>
        ) : (
          <Sections detail={detail} />
        )}
      </div>
    </div>
  );
}

interface SectionsProps {
  detail: RunAuditDetail;
}

function Sections({ detail }: SectionsProps) {
  const safe = redactPayload(detail) as RunAuditDetail;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <Section title="Audit DB row" payload={safe.audit} />
      <Section title="Runtime record" payload={safe.runtime} />
      <Section title="Phase-17 manifest" payload={safe.manifest} />
      <Section title="Cache stats" payload={safe.cache_stats} />
      <Section
        title="Signature"
        payload={safe.signature}
        emptyHint="No sigstore signature on this run (Exploratory mode)."
      />
      <Section
        title={`Analyses (${safe.analyses.length})`}
        payload={safe.analyses}
        emptyHint="No analyses recorded against this run."
      />
    </div>
  );
}

interface SectionProps {
  title: string;
  payload: unknown;
  emptyHint?: string;
}

function Section({ title, payload, emptyHint }: SectionProps) {
  const isEmpty =
    payload == null ||
    (Array.isArray(payload) && payload.length === 0) ||
    (typeof payload === "object" && Object.keys(payload as object).length === 0);
  return (
    <details open={!isEmpty} className="audit-section card">
      <summary style={{ fontWeight: 600 }}>{title}</summary>
      {isEmpty ? (
        <p className="inspector-empty" style={{ marginTop: ".5rem" }}>
          {emptyHint ?? "Not present."}
        </p>
      ) : (
        <pre
          style={{
            background: "var(--surface-muted, #f4f4f4)",
            padding: ".75rem",
            borderRadius: ".4rem",
            fontSize: ".75rem",
            maxHeight: "20rem",
            overflow: "auto",
          }}
        >
          {JSON.stringify(payload, null, 2)}
        </pre>
      )}
    </details>
  );
}
