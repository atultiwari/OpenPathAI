// Phase 21.6 chunk C — small "this screen writes here" banner.
//
// Mounted at the top of screens that materialise files (Datasets,
// Models, Train, Slides, Analyse). Shows just the path that *this*
// screen interacts with so users always know where bytes land.

import { useEffect, useState } from "react";
import { useAuth } from "../api/auth-context";
import type { StoragePaths } from "../api/types";

export type StorageKey = keyof StoragePaths;

const LABELS: Partial<Record<StorageKey, string>> = {
  datasets: "Datasets land at",
  models: "Model weights land at",
  checkpoints: "Training checkpoints land at",
  dzi: "DZI tile pyramids land at",
  audit_db: "Audit log lives at",
  cache: "Pipeline cache lives at",
  hf_hub_cache: "Hugging Face cache lives at",
  pipelines: "Saved pipelines live at",
  secrets: "Secrets file lives at",
};

type Props = {
  /** Which path to surface. Use the matching artifact category. */
  paths: readonly StorageKey[];
};

export function StorageBanner({ paths }: Props) {
  const { client } = useAuth();
  const [resolved, setResolved] = useState<StoragePaths | null>(null);

  useEffect(() => {
    let cancelled = false;
    client
      .getStoragePaths()
      .then((s) => {
        if (!cancelled) setResolved(s);
      })
      .catch(() => {
        // Banner is informational; failure is silent.
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  if (!resolved) return null;

  return (
    <aside className="storage-banner" aria-label="Storage paths">
      {paths.map((key) => {
        const label = LABELS[key] ?? key;
        const value = resolved[key];
        return (
          <div key={key} className="storage-banner-row">
            <span className="storage-banner-label">{label}</span>
            <code
              className="storage-banner-path"
              title="Click to copy"
              onClick={() => {
                if (typeof navigator !== "undefined" && navigator.clipboard) {
                  void navigator.clipboard.writeText(value);
                }
              }}
            >
              {value}
            </code>
          </div>
        );
      })}
    </aside>
  );
}
