// Phase 21.5 chunk C — HFTokenCard + ApiClient HF endpoints.

import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { ApiClient } from "../api/client";
import { AuthProvider } from "../api/auth-context";
import { HFTokenCard } from "../screens/settings/hf-token-card";

const originalFetch = globalThis.fetch;
const originalConfirm = globalThis.confirm;

afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.confirm = originalConfirm;
  globalThis.sessionStorage?.clear();
});

beforeEach(() => {
  globalThis.sessionStorage.setItem("__openpathai_canvas_token__", "tok");
});

function mockJson(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
  });
}

describe("ApiClient HF credentials methods", () => {
  it("getHfTokenStatus hits the GET endpoint", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe("http://api.test/v1/credentials/huggingface");
      return mockJson({
        present: false,
        source: "none",
        token_preview: null,
      });
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const client = new ApiClient("http://api.test", "tok");
    const status = await client.getHfTokenStatus();
    expect(status.source).toBe("none");
  });

  it("setHfToken PUTs the token in the body", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        expect(String(input)).toBe(
          "http://api.test/v1/credentials/huggingface"
        );
        expect(init?.method).toBe("PUT");
        expect(init?.body).toBe(JSON.stringify({ token: "hf_xyz" }));
        return mockJson({
          saved: true,
          secrets_path: "/x/secrets.json",
          status: { present: true, source: "settings", token_preview: "…_xyz" },
        });
      }
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const client = new ApiClient("http://api.test", "tok");
    const result = await client.setHfToken("hf_xyz");
    expect(result.saved).toBe(true);
    expect(result.status.token_preview).toBe("…_xyz");
  });
});

describe("<HFTokenCard>", () => {
  it("renders the active source from /v1/credentials/huggingface", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/v1/credentials/huggingface")) {
        return mockJson({
          present: true,
          source: "env_hf_token",
          token_preview: "…1234",
        });
      }
      return mockJson({});
    }) as unknown as typeof fetch;

    render(
      <AuthProvider>
        <HFTokenCard />
      </AuthProvider>
    );

    expect(await screen.findByText(/HF_TOKEN env var/i)).toBeInTheDocument();
    expect(screen.getByText("…1234")).toBeInTheDocument();
    // Test button is enabled when present.
    expect(
      screen.getByRole("button", { name: /test token/i })
    ).toBeEnabled();
    // Clear-settings button is disabled because the source is env, not settings.
    expect(
      screen.getByRole("button", { name: /clear settings token/i })
    ).toBeDisabled();
  });

  it("posts the typed token via setHfToken and surfaces the success banner", async () => {
    let putCalls = 0;
    globalThis.fetch = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/v1/credentials/huggingface") && init?.method === "PUT") {
          putCalls += 1;
          expect(init.body).toBe(JSON.stringify({ token: "hf_new_token" }));
          return mockJson({
            saved: true,
            secrets_path: "/tmp/secrets.json",
            status: {
              present: true,
              source: "settings",
              token_preview: "…oken",
            },
          });
        }
        // Initial GET → empty.
        return mockJson({
          present: false,
          source: "none",
          token_preview: null,
        });
      }
    ) as unknown as typeof fetch;

    render(
      <AuthProvider>
        <HFTokenCard />
      </AuthProvider>
    );

    // Wait for the initial GET to settle.
    await waitFor(() => {
      expect(
        screen.getByText(/Not configured/i)
      ).toBeInTheDocument();
    });

    const input = screen.getByLabelText(/token/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "hf_new_token" } });
    fireEvent.click(screen.getByRole("button", { name: /save token/i }));

    await waitFor(() => {
      expect(putCalls).toBe(1);
      expect(
        screen.getByText(/Token saved to \/tmp\/secrets\.json/i)
      ).toBeInTheDocument();
      expect(screen.getByText("…oken")).toBeInTheDocument();
    });
    // Token field cleared after save.
    expect(input.value).toBe("");
  });
});
