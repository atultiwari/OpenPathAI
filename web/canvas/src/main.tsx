import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app";
import "./app.css";
import "@xyflow/react/dist/style.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("missing #root element");
}
createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>
);
