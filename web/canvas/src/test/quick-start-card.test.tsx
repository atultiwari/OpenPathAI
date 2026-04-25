// Phase 21.5 chunk D — QuickStartCard render / nav / dismiss / token state.

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import {
  QuickStartCard,
  NAV_TAB_EVENT,
  navigateToTab,
} from "../components/quick-start-card";
import { AuthProvider } from "../api/auth-context";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.localStorage?.clear();
  globalThis.sessionStorage?.clear();
  globalThis.sessionStorage.setItem("__openpathai_canvas_token__", "tok");
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function mockJson(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
  });
}

function mockHfStatus(present: boolean) {
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/v1/credentials/huggingface")) {
      return mockJson({
        present,
        source: present ? "settings" : "none",
        token_preview: present ? "…abcd" : null,
      });
    }
    return mockJson({});
  }) as unknown as typeof fetch;
}

describe("<QuickStartCard>", () => {
  it("renders the four-step list and a docs link by default", async () => {
    mockHfStatus(false);

    render(
      <AuthProvider>
        <QuickStartCard />
      </AuthProvider>
    );

    expect(
      await screen.findByText(/quick start — first end-to-end run/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/plumb your hugging face token/i)).toBeInTheDocument();
    expect(screen.getByText(/pick a dataset/i)).toBeInTheDocument();
    expect(screen.getByText(/train a classifier/i)).toBeInTheDocument();
    expect(screen.getByText(/drop a tile here/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /read the full quickstart/i })
    ).toHaveAttribute(
      "href",
      "https://github.com/atultiwari/OpenPathAI/blob/main/docs/quickstart.md"
    );
  });

  it("marks the HF step done when the resolver reports a token", async () => {
    mockHfStatus(true);

    render(
      <AuthProvider>
        <QuickStartCard />
      </AuthProvider>
    );

    // Wait for the GET to settle and assert the step row picked up the
    // .is-done class via the leading checkmark.
    await waitFor(() => {
      const stepText = screen.getByText(
        /plumb your hugging face token/i
      );
      const li = stepText.closest("li");
      expect(li).not.toBeNull();
      expect(li).toHaveClass("is-done");
    });
    expect(screen.getByText(/active source: settings/i)).toBeInTheDocument();
  });

  it("emits a nav-tab event when an Open <Tab> button is clicked", async () => {
    mockHfStatus(false);
    const navHandler = vi.fn();
    window.addEventListener(NAV_TAB_EVENT, navHandler);

    try {
      render(
        <AuthProvider>
          <QuickStartCard />
        </AuthProvider>
      );
      const settingsBtn = await screen.findByRole("button", {
        name: /open settings/i,
      });
      fireEvent.click(settingsBtn);
      expect(navHandler).toHaveBeenCalledTimes(1);
      const evt = navHandler.mock.calls[0]?.[0] as CustomEvent<unknown>;
      expect(evt.detail).toBe("settings");
    } finally {
      window.removeEventListener(NAV_TAB_EVENT, navHandler);
    }
  });

  it("dismiss collapses to a pill that re-opens the card", async () => {
    mockHfStatus(false);

    const { unmount } = render(
      <AuthProvider>
        <QuickStartCard />
      </AuthProvider>
    );

    await screen.findByText(/quick start — first end-to-end run/i);
    fireEvent.click(
      screen.getByRole("button", { name: /dismiss quick start card/i })
    );
    expect(
      screen.queryByText(/quick start — first end-to-end run/i)
    ).not.toBeInTheDocument();
    const pill = screen.getByRole("button", {
      name: /show the quick start card/i,
    });
    expect(pill).toBeInTheDocument();
    expect(localStorage.getItem("openpathai.quickstart.dismissed")).toBe("1");

    unmount();

    // Persisted on a fresh mount.
    render(
      <AuthProvider>
        <QuickStartCard />
      </AuthProvider>
    );
    expect(
      screen.getByRole("button", { name: /show the quick start card/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/quick start — first end-to-end run/i)
    ).not.toBeInTheDocument();
  });

  it("navigateToTab helper dispatches the documented event", () => {
    const handler = vi.fn();
    window.addEventListener(NAV_TAB_EVENT, handler);
    try {
      navigateToTab("train");
      expect(handler).toHaveBeenCalledTimes(1);
      const evt = handler.mock.calls[0]?.[0] as CustomEvent<unknown>;
      expect(evt.detail).toBe("train");
    } finally {
      window.removeEventListener(NAV_TAB_EVENT, handler);
    }
  });
});
