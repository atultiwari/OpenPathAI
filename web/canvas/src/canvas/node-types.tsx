import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import type { CanvasNodeData } from "./types";

const cardStyle: React.CSSProperties = {
  background: "var(--color-panel-2)",
  border: "1px solid var(--color-border)",
  borderRadius: "6px",
  padding: "8px 10px",
  minWidth: "180px",
  fontSize: "12px",
  color: "var(--color-text)",
  boxShadow: "0 1px 0 rgba(0,0,0,0.4)",
};

const titleStyle: React.CSSProperties = {
  fontWeight: 600,
  marginBottom: 4,
};

const opStyle: React.CSSProperties = {
  color: "var(--color-text-dim)",
  fontFamily: "ui-monospace, SF Mono, Menlo, monospace",
  fontSize: 11,
};

export function OpenPathAINode({
  data,
  selected,
}: NodeProps & { data: CanvasNodeData }) {
  return (
    <div
      style={{
        ...cardStyle,
        borderColor: selected ? "var(--color-accent)" : "var(--color-border)",
      }}
    >
      <Handle type="target" position={Position.Left} />
      <div style={titleStyle}>{data.op}</div>
      {data.description ? (
        <div style={{ color: "var(--color-text-dim)", marginBottom: 6 }}>
          {data.description}
        </div>
      ) : null}
      <div style={opStyle}>op = {data.op}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export const nodeTypes = {
  openpathai: OpenPathAINode,
} as const;
