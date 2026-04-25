// Mirror of the Phase-19 server-side PHI middleware. Iron rule #8 says
// no filesystem path / patient identifier surfaces in plaintext, so we
// run every error string + every panel string through this helper
// before render. The server already redacts response bodies — this is
// defence-in-depth for the small set of strings we inject locally
// (e.g. ApiError.detail, prompt strings, etc.).

// These regexes scan **unescaped** JavaScript strings (after the
// network layer has already decoded the JSON body), so we don't need
// the server-side regex's JSON-escape lookahead. A windows path is
// just ``<letter>:\<identifier>``.
const UNIX_PATH_RE = /(?:\/Users\/|\/home\/|\/root\/)[^\s"']+/g;
const WIN_PATH_RE = /[A-Za-z]:\\[A-Za-z0-9_][^\s"']*/g;

async function sha256Hex8(value: string): Promise<string> {
  if (typeof crypto !== "undefined" && crypto.subtle) {
    const buf = new TextEncoder().encode(value);
    const digest = await crypto.subtle.digest("SHA-256", buf);
    const bytes = Array.from(new Uint8Array(digest));
    return bytes
      .slice(0, 4)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }
  // Fallback (test envs without WebCrypto): deterministic FNV-1a 32-bit.
  let hash = 0x811c9dc5;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0").slice(0, 8);
}

function basenameAndParent(path: string): { basename: string; parent: string } {
  const lastFs = path.lastIndexOf("/");
  const lastBs = path.lastIndexOf("\\");
  const cut = Math.max(lastFs, lastBs);
  if (cut < 0) {
    return { basename: path, parent: "" };
  }
  return { basename: path.slice(cut + 1), parent: path.slice(0, cut) };
}

// Synchronous redactor — the WebCrypto digest is async, so we use the
// FNV-1a fallback for the inline path. Sufficient for non-cryptographic
// "collation hint" semantics; the server's audit DB is the source of
// truth.
export function redactPathString(path: string): string {
  const { basename, parent } = basenameAndParent(path);
  let hash = 0x811c9dc5;
  for (let i = 0; i < parent.length; i += 1) {
    hash ^= parent.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  const suffix = hash.toString(16).padStart(8, "0").slice(0, 8);
  return `${basename}#${suffix}`;
}

export function redactString(value: string): string {
  if (!value) {
    return value;
  }
  return value
    .replace(UNIX_PATH_RE, (match) => redactPathString(match))
    .replace(WIN_PATH_RE, (match) => redactPathString(match));
}

export function redactPayload<T>(value: T): T {
  if (typeof value === "string") {
    return redactString(value) as unknown as T;
  }
  if (Array.isArray(value)) {
    return value.map((item) => redactPayload(item)) as unknown as T;
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = redactPayload(v);
    }
    return out as T;
  }
  return value;
}

export async function hashPatientId(value: string | null): Promise<string> {
  if (!value) {
    return "";
  }
  return "pt-" + (await sha256Hex8(value));
}
