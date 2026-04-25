// Tiny helpers to keep panel strings readable without leaking PHI.

import { redactString } from "./redact";

export function safeMessage(error: unknown): string {
  if (error instanceof Error) {
    return redactString(error.message);
  }
  if (typeof error === "string") {
    return redactString(error);
  }
  try {
    return redactString(JSON.stringify(error));
  } catch {
    return "Unknown error";
  }
}

export function shortHash(value: string | null | undefined, len = 8): string {
  if (!value) {
    return "";
  }
  return value.length <= len ? value : value.slice(0, len);
}
