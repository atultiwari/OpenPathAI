// Phase 21.5 chunk D — "Quick start" card.
//
// Visible on the Analyse tab the first time a user opens the canvas
// (or until they dismiss it). Walks through the four steps documented
// in docs/quickstart.md, with concrete buttons that jump to the
// relevant tab via a custom DOM event the CanvasShell listens for.
//
// Each step also probes the live state where it can — e.g. the HF
// token row turns green when the resolver reports a token, so the
// user sees their progress without having to bounce between tabs.

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../api/auth-context";
import type { HFTokenStatus } from "../api/types";
import { safeMessage } from "../lib/safe-string";

const STORAGE_KEY = "openpathai.quickstart.dismissed";
const DOCS_URL =
  "https://github.com/atultiwari/OpenPathAI/blob/main/docs/quickstart.md";

/**
 * Custom DOM event the CanvasShell listens for. Decouples cross-tab
 * navigation from the React tree without dragging in a router.
 */
export const NAV_TAB_EVENT = "openpathai:nav-tab";

export function navigateToTab(tab: string): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(NAV_TAB_EVENT, { detail: tab }));
}

function readDismissed(): boolean {
  if (typeof window === "undefined" || !window.localStorage) return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeDismissed(value: boolean): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    if (value) {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // best-effort
  }
}

type Step = {
  index: number;
  title: string;
  body: string;
  done: boolean;
  cta?: { label: string; onClick: () => void };
};

export function QuickStartCard() {
  const { client } = useAuth();
  const [dismissed, setDismissed] = useState<boolean>(() => readDismissed());
  const [hfStatus, setHfStatus] = useState<HFTokenStatus | null>(null);
  const [hfError, setHfError] = useState<string | null>(null);

  useEffect(() => {
    if (dismissed) return;
    let cancelled = false;
    client
      .getHfTokenStatus()
      .then((s) => {
        if (!cancelled) setHfStatus(s);
      })
      .catch((err) => {
        if (!cancelled) setHfError(safeMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [client, dismissed]);

  const dismiss = useCallback(() => {
    writeDismissed(true);
    setDismissed(true);
  }, []);

  if (dismissed) {
    return (
      <button
        type="button"
        className="tab-guide-pill"
        onClick={() => {
          writeDismissed(false);
          setDismissed(false);
        }}
        aria-label="Show the Quick start card"
      >
        <span aria-hidden>🚀</span>
        <span>Show Quick start</span>
      </button>
    );
  }

  const steps: Step[] = [
    {
      index: 1,
      title: "Plumb your Hugging Face token (optional)",
      body:
        hfStatus?.present
          ? `Active source: ${hfStatus.source} (${hfStatus.token_preview ?? "—"}).`
          : "Required only for gated foundation models. DINOv2 works without a token.",
      done: Boolean(hfStatus?.present),
      cta: {
        label: "Open Settings",
        onClick: () => navigateToTab("settings"),
      },
    },
    {
      index: 2,
      title: "Pick a dataset",
      body:
        "Kather-CRC-5K is the smallest open-access card and the recommended first run.",
      done: false,
      cta: {
        label: "Open Datasets",
        onClick: () => navigateToTab("datasets"),
      },
    },
    {
      index: 3,
      title: "Train a classifier (synthetic or real)",
      body:
        "Toggle the synthetic flag on for a no-download green run, off to actually fit the linear head.",
      done: false,
      cta: {
        label: "Open Train",
        onClick: () => navigateToTab("train"),
      },
    },
    {
      index: 4,
      title: "Drop a tile here and read the explanation",
      body:
        "Grad-CAM / IG / attention overlay on a single tile. Result lands in the audit DB automatically.",
      done: false,
    },
  ];

  return (
    <aside className="quick-start-card" aria-labelledby="quickstart-title">
      <header className="quick-start-header">
        <h3 id="quickstart-title">
          <span aria-hidden>🚀</span> Quick start — first end-to-end run
        </h3>
        <button
          type="button"
          className="tab-guide-dismiss"
          onClick={dismiss}
          aria-label="Dismiss Quick start card"
          title="Dismiss (you can re-open from the pill)"
        >
          ×
        </button>
      </header>

      {hfError ? <div className="banner-warn">HF status unavailable: {hfError}</div> : null}

      <ol className="quick-start-steps">
        {steps.map((step) => (
          <li key={step.index} className={step.done ? "is-done" : undefined}>
            <div className="quick-start-step-row">
              <span className="quick-start-num" aria-hidden>
                {step.done ? "✓" : step.index}
              </span>
              <div className="quick-start-step-text">
                <strong>{step.title}</strong>
                <span>{step.body}</span>
              </div>
              {step.cta ? (
                <button
                  type="button"
                  className="quick-start-cta"
                  onClick={step.cta.onClick}
                >
                  {step.cta.label}
                </button>
              ) : null}
            </div>
          </li>
        ))}
      </ol>

      <footer className="quick-start-footer">
        <a href={DOCS_URL} target="_blank" rel="noreferrer">
          Read the full quickstart →
        </a>
      </footer>
    </aside>
  );
}
