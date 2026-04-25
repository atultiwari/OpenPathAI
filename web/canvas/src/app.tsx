import { Suspense, lazy, useEffect, useState } from "react";
import { AuthProvider, useAuth } from "./api/auth-context";
import { NAV_TAB_EVENT } from "./components/quick-start-card";
import { AnalyseScreen } from "./screens/analyse/analyse-screen";
import { AnnotateScreen } from "./screens/annotate/annotate-screen";
import { CohortsScreen } from "./screens/cohorts/cohorts-screen";
import { DatasetsScreen } from "./screens/datasets/datasets-screen";
import { ModelsScreen } from "./screens/models/models-screen";
import { QuickstartScreen } from "./screens/quickstart/quickstart-screen";
import { SettingsScreen } from "./screens/settings/settings-screen";
import { TrainScreen } from "./screens/train/train-screen";
import { AuditPanel } from "./audit/audit-panel";
import { RunsPanel } from "./runs/runs-panel";

// Phase 21 refinement #3 — defer the React Flow + OpenSeadragon
// chunks until the user actually opens those screens.
const PipelinesScreen = lazy(() =>
  import("./screens/pipelines/pipelines-screen").then((m) => ({
    default: m.PipelinesScreen,
  }))
);
const SlidesScreen = lazy(() =>
  import("./screens/slides/slides-screen").then((m) => ({
    default: m.SlidesScreen,
  }))
);

import "./screens/screens.css";

type TaskTab =
  | "quickstart"
  | "analyse"
  | "slides"
  | "datasets"
  | "train"
  | "cohorts"
  | "annotate"
  | "models"
  | "runs"
  | "audit"
  | "pipelines"
  | "settings";

const TASK_TABS: {
  id: TaskTab;
  label: string;
  icon: string;
  group: "Doctor" | "ML" | "Power user";
}[] = [
  { id: "quickstart", label: "Quickstart", icon: "🚀", group: "Doctor" },
  { id: "analyse", label: "Analyse", icon: "🔬", group: "Doctor" },
  { id: "slides", label: "Slides", icon: "🩻", group: "Doctor" },
  { id: "datasets", label: "Datasets", icon: "🗂", group: "Doctor" },
  { id: "train", label: "Train", icon: "🎯", group: "Doctor" },
  { id: "cohorts", label: "Cohorts", icon: "🧪", group: "Doctor" },
  { id: "annotate", label: "Annotate", icon: "✍️", group: "Doctor" },
  { id: "models", label: "Models", icon: "📦", group: "ML" },
  { id: "runs", label: "Runs", icon: "📈", group: "ML" },
  { id: "audit", label: "Audit", icon: "🧾", group: "ML" },
  { id: "pipelines", label: "Pipelines", icon: "🧩", group: "Power user" },
  { id: "settings", label: "Settings", icon: "⚙", group: "Power user" },
];

function TokenPrompt({
  onSubmit,
  baseUrl,
  setBaseUrl,
}: {
  onSubmit: (token: string) => void;
  baseUrl: string;
  setBaseUrl: (url: string) => void;
}) {
  const [draft, setDraft] = useState("");
  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h2>Connect to OpenPathAI API</h2>
        <p className="inspector-empty">
          Paste the bearer token printed by <code>openpathai serve</code>.
          The token is held in this tab's session memory only — closing the
          tab clears it.
        </p>
        <form
          className="token-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim()) onSubmit(draft.trim());
          }}
        >
          <div className="inspector-row">
            <label htmlFor="t_baseurl">Base URL</label>
            <input
              id="t_baseurl"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://127.0.0.1:7870"
            />
          </div>
          <div className="inspector-row">
            <label htmlFor="t_token">Bearer token</label>
            <input
              id="t_token"
              type="password"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
            />
          </div>
          <div className="actions">
            <button type="submit" disabled={!draft.trim()}>
              Connect
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Sidebar({
  current,
  onPick,
  onSignOut,
}: {
  current: TaskTab;
  onPick: (tab: TaskTab) => void;
  onSignOut: () => void;
}) {
  const groups = ["Doctor", "ML", "Power user"] as const;
  return (
    <nav className="task-sidebar" aria-label="Primary navigation">
      {groups.map((group) => (
        <div key={group}>
          <h3>{group}</h3>
          {TASK_TABS.filter((t) => t.group === group).map((t) => (
            <button
              key={t.id}
              type="button"
              className={t.id === current ? "nav-item active" : "nav-item"}
              onClick={() => onPick(t.id)}
            >
              <span className="nav-icon" aria-hidden>
                {t.icon}
              </span>
              {t.label}
            </button>
          ))}
        </div>
      ))}
      <button
        type="button"
        className="nav-item"
        onClick={onSignOut}
        style={{ marginTop: "auto", color: "var(--color-text-dim)" }}
      >
        <span className="nav-icon" aria-hidden>
          ⏻
        </span>
        Sign out
      </button>
    </nav>
  );
}

const KNOWN_TABS: ReadonlySet<TaskTab> = new Set([
  "quickstart",
  "analyse",
  "slides",
  "datasets",
  "train",
  "cohorts",
  "annotate",
  "models",
  "runs",
  "audit",
  "pipelines",
  "settings",
]);

function CanvasShell() {
  const { token, setToken, baseUrl, setBaseUrl } = useAuth();
  const [tab, setTab] = useState<TaskTab>("quickstart");

  // Phase 21.5 chunk D — listen for cross-tab nav events emitted by
  // the Quick-start card. Decouples nav from prop-drilling without a
  // router.
  useEffect(() => {
    function onNav(event: Event) {
      const detail = (event as CustomEvent<unknown>).detail;
      if (typeof detail === "string" && KNOWN_TABS.has(detail as TaskTab)) {
        setTab(detail as TaskTab);
      }
    }
    window.addEventListener(NAV_TAB_EVENT, onNav);
    return () => window.removeEventListener(NAV_TAB_EVENT, onNav);
  }, []);

  if (!token) {
    return (
      <TokenPrompt
        baseUrl={baseUrl}
        setBaseUrl={setBaseUrl}
        onSubmit={setToken}
      />
    );
  }

  return (
    <div className="task-shell">
      <header className="task-topbar">
        <h1>OpenPathAI</h1>
        <span className="pill">{baseUrl}</span>
        <div className="topbar-actions">
          <span className="pill">v2.0 canvas</span>
        </div>
      </header>

      <Sidebar
        current={tab}
        onPick={setTab}
        onSignOut={() => setToken(null)}
      />

      <main style={{ gridArea: "content", overflow: "auto" }}>
        <Suspense fallback={<p className="inspector-empty">Loading…</p>}>
          {tab === "quickstart" && <QuickstartScreen />}
          {tab === "analyse" && <AnalyseScreen />}
          {tab === "slides" && <SlidesScreen />}
          {tab === "datasets" && <DatasetsScreen />}
          {tab === "train" && <TrainScreen />}
          {tab === "cohorts" && <CohortsScreen />}
          {tab === "annotate" && <AnnotateScreen />}
          {tab === "models" && <ModelsScreen />}
          {tab === "runs" && <RunsPanel />}
          {tab === "audit" && <AuditPanel />}
          {tab === "pipelines" && <PipelinesScreen />}
          {tab === "settings" && <SettingsScreen />}
        </Suspense>
      </main>
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <CanvasShell />
    </AuthProvider>
  );
}
