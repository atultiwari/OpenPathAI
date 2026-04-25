// Phase 21.6 chunk C — Settings card listing every OpenPathAI path.

import { useEffect, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type { StoragePaths } from "../../api/types";
import { safeMessage } from "../../lib/safe-string";

const ROW_LABELS: Record<keyof StoragePaths, string> = {
  openpathai_home: "OpenPathAI home root",
  datasets: "Datasets",
  models: "Model weights",
  checkpoints: "Training checkpoints",
  dzi: "DZI tile pyramids",
  audit_db: "Audit DB (SQLite)",
  cache: "Pipeline cache",
  secrets: "Secrets file (mode 0600)",
  hf_hub_cache: "Hugging Face hub cache",
  pipelines: "Saved pipelines",
};

const ROW_ENV_HINT: Partial<Record<keyof StoragePaths, string>> = {
  openpathai_home: "Override with $OPENPATHAI_HOME",
  hf_hub_cache: "Override with $HF_HOME",
};

export function StoragePathsCard() {
  const { client } = useAuth();
  const [paths, setPaths] = useState<StoragePaths | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    client
      .getStoragePaths()
      .then((s) => {
        if (!cancelled) setPaths(s);
      })
      .catch((err) => {
        if (!cancelled) setError(safeMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  function copy(value: string) {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      void navigator.clipboard.writeText(value).then(() => {
        setCopied(value);
        setTimeout(() => setCopied(null), 1200);
      });
    }
  }

  return (
    <div className="card">
      <h3>Storage paths</h3>
      <p className="help" style={{ marginBottom: 12 }}>
        Where every OpenPathAI artifact lives on disk. Override
        <code> $OPENPATHAI_HOME </code> in
        <code> .env </code> to relocate everything except the Hugging
        Face hub cache (<code>$HF_HOME</code>). Click any path to copy.
      </p>
      {error ? <div className="banner-err">{error}</div> : null}
      {paths ? (
        <table className="panel-table">
          <tbody>
            {(Object.keys(ROW_LABELS) as Array<keyof StoragePaths>).map((key) => {
              const value = paths[key];
              const hint = ROW_ENV_HINT[key];
              return (
                <tr key={key}>
                  <th style={{ whiteSpace: "nowrap" }}>{ROW_LABELS[key]}</th>
                  <td>
                    <code
                      style={{ cursor: "pointer" }}
                      onClick={() => copy(value)}
                      title="Click to copy"
                    >
                      {value}
                    </code>
                    {copied === value ? (
                      <span style={{ marginLeft: 8, color: "var(--color-accent-2)", fontSize: 11 }}>
                        copied
                      </span>
                    ) : null}
                    {hint ? (
                      <div style={{ fontSize: 10.5, color: "var(--color-text-dim)", marginTop: 2 }}>
                        {hint}
                      </div>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p>Loading…</p>
      )}
    </div>
  );
}
