// Phase 21.5 — per-tab "About this screen" guide.
//
// Each screen mounts <TabGuide tab="…"/> at the top. The component
// renders an opinionated info card the first time the user lands on
// the tab. Once dismissed, it collapses to a small pill button that
// re-opens the card. State persists in localStorage per-tab so the
// dismiss sticks across reloads.

import { useCallback, useEffect, useState } from "react";
import { TAB_GUIDES, type TabGuideId } from "./tab-guide-content";

const STORAGE_PREFIX = "openpathai.tabguide.";

function storageKey(tab: TabGuideId): string {
  return `${STORAGE_PREFIX}${tab}.dismissed`;
}

function readDismissed(tab: TabGuideId): boolean {
  if (typeof window === "undefined" || !window.localStorage) return false;
  try {
    return window.localStorage.getItem(storageKey(tab)) === "1";
  } catch {
    return false;
  }
}

function writeDismissed(tab: TabGuideId, value: boolean): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    if (value) {
      window.localStorage.setItem(storageKey(tab), "1");
    } else {
      window.localStorage.removeItem(storageKey(tab));
    }
  } catch {
    // Persisting the dismiss state is a nice-to-have; failing to write
    // it (e.g. private mode) must not crash the screen.
  }
}

type Props = {
  tab: TabGuideId;
  /** Render compact inline pill only — no expanded card by default. */
  startCollapsed?: boolean;
};

export function TabGuide({ tab, startCollapsed = false }: Props) {
  const guide = TAB_GUIDES[tab];
  const [collapsed, setCollapsed] = useState<boolean>(() =>
    startCollapsed ? true : readDismissed(tab)
  );

  // Re-sync if the tab prop changes (the canvas swaps screens in place,
  // but the TabGuide is mounted per-screen so this mostly catches HMR).
  useEffect(() => {
    setCollapsed(startCollapsed ? true : readDismissed(tab));
  }, [tab, startCollapsed]);

  const dismiss = useCallback(() => {
    writeDismissed(tab, true);
    setCollapsed(true);
  }, [tab]);

  const expand = useCallback(() => {
    writeDismissed(tab, false);
    setCollapsed(false);
  }, [tab]);

  if (!guide) return null;

  if (collapsed) {
    return (
      <button
        type="button"
        className="tab-guide-pill"
        onClick={expand}
        aria-label={`Show "About ${guide.title}" guide`}
      >
        <span aria-hidden>ⓘ</span>
        <span>About {guide.title}</span>
      </button>
    );
  }

  return (
    <aside
      className="tab-guide"
      aria-labelledby={`tab-guide-title-${tab}`}
    >
      <header className="tab-guide-header">
        <h3 id={`tab-guide-title-${tab}`}>
          <span aria-hidden>ⓘ</span> About {guide.title}
        </h3>
        <button
          type="button"
          className="tab-guide-dismiss"
          onClick={dismiss}
          aria-label="Dismiss guide"
          title="Dismiss (you can re-open from the ⓘ pill)"
        >
          ×
        </button>
      </header>
      <p className="tab-guide-purpose">{guide.purpose}</p>

      {guide.steps.length ? (
        <ol className="tab-guide-steps">
          {guide.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      ) : null}

      <dl className="tab-guide-meta">
        {guide.pythonNode ? (
          <>
            <dt>Python node</dt>
            <dd>
              <code>{guide.pythonNode}</code>
            </dd>
          </>
        ) : null}
        {guide.cachedAndAudited ? (
          <>
            <dt>Cached / audited</dt>
            <dd>{guide.cachedAndAudited}</dd>
          </>
        ) : null}
        {guide.docsHref ? (
          <>
            <dt>Docs</dt>
            <dd>
              <a href={guide.docsHref} target="_blank" rel="noreferrer">
                {guide.docsLabel ?? guide.docsHref}
              </a>
            </dd>
          </>
        ) : null}
      </dl>
    </aside>
  );
}
