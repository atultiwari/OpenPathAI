import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { SchemaForm } from "../inspector/schema-form";

describe("SchemaForm", () => {
  it("renders a friendly placeholder when there are no inputs", () => {
    render(<SchemaForm schema={undefined} values={{}} onChange={() => {}} />);
    expect(screen.getByText(/no configurable inputs/i)).toBeInTheDocument();
  });

  it("renders required fields with the required marker", () => {
    render(
      <SchemaForm
        schema={{
          type: "object",
          required: ["name"],
          properties: {
            name: { type: "string", description: "tile id" },
          },
        }}
        values={{}}
        onChange={() => {}}
      />
    );
    const label = screen.getByText("name");
    expect(label.classList.contains("required")).toBe(true);
  });

  it("converts integer inputs", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: { epochs: { type: "integer" } },
        }}
        values={{}}
        onChange={onChange}
      />
    );
    fireEvent.change(screen.getByLabelText("epochs"), {
      target: { value: "5" },
    });
    expect(onChange).toHaveBeenCalledWith({ epochs: 5 });
  });

  it("renders enum as a select", () => {
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: {
            mode: { type: "string", enum: ["fast", "thorough"] },
          },
        }}
        values={{ mode: "fast" }}
        onChange={() => {}}
      />
    );
    const select = screen.getByLabelText("mode") as HTMLSelectElement;
    expect(select.tagName).toBe("SELECT");
    expect(select.value).toBe("fast");
  });
});
