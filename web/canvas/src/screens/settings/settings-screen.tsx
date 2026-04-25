import { useEffect, useState } from "react";
import { useAuth } from "../../api/auth-context";
import { safeMessage } from "../../lib/safe-string";
import { TabGuide } from "../../components/tab-guide";

export function SettingsScreen() {
  const { baseUrl, setBaseUrl, token, setToken, client } = useAuth();
  const [draftBase, setDraftBase] = useState(baseUrl);
  const [version, setVersion] = useState<{
    openpathai_version: string;
    api_version: string;
    commit: string | null;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    client
      .version()
      .then((v) => {
        if (!cancelled) setVersion(v);
      })
      .catch((err) => {
        if (!cancelled) setError(safeMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  return (
    <section className="task-content">
      <TabGuide tab="settings" />
      <h2>Settings</h2>
      <p className="lede">
        Per-tab settings. The bearer token lives in this tab's session
        storage only — closing the tab clears it.
      </p>

      {error ? <div className="banner-err">{error}</div> : null}

      <div className="card">
        <h3>API connection</h3>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="s_base">Base URL</label>
            <input
              id="s_base"
              value={draftBase}
              onChange={(e) => setDraftBase(e.target.value)}
            />
          </div>
          <div className="field">
            <label>Token (last 8 chars)</label>
            <code>{token ? `…${token.slice(-8)}` : "—"}</code>
          </div>
        </div>
        <div className="toolbar" style={{ marginTop: 12 }}>
          <button onClick={() => setBaseUrl(draftBase)}>Save base URL</button>
          <button onClick={() => setToken(null)}>Sign out</button>
        </div>
      </div>

      <div className="card">
        <h3>Server version</h3>
        {version ? (
          <table className="panel-table">
            <tbody>
              <tr>
                <th>OpenPathAI</th>
                <td>{version.openpathai_version}</td>
              </tr>
              <tr>
                <th>API</th>
                <td>{version.api_version}</td>
              </tr>
              <tr>
                <th>Commit</th>
                <td>{version.commit ?? "—"}</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p>Loading…</p>
        )}
      </div>
    </section>
  );
}
