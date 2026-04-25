import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type { ModelSummary, TilePrediction } from "../../api/types";
import { safeMessage } from "../../lib/safe-string";

const EXPLAINERS = ["gradcam", "gradcam++", "eigencam", "attention", "ig"];

type ZeroShotState = {
  enabled: boolean;
  classes: string;
};

export function AnalyseScreen() {
  const { client } = useAuth();
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [modelName, setModelName] = useState<string>("");
  const [explainer, setExplainer] = useState<string>("gradcam");
  const [low, setLow] = useState<number>(0.4);
  const [high, setHigh] = useState<number>(0.6);
  const [zeroShot, setZeroShot] = useState<ZeroShotState>({
    enabled: false,
    classes: "benign\nmalignant",
  });
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TilePrediction | null>(null);
  const [zeroShotOutput, setZeroShotOutput] = useState<{
    classes: string[];
    probs: number[];
    predicted: string;
  } | null>(null);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    let cancelled = false;
    client
      .listModels({ limit: 200 })
      .then((response) => {
        if (cancelled) return;
        const eligible = response.items.filter((m) =>
          ["classifier", "foundation"].includes(m.kind)
        );
        setModels(eligible);
        if (!modelName && eligible.length) {
          setModelName(eligible[0].id);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(safeMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [client, modelName]);

  const onFile = useCallback((f: File | null) => {
    setFile(f);
    setResult(null);
    setZeroShotOutput(null);
    if (filePreview) URL.revokeObjectURL(filePreview);
    setFilePreview(f ? URL.createObjectURL(f) : null);
  }, [filePreview]);

  const onDrop = (event: React.DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragOver(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) onFile(dropped);
  };

  const submit = async () => {
    if (!file || !modelName) {
      setError("Pick a tile and a model first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (zeroShot.enabled) {
        const buf = await file.arrayBuffer();
        const b64 = btoa(
          String.fromCharCode(...new Uint8Array(buf).slice(0, buf.byteLength))
        );
        const classes = zeroShot.classes
          .split("\n")
          .map((c) => c.trim())
          .filter(Boolean);
        if (classes.length < 2) {
          throw new Error("Provide at least two class names.");
        }
        const response = await client.classifyNamed({
          image_b64: b64,
          classes,
        });
        setZeroShotOutput({
          classes: response.classes,
          probs: response.probs,
          predicted: response.predicted_prompt,
        });
      } else {
        const response = await client.analyseTile(file, {
          modelName,
          explainer,
          low,
          high,
        });
        setResult(response);
      }
    } catch (err) {
      setError(safeMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const downloadPdf = async () => {
    setBusy(true);
    try {
      const blob = await client.analyseReport();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `openpathai-analysis-${Date.now()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(safeMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="task-content">
      <h2>Analyse</h2>
      <p className="lede">
        Upload a tile (PNG / JPEG / TIFF). Pick a model and an explainer; or
        flip the zero-shot toggle to classify against free-text class names
        without training.
      </p>

      {error ? <div className="banner-err">{error}</div> : null}

      <div className="card">
        <h3>Input</h3>
        <label
          className={dragOver ? "dropzone is-over" : "dropzone"}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          {file ? (
            <span>
              <strong>{file.name}</strong> — {(file.size / 1024).toFixed(1)} KB
              <br />
              <small>(drop another file to replace)</small>
            </span>
          ) : (
            <span>Drop a tile here, or click to browse.</span>
          )}
          <input
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => onFile(e.target.files?.[0] ?? null)}
          />
        </label>
        {filePreview ? (
          <div style={{ marginTop: 12 }}>
            <figcaption>Preview</figcaption>
            <img
              alt="preview"
              src={filePreview}
              style={{ maxWidth: 240, borderRadius: 6, border: "1px solid var(--color-border)" }}
            />
          </div>
        ) : null}
      </div>

      <div className="card">
        <h3>Model & explainability</h3>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="a_model">Model</label>
            <select
              id="a_model"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              disabled={zeroShot.enabled}
            >
              {models.map((m) => (
                <option key={`${m.kind}-${m.id}`} value={m.id}>
                  {m.id} ({m.kind}){m.gated ? " — gated" : ""}
                </option>
              ))}
            </select>
            <span className="help">
              Filtered to classifier + foundation kinds.
            </span>
          </div>
          <div className="field">
            <label htmlFor="a_explainer">Explainer</label>
            <select
              id="a_explainer"
              value={explainer}
              onChange={(e) => setExplainer(e.target.value)}
              disabled={zeroShot.enabled}
            >
              {EXPLAINERS.map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="a_low">Borderline low</label>
            <input
              id="a_low"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={low}
              onChange={(e) => setLow(Number(e.target.value) || 0)}
              disabled={zeroShot.enabled}
            />
          </div>
          <div className="field">
            <label htmlFor="a_high">Borderline high</label>
            <input
              id="a_high"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={high}
              onChange={(e) => setHigh(Number(e.target.value) || 0)}
              disabled={zeroShot.enabled}
            />
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Zero-shot (CONCH)</h3>
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="checkbox"
            checked={zeroShot.enabled}
            style={{ width: "auto" }}
            onChange={(e) =>
              setZeroShot((s) => ({ ...s, enabled: e.target.checked }))
            }
          />
          <span>Use natural-language class names instead of a trained model</span>
        </label>
        {zeroShot.enabled ? (
          <div className="field" style={{ marginTop: 12 }}>
            <label htmlFor="a_zs_classes">Classes (one per line)</label>
            <textarea
              id="a_zs_classes"
              rows={4}
              value={zeroShot.classes}
              onChange={(e) =>
                setZeroShot((s) => ({ ...s, classes: e.target.value }))
              }
            />
          </div>
        ) : null}
      </div>

      <div className="toolbar">
        <button onClick={submit} disabled={busy || !file}>
          {busy ? "Working…" : "Analyse"}
        </button>
        <button onClick={downloadPdf} disabled={busy || !result}>
          Download PDF report
        </button>
      </div>

      {result ? <PredictionCard r={result} /> : null}
      {zeroShotOutput ? (
        <ZeroShotCard
          classes={zeroShotOutput.classes}
          probs={zeroShotOutput.probs}
          predicted={zeroShotOutput.predicted}
        />
      ) : null}
    </section>
  );
}

function PredictionCard({ r }: { r: TilePrediction }) {
  const top = Math.max(...r.probabilities);
  return (
    <div className="card">
      <h3>Prediction</h3>
      {r.fallback_reason ? (
        <div className="banner-warn">
          Resolved to <code>{r.resolved_model_name}</code> — fallback reason:{" "}
          {r.fallback_reason}
        </div>
      ) : null}
      <div className="kpi-row">
        <div className={r.borderline ? "kpi warn" : "kpi ok"}>
          <div className="label">Predicted class</div>
          <div className="value">{r.predicted_class}</div>
        </div>
        <div className="kpi">
          <div className="label">Confidence</div>
          <div className="value">{(top * 100).toFixed(1)}%</div>
        </div>
        <div className="kpi">
          <div className="label">Borderline</div>
          <div className="value">{r.borderline ? "Yes" : "No"}</div>
        </div>
      </div>
      <table className="panel-table bordered">
        <thead>
          <tr>
            <th>Class</th>
            <th>Probability</th>
          </tr>
        </thead>
        <tbody>
          {r.classes.map((cls, i) => (
            <tr key={cls}>
              <td>{cls}</td>
              <td>{(r.probabilities[i] * 100).toFixed(2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="preview-grid">
        <figure>
          <figcaption>Tile</figcaption>
          <img alt="tile" src={`data:image/png;base64,${r.thumbnail_b64}`} />
        </figure>
        <figure>
          <figcaption>Heatmap ({r.explainer_name})</figcaption>
          <img alt="heatmap" src={`data:image/png;base64,${r.heatmap_b64}`} />
        </figure>
      </div>
    </div>
  );
}

function ZeroShotCard({
  classes,
  probs,
  predicted,
}: {
  classes: string[];
  probs: number[];
  predicted: string;
}) {
  return (
    <div className="card">
      <h3>Zero-shot result</h3>
      <p className="lede">
        Predicted prompt: <code>{predicted}</code>
      </p>
      <table className="panel-table bordered">
        <thead>
          <tr>
            <th>Class</th>
            <th>Probability</th>
          </tr>
        </thead>
        <tbody>
          {classes.map((cls, i) => (
            <tr key={cls}>
              <td>{cls}</td>
              <td>{(probs[i] * 100).toFixed(2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
