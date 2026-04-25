// Phase 21.6 chunk A — Quickstart wizard tab.
//
// Replaces the inline QuickStartCard with a dedicated multi-step
// wizard. State persists in localStorage so a refresh resumes mid-
// flow. Each step shows what *you* do, what *we* do, and where the
// resulting artifacts land on disk.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../../api/auth-context";
import { TabGuide } from "../../components/tab-guide";
import { safeMessage } from "../../lib/safe-string";
import {
  WIZARD_TEMPLATES,
  findTemplate,
  type StepResult,
  type StepStatus,
  type WizardContext,
  type WizardStep,
  type WizardTemplate,
} from "./templates";
import "./quickstart-screen.css";

const STORAGE_KEY = "openpathai.quickstart.session";

type StoredSession = {
  templateId: string;
  stepResults: Record<string, StepResult>;
  state: Record<string, unknown>;
};

function loadSession(): StoredSession | null {
  if (typeof window === "undefined" || !window.localStorage) return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      "templateId" in parsed &&
      typeof (parsed as StoredSession).templateId === "string"
    ) {
      return parsed as StoredSession;
    }
  } catch {
    // ignore corrupt storage
  }
  return null;
}

function saveSession(session: StoredSession | null): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    if (session) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // best-effort
  }
}

function statusLabel(status: StepStatus): string {
  switch (status) {
    case "done":
      return "Done";
    case "running":
      return "Running…";
    case "error":
      return "Error";
    case "skipped":
      return "Skipped";
    case "pending":
    default:
      return "Pending";
  }
}

function progress(template: WizardTemplate, results: Record<string, StepResult>): number {
  if (template.steps.length === 0) return 0;
  const done = template.steps.filter(
    (s) => results[s.id]?.status === "done" || results[s.id]?.status === "skipped"
  ).length;
  return Math.round((done / template.steps.length) * 100);
}

