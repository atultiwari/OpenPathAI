// Shared canvas state types.

import type { Pipeline, PipelineStep } from "../api/types";

export type CanvasNodeData = {
  op: string;
  description?: string;
  inputs: Record<string, unknown>;
};

export type CanvasNode = {
  id: string;
  type: "openpathai";
  position: { x: number; y: number };
  data: CanvasNodeData;
};

export type CanvasEdge = {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
};

export type CanvasState = {
  pipelineId: string;
  mode: Pipeline["mode"];
  nodes: CanvasNode[];
  edges: CanvasEdge[];
};

export function newCanvas(pipelineId = "untitled"): CanvasState {
  return {
    pipelineId,
    mode: "exploratory",
    nodes: [],
    edges: [],
  };
}

export function toPipeline(canvas: CanvasState): Pipeline {
  const steps: PipelineStep[] = canvas.nodes.map((node) => ({
    id: node.id,
    op: node.data.op,
    inputs: { ...node.data.inputs },
  }));
  return {
    id: canvas.pipelineId,
    mode: canvas.mode,
    steps,
  };
}

export function uniqueStepId(canvas: CanvasState, op: string): string {
  const base = op.replace(/[^A-Za-z0-9_]/g, "_") || "node";
  let i = 1;
  let candidate = `${base}_${i}`;
  const used = new Set(canvas.nodes.map((n) => n.id));
  while (used.has(candidate)) {
    i += 1;
    candidate = `${base}_${i}`;
  }
  return candidate;
}
