import { describe, expect, it, vi, afterEach } from "vitest";
import { ApiClient, ApiError } from "../api/client";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function mockJson(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
  });
}

describe("ApiClient", () => {
  it("includes a bearer token in protected calls", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        expect(url).toBe("http://api.test/v1/nodes");
        const headers = (init?.headers ?? {}) as Record<string, string>;
        expect(headers.Authorization).toBe("Bearer tok-123");
        expect(headers.Accept).toBe("application/json");
        return mockJson({ items: [], total: 0 });
      }
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const client = new ApiClient("http://api.test/", "tok-123");
    const response = await client.listNodes();
    expect(response.total).toBe(0);
  });

  it("surfaces an ApiError for non-2xx responses", async () => {
    globalThis.fetch = vi.fn(async () =>
      mockJson({ detail: "missing token" }, { status: 401 })
    ) as unknown as typeof fetch;
    const client = new ApiClient("http://api.test", null);
    await expect(client.listNodes()).rejects.toMatchObject({
      status: 401,
      detail: "missing token",
    });
  });

  it("passes query params through", async () => {
    let captured: string | null = null;
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      captured = String(input);
      return mockJson({ items: [], total: 0 });
    }) as unknown as typeof fetch;
    const client = new ApiClient("http://api.test", "tok");
    await client.listModels({ kind: "foundation", limit: 5 });
    expect(captured).toContain("kind=foundation");
    expect(captured).toContain("limit=5");
  });

  it("returns undefined for 204 responses", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(null, { status: 204 })
    ) as unknown as typeof fetch;
    const client = new ApiClient("http://api.test", "tok");
    await expect(client.deletePipeline("demo")).resolves.toBeUndefined();
  });

  it("ApiError can be thrown + caught", () => {
    const e = new ApiError(409, "conflict");
    expect(e.message).toContain("409");
    expect(e.status).toBe(409);
  });
});
