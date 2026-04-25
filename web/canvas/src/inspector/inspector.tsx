import type { NodeSummary } from "../api/types";
import type { CanvasNode, CanvasState } from "../canvas/types";
import { SchemaForm } from "./schema-form";

type Props = {
  canvas: CanvasState;
  selection: string | null;
  catalog: Map<string, NodeSummary>;
  onChange: (next: CanvasState) => void;
  onRename: (oldId: string, newId: string) => void;
};

function findNode(
  canvas: CanvasState,
  id: string | null
): CanvasNode | undefined {
  if (!id) return undefined;
  return canvas.nodes.find((n) => n.id === id);
}

export function Inspector({
  canvas,
  selection,
  catalog,
  onChange,
  onRename,
}: Props) {
  const node = findNode(canvas, selection);

  if (!node) {
    return (
      <aside className="app-inspector" aria-label="Inspector">
        <h2>Inspector</h2>
        <p className="inspector-empty">
          Select a node on the canvas to edit its inputs, or drag a node from
          the palette to start.
        </p>
        <h2 style={{ marginTop: 24 }}>Pipeline</h2>
        <div className="inspector-row">
          <label htmlFor="pipeline-id">Pipeline id</label>
          <input
            id="pipeline-id"
            value={canvas.pipelineId}
            onChange={(e) =>
              onChange({ ...canvas, pipelineId: e.target.value })
            }
          />
        </div>
        <div className="inspector-row">
          <label htmlFor="pipeline-mode">Mode</label>
          <select
            id="pipeline-mode"
            value={canvas.mode}
            onChange={(e) =>
              onChange({
                ...canvas,
                mode: e.target.value as CanvasState["mode"],
              })
            }
          >
            <option value="exploratory">exploratory</option>
            <option value="diagnostic">diagnostic</option>
          </select>
        </div>
      </aside>
    );
  }

  const summary = catalog.get(node.data.op);

  function update(newInputs: Record<string, unknown>) {
    const nextNodes = canvas.nodes.map((n) =>
      n.id === node!.id
        ? { ...n, data: { ...n.data, inputs: newInputs } }
        : n
    );
    onChange({ ...canvas, nodes: nextNodes });
  }

  return (
    <aside className="app-inspector" aria-label="Inspector">
      <h2>Step</h2>
      <div className="inspector-row">
        <label htmlFor="step-id">Step id</label>
        <input
          id="step-id"
          value={node.id}
          onChange={(e) => onRename(node.id, e.target.value)}
        />
      </div>
      <div className="inspector-row">
        <label>Op</label>
        <code style={{ fontSize: 12 }}>{node.data.op}</code>
      </div>
      {summary?.description ? (
        <p className="inspector-empty">{summary.description}</p>
      ) : null}

      <h2>Inputs</h2>
      <SchemaForm
        schema={summary?.input_schema}
        values={node.data.inputs}
        onChange={update}
      />

      <button
        type="button"
        style={{ marginTop: 16 }}
        onClick={() => {
          onChange({
            ...canvas,
            nodes: canvas.nodes.filter((n) => n.id !== node.id),
            edges: canvas.edges.filter(
              (e) => e.source !== node.id && e.target !== node.id
            ),
          });
        }}
      >
        Remove step
      </button>
    </aside>
  );
}
