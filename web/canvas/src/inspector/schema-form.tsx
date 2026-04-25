// Render a tiny pydantic JSON Schema as a form. We deliberately
// support only the widget kinds Phase-19 nodes actually use today —
// string, integer, number, boolean, enum, array<primitive>. Anything
// else falls back to a raw JSON textarea (safe escape hatch).

import { useMemo } from "react";
import type { JsonSchema } from "../api/types";

type Props = {
  schema: JsonSchema | undefined;
  values: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
};

type FieldKind =
  | "string"
  | "integer"
  | "number"
  | "boolean"
  | "enum"
  | "array_string"
  | "json";

function classifyField(schema: JsonSchema): FieldKind {
  if (Array.isArray(schema.enum) && schema.enum.length > 0) {
    return "enum";
  }
  if (schema.type === "boolean") {
    return "boolean";
  }
  if (schema.type === "integer") {
    return "integer";
  }
  if (schema.type === "number") {
    return "number";
  }
  if (schema.type === "string") {
    return "string";
  }
  if (
    schema.type === "array" &&
    schema.items &&
    typeof schema.items === "object" &&
    (schema.items as JsonSchema).type === "string"
  ) {
    return "array_string";
  }
  return "json";
}

function fieldLabel(name: string, schema: JsonSchema): string {
  if (typeof schema.description === "string" && schema.description) {
    return schema.description.length > 64
      ? schema.description.slice(0, 60) + "…"
      : schema.description;
  }
  return name;
}

function coerceNumber(raw: string, kind: "integer" | "number"): unknown {
  if (raw === "") return undefined;
  const num = kind === "integer" ? Number.parseInt(raw, 10) : Number(raw);
  if (Number.isNaN(num)) return raw;
  return num;
}

export function SchemaForm({ schema, values, onChange }: Props) {
  const properties: Record<string, JsonSchema> = useMemo(() => {
    if (!schema || typeof schema !== "object") return {};
    const props = (schema as JsonSchema).properties;
    return props ?? {};
  }, [schema]);

  const required = useMemo<Set<string>>(
    () =>
      new Set(
        Array.isArray(schema?.required)
          ? (schema?.required as string[])
          : []
      ),
    [schema]
  );

  if (!schema || Object.keys(properties).length === 0) {
    return (
      <p className="inspector-empty">
        This node has no configurable inputs.
      </p>
    );
  }

  function update(name: string, next: unknown): void {
    const merged = { ...values };
    if (next === undefined || next === "" || next === null) {
      delete merged[name];
    } else {
      merged[name] = next;
    }
    onChange(merged);
  }

  return (
    <form
      onSubmit={(e) => e.preventDefault()}
      style={{ display: "flex", flexDirection: "column" }}
    >
      {Object.entries(properties).map(([name, propSchema]) => {
        const kind = classifyField(propSchema);
        const raw = values[name];
        const isRequired = required.has(name);
        const labelText = fieldLabel(name, propSchema);
        const labelClass = isRequired ? "required" : undefined;

        if (kind === "boolean") {
          return (
            <div className="inspector-row" key={name}>
              <label className={labelClass} htmlFor={`f_${name}`}>
                {name}
              </label>
              <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                {labelText}
              </span>
              <input
                id={`f_${name}`}
                type="checkbox"
                checked={!!raw}
                onChange={(e) => update(name, e.target.checked)}
                style={{ width: "auto" }}
              />
            </div>
          );
        }

        if (kind === "enum") {
          const options = (propSchema.enum ?? []) as unknown[];
          return (
            <div className="inspector-row" key={name}>
              <label className={labelClass} htmlFor={`f_${name}`}>
                {name}
              </label>
              <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                {labelText}
              </span>
              <select
                id={`f_${name}`}
                value={raw === undefined ? "" : String(raw)}
                onChange={(e) => update(name, e.target.value || undefined)}
              >
                <option value="">—</option>
                {options.map((opt) => (
                  <option key={String(opt)} value={String(opt)}>
                    {String(opt)}
                  </option>
                ))}
              </select>
            </div>
          );
        }

        if (kind === "array_string") {
          const arr = Array.isArray(raw) ? (raw as unknown[]) : [];
          const text = arr.map((v) => String(v)).join("\n");
          return (
            <div className="inspector-row" key={name}>
              <label className={labelClass} htmlFor={`f_${name}`}>
                {name}
              </label>
              <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                {labelText} (one per line)
              </span>
              <textarea
                id={`f_${name}`}
                rows={3}
                value={text}
                onChange={(e) => {
                  const lines = e.target.value
                    .split("\n")
                    .map((s) => s.trim())
                    .filter(Boolean);
                  update(name, lines.length ? lines : undefined);
                }}
              />
            </div>
          );
        }

        if (kind === "json") {
          const text = raw === undefined ? "" : JSON.stringify(raw, null, 2);
          return (
            <div className="inspector-row" key={name}>
              <label className={labelClass} htmlFor={`f_${name}`}>
                {name} (JSON)
              </label>
              <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
                {labelText}
              </span>
              <textarea
                id={`f_${name}`}
                rows={4}
                value={text}
                onChange={(e) => {
                  if (!e.target.value.trim()) {
                    update(name, undefined);
                    return;
                  }
                  try {
                    update(name, JSON.parse(e.target.value));
                  } catch {
                    // Keep the user's draft; they'll fix it.
                    update(name, e.target.value);
                  }
                }}
              />
            </div>
          );
        }

        return (
          <div className="inspector-row" key={name}>
            <label className={labelClass} htmlFor={`f_${name}`}>
              {name}
            </label>
            <span style={{ fontSize: 11, color: "var(--color-text-dim)" }}>
              {labelText}
            </span>
            <input
              id={`f_${name}`}
              type={kind === "string" ? "text" : "number"}
              value={raw === undefined ? "" : String(raw)}
              onChange={(e) => {
                if (kind === "integer" || kind === "number") {
                  update(name, coerceNumber(e.target.value, kind));
                } else {
                  update(name, e.target.value || undefined);
                }
              }}
              step={kind === "integer" ? 1 : "any"}
            />
          </div>
        );
      })}
    </form>
  );
}
