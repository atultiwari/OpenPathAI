// Phase 21.5 chunk B — TabGuide render / dismiss / persistence.

import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { TabGuide } from "../components/tab-guide";
import { TAB_GUIDES, type TabGuideId } from "../components/tab-guide-content";

beforeEach(() => {
  globalThis.localStorage?.clear();
});

describe("TAB_GUIDES content", () => {
  const REQUIRED_TABS: TabGuideId[] = [
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
  ];

  it("ships an entry for every sidebar tab", () => {
    for (const tab of REQUIRED_TABS) {
      const entry = TAB_GUIDES[tab];
      expect(entry, `missing entry for ${tab}`).toBeDefined();
      expect(entry.title.length).toBeGreaterThan(0);
      expect(entry.purpose.length).toBeGreaterThan(40);
      expect(entry.steps.length).toBeGreaterThanOrEqual(2);
    }
  });
});

describe("<TabGuide>", () => {
  it("renders the expanded card by default and lists the steps", () => {
    render(<TabGuide tab="analyse" />);
    expect(screen.getByText(/About Analyse/i)).toBeInTheDocument();
    // Step 1 mentions the dropdown.
    expect(
      screen.getByText(/pick a model from the dropdown/i)
    ).toBeInTheDocument();
    // Python node row.
    expect(
      screen.getByText(/openpathai\.analyse\.classify_tile/i)
    ).toBeInTheDocument();
  });

  it("collapses to a pill when dismissed and persists across re-renders", () => {
    const { unmount } = render(<TabGuide tab="train" />);
    const dismiss = screen.getByRole("button", { name: /dismiss guide/i });
    fireEvent.click(dismiss);
    // After dismiss → only the re-open pill remains.
    expect(
      screen.queryByText(/Pick dataset \+ model \+ duration/i)
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /show "about train" guide/i })
    ).toBeInTheDocument();
    expect(localStorage.getItem("openpathai.tabguide.train.dismissed")).toBe(
      "1"
    );

    unmount();
    render(<TabGuide tab="train" />);
    // Persisted: still collapsed on a fresh mount.
    expect(
      screen.getByRole("button", { name: /show "about train" guide/i })
    ).toBeInTheDocument();
  });

  it("re-opens when the pill is clicked, clearing the persisted flag", () => {
    localStorage.setItem("openpathai.tabguide.audit.dismissed", "1");
    render(<TabGuide tab="audit" />);
    const pill = screen.getByRole("button", {
      name: /show "about audit" guide/i,
    });
    fireEvent.click(pill);
    expect(screen.getByText(/About Audit/i)).toBeInTheDocument();
    expect(
      localStorage.getItem("openpathai.tabguide.audit.dismissed")
    ).toBeNull();
  });
});
