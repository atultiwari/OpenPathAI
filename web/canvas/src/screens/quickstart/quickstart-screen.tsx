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
  TASK_LABELS,
  WIZARD_TEMPLATES,
  findTemplate,
  templatesByTask,
  type FixAction,
  type ManualChoice,
  type PreflightResult,
  type StepControl,
  type StepResult,
  type StepStatus,
  type WizardContext,
  type WizardStep,
  type WizardTemplate,
} from "./templates";
import { navigateToTab } from "../../components/quick-start-card";
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
  // Phase 22.0 chunk B/C — per-step preflight + which rows the user
  // has explicitly opened the inspect panel on.
  const [preflightCache, setPreflightCache] = useState<
    Record<string, PreflightResult>
  >({});
  const [inspectingStep, setInspectingStep] = useState<string | null>(null);
  const [preflightBusy, setPreflightBusy] = useState<string | null>(null);

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

  // Phase 22.0 chunk B — preflight runner. Returns the latest result
  // and caches it so the row can render the verdict without re-fetching.
  const runPreflight = useCallback(
    async (step: WizardStep): Promise<PreflightResult | null> => {
      if (!template || !step.preflight) return null;
      setPreflightBusy(step.id);
      try {
        const result = await step.preflight({
          client,
          template,
          state: ctxState.current,
        });
        setPreflightCache((prev) => ({ ...prev, [step.id]: result }));
        return result;
      } catch (err) {
        const result: PreflightResult = {
          ok: false,
          blockers: [
            {
              title: "Preflight failed",
              detail: err instanceof Error ? err.message : String(err),
            },
          ],
        };
        setPreflightCache((prev) => ({ ...prev, [step.id]: result }));
        return result;
      } finally {
        setPreflightBusy(null);
      }
    },
    [client, template]
  );

  // Phase 22.0 chunk D — execute a serialisable fix action.
  const applyFix = useCallback(
    async (step: WizardStep, action: FixAction) => {
      switch (action.kind) {
        case "set_state":
          ctxState.current = {
            ...ctxState.current,
            [action.key]: action.value,
          };
          // Persist + propagate.
          setSession((prev) => {
            if (!prev) return prev;
            const next = { ...prev, state: { ...ctxState.current } };
            saveSession(next);
            return next;
          });
          break;
        case "navigate_tab":
          navigateToTab(action.tab);
          return;
        case "open_url":
          if (typeof window !== "undefined") {
            window.open(action.url, "_blank", "noopener,noreferrer");
          }
          return;
        case "rerun_step":
          // The action's target step is the one we're currently
          // inspecting; just re-run preflight.
          break;
        case "noop":
          // intentionally no-op; message conveyed in the label
          break;
      }
      await runPreflight(step);
    },
    [runPreflight]
  );

  async function runStep(step: WizardStep) {
    if (!template || !step.run) return;
    setBusyStep(step.id);
    setError(null);

    // Phase 22.0 chunk B — refuse to run if preflight blocks. The row
    // surfaces the blockers + fixes inline; the user clicks Inspect to
    // see them.
    if (step.preflight) {
      const verdict = await runPreflight(step);
      if (verdict && !verdict.ok) {
        setBusyStep(null);
        setInspectingStep(step.id);
        const summary = verdict.blockers
          ? verdict.blockers.map((b) => b.title).join(" · ")
          : "Preflight failed.";
        updateResults(step.id, {
          status: "error",
          message: `Preflight blocked the run: ${summary}`,
        });
        setError(`Preflight blocked: ${summary}`);
        return;
      }
    }

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

  function confirmManualChoice(step: WizardStep, choice: ManualChoice) {
    if (!template) return;
    if (choice.state) {
      ctxState.current = { ...ctxState.current, ...choice.state };
    }
    updateResults(step.id, {
      status: choice.id === "skip_hf" ? "skipped" : "done",
      message: choice.message ?? `Confirmed: ${choice.label}.`,
    });
  }

  function setControlValue(controlId: string, value: unknown) {
    ctxState.current = { ...ctxState.current, [controlId]: value };
    setSession((prev) => {
      if (!prev) return prev;
      const next: StoredSession = {
        ...prev,
        state: { ...ctxState.current },
      };
      saveSession(next);
      return next;
    });
  }

  // Template picker (no session yet).
  if (!template) {
    return (
      <section className="task-content">
        <TabGuide tab="quickstart" />
        <h2>Quickstart wizard</h2>
        <p className="lede">
          Pick a task, then a template. Each template walks you through
          the dataset / model setup, the run itself, and where the
          artifacts land on disk. {WIZARD_TEMPLATES.length} templates
          ship across {templatesByTask().length} task types.
        </p>

        {templatesByTask().map(({ task, templates }) => (
          <div key={task} style={{ marginBottom: "var(--space-5)" }}>
            <h3
              style={{
                margin: "0 0 var(--space-2)",
                fontSize: 13,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                color: "var(--color-text-dim)",
              }}
            >
              {TASK_LABELS[task]} · {templates.length}
            </h3>
            <div className="qs-template-grid">
              {templates.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className="qs-template-card"
                  onClick={() => pickTemplate(t)}
                >
                  <div className="qs-template-head">
                    <strong>{t.label}</strong>
                    <div style={{ display: "flex", gap: 6 }}>
                      {t.preview ? (
                        <span className="qs-tier qs-tier-synthetic">
                          preview
                        </span>
                      ) : null}
                      <span className={`qs-tier qs-tier-${t.tier}`}>
                        {t.tier}
                      </span>
                    </div>
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
          </div>
        ))}
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

                {result.artifacts?.install_cmd ? (
                  <InstallHint command={result.artifacts.install_cmd} />
                ) : null}
                {result.artifacts?.install_extra && !result.artifacts?.install_cmd ? (
                  <InstallHint command={`uv sync --extra ${result.artifacts.install_extra.split(' ')[0].replace(/\[|\]/g, '')}`} />
                ) : null}

                {result.artifacts ? (
                  <dl className="qs-artifacts">
                    {Object.entries(result.artifacts)
                      .filter(([k]) => k !== "install_cmd" && k !== "install_extra")
                      .map(([k, v]) => (
                        <div key={k}>
                          <dt>{k}</dt>
                          <dd>
                            <code>{v}</code>
                          </dd>
                        </div>
                      ))}
                  </dl>
                ) : null}

                {step.controls?.length ? (
                  <div className="qs-controls">
                    {step.controls.map((control) =>
                      control.kind === "model_select" ? (
                        <ModelSelectControl
                          key={control.id}
                          control={control}
                          state={ctxState.current}
                          onChange={setControlValue}
                        />
                      ) : (
                        renderControl(control, ctxState.current, setControlValue)
                      )
                    )}
                  </div>
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
                  {step.manualChoices?.length
                    ? step.manualChoices.map((choice) => (
                        <button
                          key={choice.id}
                          type="button"
                          onClick={() => confirmManualChoice(step, choice)}
                          className={
                            choice.id === "skip_hf" || choice.id.startsWith("skip")
                              ? "qs-skip"
                              : undefined
                          }
                        >
                          {choice.label}
                        </button>
                      ))
                    : null}
                  {step.preflight ? (
                    (() => {
                      const verdict = preflightCache[step.id];
                      const issueCount =
                        (verdict?.blockers?.length ?? 0) +
                        (verdict?.warnings?.length ?? 0);
                      const label =
                        verdict == null
                          ? "Inspect"
                          : verdict.ok
                          ? `Inspect · ✓ preflight`
                          : `Inspect · ⚠ ${issueCount} issue${issueCount === 1 ? "" : "s"}`;
                      return (
                        <button
                          type="button"
                          className={
                            verdict && !verdict.ok ? undefined : "qs-skip"
                          }
                          onClick={async () => {
                            if (!verdict) await runPreflight(step);
                            setInspectingStep((curr) =>
                              curr === step.id ? null : step.id
                            );
                          }}
                        >
                          {preflightBusy === step.id ? "Checking…" : label}
                        </button>
                      );
                    })()
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

                {step.preflight && inspectingStep === step.id ? (
                  <PreflightPanel
                    verdict={preflightCache[step.id] ?? null}
                    onApplyFix={(fix) => void applyFix(step, fix.action)}
                    onRefresh={() => void runPreflight(step)}
                  />
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function PreflightPanel({
  verdict,
  onApplyFix,
  onRefresh,
}: {
  verdict: PreflightResult | null;
  onApplyFix: (fix: { label: string; action: FixAction }) => void;
  onRefresh: () => void;
}) {
  if (!verdict) {
    return (
      <div className="qs-preflight-panel">
        <p className="qs-preflight-empty">
          Click "Inspect" to run the preflight checks for this step.
        </p>
        <button type="button" onClick={onRefresh}>
          Run preflight
        </button>
      </div>
    );
  }
  return (
    <div
      className={`qs-preflight-panel ${
        verdict.ok ? "qs-preflight-ok" : "qs-preflight-bad"
      }`}
      role="region"
      aria-label="Step preflight"
    >
      <header>
        <strong>
          {verdict.ok
            ? "✓ Preflight passed"
            : `⚠ Preflight blocked the run (${verdict.blockers?.length ?? 0} issue${
                (verdict.blockers?.length ?? 0) === 1 ? "" : "s"
              })`}
        </strong>
        <button
          type="button"
          onClick={onRefresh}
          className="qs-preflight-refresh"
        >
          Re-check
        </button>
      </header>
      {verdict.manifest ? (
        <dl className="qs-preflight-manifest">
          {Object.entries(verdict.manifest).map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>
                <code>{v}</code>
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
      {verdict.blockers?.length ? (
        <ul className="qs-preflight-blockers">
          {verdict.blockers.map((b) => (
            <li key={b.title}>
              <strong>✗ {b.title}</strong>
              {b.detail ? <span>{b.detail}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {verdict.warnings?.length ? (
        <ul className="qs-preflight-warnings">
          {verdict.warnings.map((w) => (
            <li key={w.title}>
              <strong>⚠ {w.title}</strong>
              {w.detail ? <span>{w.detail}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {verdict.fixes?.length ? (
        <div className="qs-preflight-fixes">
          {verdict.fixes.map((f) => (
            <button
              key={f.label}
              type="button"
              onClick={() => onApplyFix(f)}
              className="qs-fix-button"
            >
              ↩ {f.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function InstallHint({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="qs-install-hint" role="status">
      <strong>Install the missing extra:</strong>
      <code>{command}</code>
      <button
        type="button"
        onClick={() => {
          if (typeof navigator !== "undefined" && navigator.clipboard) {
            void navigator.clipboard.writeText(command).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1200);
            });
          }
        }}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function ModelSelectControl({
  control,
  state,
  onChange,
}: {
  control: Extract<StepControl, { kind: "model_select" }>;
  state: Record<string, unknown>;
  onChange: (id: string, value: unknown) => void;
}) {
  const { client } = useAuth();
  const [models, setModels] = useState<
    { id: string; label: string; downloaded: boolean; gated: boolean }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const current =
    typeof state[control.id] === "string"
      ? (state[control.id] as string)
      : control.defaultValue ?? "";

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const kinds = control.kindFilter ?? ["foundation", "classifier"];
        const responses = await Promise.all(
          kinds.map((k) =>
            client.listModels({ kind: k, limit: 200 }).catch(() => null)
          )
        );
        const all = responses
          .filter((r): r is NonNullable<typeof r> => r != null)
          .flatMap((r) => (Array.isArray(r.items) ? r.items : []));
        if (cancelled) return;
        const enriched = await Promise.all(
          all.map(async (m) => {
            let downloaded = false;
            try {
              const status = await client.getModelStatus(m.id);
              downloaded = status.present;
            } catch {
              // best-effort
            }
            return {
              id: m.id,
              gated: m.gated,
              downloaded,
              label: `${m.id} · ${m.license ?? "?"}${
                downloaded ? " · ✓ on disk" : ""
              }${m.gated && !downloaded ? " · gated" : ""}`,
            };
          })
        );
        if (!cancelled) setModels(enriched);
      } catch {
        // best-effort — fall back to defaultValue only
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client, control.kindFilter]);

  // Seed default into ctx.state on first mount so the train run sees it.
  useEffect(() => {
    if (!state[control.id] && control.defaultValue) {
      onChange(control.id, control.defaultValue);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="qs-control">
      <label htmlFor={`qs-${control.id}`}>{control.label}</label>
      <select
        id={`qs-${control.id}`}
        value={current}
        onChange={(e) => onChange(control.id, e.target.value)}
      >
        {loading ? <option value={current}>loading…</option> : null}
        {!loading && models.length === 0 ? (
          <option value={current}>{current || "(no models)"}</option>
        ) : null}
        {models.map((m) => (
          <option
            key={m.id}
            value={m.id}
            disabled={m.gated && !m.downloaded}
          >
            {m.label}
          </option>
        ))}
      </select>
      {control.help ? <span className="qs-control-help">{control.help}</span> : null}
    </div>
  );
}

function renderControl(
  control: StepControl,
  state: Record<string, unknown>,
  onChange: (id: string, value: unknown) => void
) {
  const current = state[control.id];
  if (control.kind === "text") {
    return (
      <div key={control.id} className="qs-control">
        <label htmlFor={`qs-${control.id}`}>{control.label}</label>
        <input
          id={`qs-${control.id}`}
          type="text"
          placeholder={control.placeholder}
          value={typeof current === "string" ? current : ""}
          onChange={(e) => onChange(control.id, e.target.value)}
          spellCheck={false}
          autoComplete="off"
        />
        {control.help ? <span className="qs-control-help">{control.help}</span> : null}
      </div>
    );
  }
  if (control.kind === "select") {
    const value =
      typeof current === "string" && control.options.includes(current)
        ? current
        : control.options[0];
    return (
      <div key={control.id} className="qs-control">
        <label htmlFor={`qs-${control.id}`}>{control.label}</label>
        <select
          id={`qs-${control.id}`}
          value={value}
          onChange={(e) => onChange(control.id, e.target.value)}
        >
          {control.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        {control.help ? <span className="qs-control-help">{control.help}</span> : null}
      </div>
    );
  }
  // checkbox
  const checked = current === undefined ? true : current === true;
  return (
    <div key={control.id} className="qs-control qs-control-checkbox">
      <label htmlFor={`qs-${control.id}`}>
        <input
          id={`qs-${control.id}`}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(control.id, e.target.checked)}
        />
        <span>{control.label}</span>
      </label>
      {control.help ? <span className="qs-control-help">{control.help}</span> : null}
    </div>
  );
}
