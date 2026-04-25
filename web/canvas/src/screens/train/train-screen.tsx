import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../api/auth-context";
import type {
  DatasetCard,
  ModelSummary,
  TrainMetricsResponse,
} from "../../api/types";
import { safeMessage } from "../../lib/safe-string";
import { TabGuide } from "../../components/tab-guide";
import { StorageBanner } from "../../components/storage-banner";

type DurationPreset = "Quick" | "Standard" | "Thorough";
type Difficulty = "Easy" | "Standard" | "Expert";

const DURATION_TO_EPOCHS: Record<DurationPreset, number> = {
  Quick: 1,
  Standard: 5,
  Thorough: 20,
};

export function TrainScreen() {
  const { client } = useAuth();
  const [datasets, setDatasets] = useState<DatasetCard[]>([]);
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [difficulty, setDifficulty] = useState<Difficulty>("Easy");
  const [duration, setDuration] = useState<DurationPreset>("Standard");
  const [datasetName, setDatasetName] = useState<string>("");
  const [modelName, setModelName] = useState<string>("");
  const [epochs, setEpochs] = useState<number>(5);
  const [batchSize, setBatchSize] = useState<number>(32);
  const [learningRate, setLearningRate] = useState<number>(1e-3);
  const [seed, setSeed] = useState<number>(0);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<TrainMetricsResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      client.listDatasets({ limit: 500 }),
      client.listModels({ kind: "classifier", limit: 500 }),
    ])
      .then(([d, m]) => {
        if (cancelled) return;
        setDatasets(d.items);
        setModels(m.items);
        if (!datasetName && d.items.length) setDatasetName(d.items[0].name);
        if (!modelName && m.items.length) setModelName(m.items[0].id);
      })
      .catch((err) => {
        if (!cancelled) setError(safeMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [client, datasetName, modelName]);

  // Easy mode controls duration via the preset; Standard/Expert allow direct hparam edits.
  const effectiveEpochs = useMemo(() => {
    if (difficulty === "Easy") return DURATION_TO_EPOCHS[duration];
    return epochs;
  }, [difficulty, duration, epochs]);

  const start = async () => {
    setRunning(true);
    setError(null);
    setMetrics(null);
    try {
      const record = await client.submitTrain({
        dataset: datasetName,
        model: modelName,
        epochs: effectiveEpochs,
        batch_size: batchSize,
        learning_rate: learningRate,
        seed,
        duration_preset: duration,
      });
      setRunId(record.run_id);
    } catch (err) {
      setError(safeMessage(err));
    } finally {
      setRunning(false);
    }
  };

  // Polling
  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const m = await client.getTrainMetrics(runId);
        if (cancelled) return;
        setMetrics(m);
        if (m.status !== "queued" && m.status !== "running") return;
      } catch (err) {
        if (!cancelled) setError(safeMessage(err));
        return;
      }
      window.setTimeout(tick, 1500);
    };
    tick();
    return () => {
      cancelled = true;
    };
  }, [client, runId]);

  return (
    <section className="task-content">
      <TabGuide tab="train" />
      <StorageBanner paths={["checkpoints", "models"]} />
      <h2>Train</h2>
      <p className="lede">
        Pick a dataset and a model. Easy mode collapses everything to a
        duration preset; Standard surfaces learning rate, batch size, seed;
        Expert exposes the full hparam matrix (loss, scheduler, etc. — coming
        soon).
      </p>

      {error ? <div className="banner-err">{error}</div> : null}

      <div className="card">
        <h3>Difficulty</h3>
        <div className="toolbar">
          {(["Easy", "Standard", "Expert"] as Difficulty[]).map((d) => (
            <button
              key={d}
              onClick={() => setDifficulty(d)}
              className={d === difficulty ? "active" : undefined}
              style={
                d === difficulty
                  ? { borderColor: "var(--color-accent)", color: "var(--color-accent)" }
                  : undefined
              }
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Pick</h3>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="t_dataset">Dataset</label>
            <select
              id="t_dataset"
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value)}
            >
              {datasets.map((d) => (
                <option key={d.name} value={d.name}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="t_model">Model</label>
            <select
              id="t_model"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.id}
                </option>
              ))}
            </select>
          </div>
          {difficulty === "Easy" ? (
            <div className="field">
              <label htmlFor="t_duration">Duration</label>
              <select
                id="t_duration"
                value={duration}
                onChange={(e) => setDuration(e.target.value as DurationPreset)}
              >
                <option value="Quick">Quick (1 epoch)</option>
                <option value="Standard">Standard (5 epochs)</option>
                <option value="Thorough">Thorough (20 epochs)</option>
              </select>
            </div>
          ) : (
            <>
              <div className="field">
                <label htmlFor="t_epochs">Epochs</label>
                <input
                  id="t_epochs"
                  type="number"
                  min={1}
                  max={200}
                  value={epochs}
                  onChange={(e) => setEpochs(Number(e.target.value) || 1)}
                />
              </div>
              <div className="field">
                <label htmlFor="t_bs">Batch size</label>
                <input
                  id="t_bs"
                  type="number"
                  min={1}
                  max={1024}
                  value={batchSize}
                  onChange={(e) => setBatchSize(Number(e.target.value) || 1)}
                />
              </div>
              <div className="field">
                <label htmlFor="t_lr">Learning rate</label>
                <input
                  id="t_lr"
                  type="number"
                  min={0}
                  max={1}
                  step={1e-4}
                  value={learningRate}
                  onChange={(e) =>
                    setLearningRate(Number(e.target.value) || 1e-3)
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="t_seed">Seed</label>
                <input
                  id="t_seed"
                  type="number"
                  min={0}
                  max={99999}
                  value={seed}
                  onChange={(e) => setSeed(Number(e.target.value) || 0)}
                />
              </div>
            </>
          )}
        </div>
      </div>

      <div className="toolbar">
        <button onClick={start} disabled={running || !datasetName || !modelName}>
          {running ? "Submitting…" : "Start training"}
        </button>
        {runId ? <span className="pill">run: {runId.slice(0, 12)}</span> : null}
      </div>

      {metrics ? (
        <div className="card">
          <h3>Live status</h3>
          <div className="kpi-row">
            <div
              className={
                metrics.status === "error"
                  ? "kpi err"
                  : metrics.status === "success"
                  ? "kpi ok"
                  : "kpi"
              }
            >
              <div className="label">Status</div>
              <div className="value">{metrics.status}</div>
            </div>
            {metrics.metadata.epochs ? (
              <div className="kpi">
                <div className="label">Epochs</div>
                <div className="value">
                  {String(metrics.metadata.epochs ?? "")}
                </div>
              </div>
            ) : null}
            {metrics.metadata.dataset ? (
              <div className="kpi">
                <div className="label">Dataset</div>
                <div className="value">
                  {String(metrics.metadata.dataset ?? "")}
                </div>
              </div>
            ) : null}
            {metrics.metadata.model ? (
              <div className="kpi">
                <div className="label">Model</div>
                <div className="value">
                  {String(metrics.metadata.model ?? "")}
                </div>
              </div>
            ) : null}
          </div>
          {metrics.error ? (
            <div className="banner-err">{metrics.error}</div>
          ) : null}
          {metrics.status === "error" ? (
            <p className="lede">
              Training requires the <code>[train]</code> extra. Run{" "}
              <code>uv sync --extra train</code> on the API host and retry.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
