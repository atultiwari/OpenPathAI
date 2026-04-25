import { useCallback, useMemo } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
} from "@xyflow/react";
import type { Connection, Edge, EdgeChange, Node, NodeChange } from "@xyflow/react";
import type { NodeSummary } from "../api/types";
import type { CanvasNode, CanvasState } from "./types";
import { uniqueStepId } from "./types";
import { nodeTypes } from "./node-types";

type Props = {
  canvas: CanvasState;
  onChange: (next: CanvasState) => void;
  selection: string | null;
  onSelect: (id: string | null) => void;
  catalog: Map<string, NodeSummary>;
};

export function Canvas({
  canvas,
  onChange,
  selection,
  onSelect,
  catalog,
}: Props) {
  const nodes = useMemo<Node[]>(
    () =>
      canvas.nodes.map((n) => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: n.data,
        selected: n.id === selection,
      })),
    [canvas.nodes, selection]
  );

  const edges = useMemo<Edge[]>(
    () =>
      canvas.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle,
      })),
    [canvas.edges]
  );

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const next = applyNodeChanges(changes, nodes);
      const updated: CanvasNode[] = next.map((n) => {
        const found = canvas.nodes.find((c) => c.id === n.id);
        const data = (n.data as CanvasNode["data"]) ?? found?.data ?? {
          op: n.id,
          inputs: {},
        };
        return {
          id: n.id,
          type: "openpathai",
          position: n.position,
          data,
        };
      });
      onChange({ ...canvas, nodes: updated });
    },
    [canvas, nodes, onChange]
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const next = applyEdgeChanges(changes, edges);
      onChange({
        ...canvas,
        edges: next.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle ?? undefined,
          targetHandle: e.targetHandle ?? undefined,
        })),
      });
    },
    [canvas, edges, onChange]
  );

  const onConnect = useCallback(
    (params: Connection) => {
      const next = addEdge(params, edges);
      onChange({
        ...canvas,
        edges: next.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle ?? undefined,
          targetHandle: e.targetHandle ?? undefined,
        })),
      });
    },
    [canvas, edges, onChange]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const op = event.dataTransfer.getData("application/openpathai-op");
      if (!op) {
        return;
      }
      const summary = catalog.get(op);
      const stepId = uniqueStepId(canvas, op);
      const target = event.currentTarget as HTMLElement;
      const bounds = target.getBoundingClientRect();
      const newNode: CanvasNode = {
        id: stepId,
        type: "openpathai",
        position: {
          x: event.clientX - bounds.left,
          y: event.clientY - bounds.top,
        },
        data: {
          op,
          description: summary?.description ?? "",
          inputs: {},
        },
      };
      onChange({ ...canvas, nodes: [...canvas.nodes, newNode] });
      onSelect(stepId);
    },
    [canvas, catalog, onChange, onSelect]
  );

  return (
    <div
      className="app-canvas"
      onDragOver={onDragOver}
      onDrop={onDrop}
      style={{ width: "100%", height: "100%" }}
    >
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => onSelect(node.id)}
          onPaneClick={() => onSelect(null)}
          fitView
        >
          <Background gap={16} />
          <Controls position="bottom-right" />
          <MiniMap pannable zoomable />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
