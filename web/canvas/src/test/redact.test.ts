import { describe, expect, it } from "vitest";
import { redactPathString, redactPayload, redactString } from "../lib/redact";

describe("redactString", () => {
  it("rewrites unix paths", () => {
    const out = redactString("/Users/dr-smith/patient-42/slide.svs");
    expect(out).not.toContain("/Users/");
    expect(out).toContain("slide.svs");
  });

  it("rewrites windows paths", () => {
    const out = redactString("C:\\data\\cases\\CaseA.svs");
    expect(out).toMatch(/CaseA\.svs#/);
    expect(out).not.toContain("\\data\\cases");
  });

  it("leaves text without paths untouched", () => {
    expect(redactString("plain prose")).toBe("plain prose");
    expect(redactString("")).toBe("");
  });

  it("collates same parent to same suffix", () => {
    const a = redactPathString("/Users/x/a.svs");
    const b = redactPathString("/Users/x/b.svs");
    expect(a.split("#")[1]).toBe(b.split("#")[1]);
  });
});

describe("redactPayload", () => {
  it("recurses into nested structures", () => {
    const input = {
      arr: ["/Users/dr/a.svs", "/home/x/b.svs"],
      nested: { p: "C:\\foo\\bar.svs" },
      keep: 42,
    };
    const out = redactPayload(input) as typeof input;
    expect(out.arr[0]).not.toContain("/Users/");
    expect(out.arr[1]).not.toContain("/home/");
    expect(out.nested.p).not.toContain("\\foo\\bar.svs");
    expect(out.keep).toBe(42);
  });
});