export function QuickstartScreen() {
  const { client } = useAuth();
  const [session, setSession] = useState<StoredSession | null>(() => loadSession());
  const [error, setError] = useState<string | null>(null);
  const [busyStep, setBusyStep] = useState<string | null>(null);
  const ctxState = useRef<Record<string, unknown>>(session?.state ?? {});

  const template = useMemo<WizardTemplate | null>(
    () => (session ? findTemplate(session.templateId) ?? null : null),
    [session]
  );

  const updateResults = useCallback(
    (stepId: string, result: StepResult) => {
      setSession((prev) => {
        if (!prev) return prev;
        const next: StoredSession = {
          ...prev,
          stepResults: { ...prev.stepResults, [stepId]: result },
          state: { ...ctxState.current },
        };
        saveSession(next);
        return next;
      });
    },
    []
  );

  // Probe step status when a template is loaded so e.g. the HF-token
  // and dataset-download rows pre-fill if the user already did them
  // through other surfaces.
  useEffect(() => {
    if (!template) return;
    let cancelled = false;
    (async () => {
      const ctx: WizardContext = {
        client,
        template,
        state: ctxState.current,
      };
      for (const step of template.steps) {
        if (cancelled) break;
        if (!step.probe) continue;
        // Don't overwrite a user-completed (done/error/skipped) row.
        const existing = session?.stepResults[step.id];
        if (existing && existing.status !== "pending") continue;
        try {
          const probed = await step.probe(ctx);
          if (probed && !cancelled) {
            updateResults(step.id, probed);
          }
        } catch {
          // probes are best-effort
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template, client, updateResults]);

  function pickTemplate(t: WizardTemplate) {
    const next: StoredSession = {
      templateId: t.id,
      stepResults: {},
      state: {},
    };
    ctxState.current = {};
    saveSession(next);
    setSession(next);
    setError(null);
  }

  function reset() {
    saveSession(null);
    setSession(null);
    ctxState.current = {};
    setError(null);
  }

  async function runStep(step: WizardStep) {
    if (!template || !step.run) return;
    setBusyStep(step.id);
    setError(null);
    updateResults(step.id, { status: "running" });
    try {
      const result = await step.run({
        client,
        template,
        state: ctxState.current,
      });
      updateResults(step.id, result);
      if (result.status === "error" && result.message) {
        setError(result.message);
      }
    } catch (err) {
      const message = safeMessage(err);
      updateResults(step.id, { status: "error", message });
      setError(message);
    } finally {
      setBusyStep(null);
    }
  }

  function skipStep(step: WizardStep) {
    if (!template) return;
    updateResults(step.id, {
      status: "skipped",
      message: "Marked as skipped by the user.",
    });
  }

  // Template picker (no session yet).
  if (!template) {
    return (
      <section className="task-content">
        <TabGuide tab="quickstart" />
        <h2>Quickstart wizard</h2>
        <p className="lede">
          Pick a template to walk through your first end-to-end run. Each
          template downloads the dataset, fits a model, and lands a
          prediction in the audit DB. Storage paths are surfaced at every
          step so you always know where artifacts live.
        </p>

        <div className="qs-template-grid">
          {WIZARD_TEMPLATES.map((t) => (
            <button
              key={t.id}
              type="button"
              className="qs-template-card"
              onClick={() => pickTemplate(t)}
            >
              <div className="qs-template-head">
                <strong>{t.label}</strong>
                <span className={`qs-tier qs-tier-${t.tier}`}>{t.tier}</span>
              </div>
              <p>{t.blurb}</p>
              <dl className="qs-template-meta">
                <div>
                  <dt>Dataset</dt>
                  <dd>
                    <code>{t.datasetCard}</code>
                  </dd>
                </div>
                <div>
                  <dt>Model</dt>
                  <dd>
                    <code>{t.modelCard}</code>
                  </dd>
                </div>
                <div>
                  <dt>Steps</dt>
                  <dd>{t.steps.length}</dd>
                </div>
                <div>
                  <dt>Est.</dt>
                  <dd>~{t.estimatedMinutes} min</dd>
                </div>
              </dl>
              <span className="qs-template-cta">Start →</span>
            </button>
          ))}
        </div>
      </section>
    );
  }

  // Active wizard.
  const pct = progress(template, session?.stepResults ?? {});
  return (
    <section className="task-content">
      <TabGuide tab="quickstart" />
      <header className="qs-header">
        <div>
          <h2>{template.label}</h2>
          <p className="lede">{template.blurb}</p>
        </div>
        <div className="qs-header-actions">
          <button type="button" onClick={reset}>
            Pick a different template
          </button>
        </div>
      </header>

      <div className="qs-progress" aria-label="Wizard progress">
        <div className="qs-progress-bar">
          <span style={{ width: `${pct}%` }} />
        </div>
        <span className="qs-progress-label">{pct}%</span>
      </div>

      {error ? (
        <div className="banner-err" role="alert">
          {error}
        </div>
      ) : null}

      <ol className="qs-step-list">
        {template.steps.map((step, idx) => {
          const result = session?.stepResults[step.id] ?? { status: "pending" as StepStatus };
          const isBusy = busyStep === step.id;
          const isDone = result.status === "done" || result.status === "skipped";
          return (
            <li
              key={step.id}
              className={`qs-step qs-step-${result.status}`}
            >
              <div className="qs-step-head">
                <span className="qs-step-num">
                  {result.status === "done" || result.status === "skipped"
                    ? "✓"
                    : idx + 1}
                </span>
                <div className="qs-step-title">
                  <strong>{step.title}</strong>
                  <span className="qs-step-blurb">{step.blurb}</span>
                </div>
                <span className={`qs-step-status qs-step-status-${result.status}`}>
                  {statusLabel(result.status)}
                </span>
              </div>

              <div className="qs-step-body">
                <div className="qs-step-grid">
                  {step.userActions?.length ? (
                    <div>
                      <h4>You do this</h4>
                      <ol>
                        {step.userActions.map((line) => (
                          <li key={line}>{line}</li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                  {step.wizardActions?.length ? (
                    <div>
                      <h4>Wizard does this</h4>
                      <ol>
                        {step.wizardActions.map((line) => (
                          <li key={line}>{line}</li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                </div>

                {step.storagePathHint ? (
                  <div className="qs-storage-callout">
                    <span className="qs-storage-label">On disk:</span>
                    <code>{step.storagePathHint}</code>
                  </div>
                ) : null}

                {result.message ? (
                  <p className="qs-step-message">{result.message}</p>
                ) : null}

                {result.artifacts ? (
                  <dl className="qs-artifacts">
                    {Object.entries(result.artifacts).map(([k, v]) => (
                      <div key={k}>
                        <dt>{k}</dt>
                        <dd>
                          <code>{v}</code>
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : null}

                <div className="qs-step-actions">
                  {step.run ? (
                    <button
                      type="button"
                      onClick={() => void runStep(step)}
                      disabled={isBusy}
                    >
                      {isDone ? "Re-run" : "Run"}
                    </button>
                  ) : null}
                  {step.skippable && !isDone ? (
                    <button
                      type="button"
                      onClick={() => skipStep(step)}
                      className="qs-skip"
                    >
                      Skip
                    </button>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
