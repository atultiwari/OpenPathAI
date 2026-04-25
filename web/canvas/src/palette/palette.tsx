import { useMemo } from "react";
import type { NodeSummary } from "../api/types";

type Props = {
  nodes: NodeSummary[];
  loading: boolean;
  error: string | null;
  filter: string;
  onFilterChange: (value: string) => void;
};

export function Palette({
  nodes,
  loading,
  error,
  filter,
  onFilterChange,
}: Props) {
  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) {
      return nodes;
    }
    return nodes.filter(
      (n) =>
        n.id.toLowerCase().includes(needle) ||
        n.description.toLowerCase().includes(needle)
    );
  }, [nodes, filter]);

  function onDragStart(event: React.DragEvent, op: string) {
    event.dataTransfer.setData("application/openpathai-op", op);
    event.dataTransfer.effectAllowed = "move";
  }

  return (
    <aside className="app-palette" aria-label="Node palette">
      <input
        type="search"
        placeholder="Filter nodes…"
        value={filter}
        onChange={(e) => onFilterChange(e.target.value)}
        aria-label="Filter nodes"
      />
      <h2>Nodes</h2>
      {loading ? (
        <p style={{ fontSize: 12, color: "var(--color-text-dim)" }}>
          Loading catalog…
        </p>
      ) : null}
      {error ? (
        <p style={{ fontSize: 12, color: "var(--color-error)" }}>{error}</p>
      ) : null}
      {!loading && !error && filtered.length === 0 ? (
        <p style={{ fontSize: 12, color: "var(--color-text-dim)" }}>
          {nodes.length
            ? "No matches."
            : "Catalog empty — is the API token correct?"}
        </p>
      ) : null}
      {filtered.map((node) => (
        <div
          key={node.id}
          className="palette-item"
          draggable
          onDragStart={(e) => onDragStart(e, node.id)}
          title={node.description}
        >
          {node.id}
          {node.description ? <small>{node.description}</small> : null}
        </div>
      ))}
    </aside>
  );
}
