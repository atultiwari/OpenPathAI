# Colab export + manifest sync (Phase 11)

Phase 11 closes the reproducibility loop for users on non-local compute:
any pipeline you can run locally can also be run on Google Colab (or
any Jupyter-compatible runtime), and the resulting run manifest can be
pulled back into the local audit DB so the **Runs** tab in the GUI lists
the Colab run alongside your local runs.

Two commands implement the round-trip:

| Direction | Command | Output |
|---|---|---|
| Local → Colab | `openpathai export-colab --pipeline PATH --out run.ipynb` | A self-contained `.ipynb` with pinned install + embedded YAML |
| Colab → Local | `openpathai sync manifest.json` | A row in `~/.openpathai/audit.db` |

Neither command touches PHI, executes user code locally, or talks to the
network beyond the OpenPathAI PyPI install the notebook itself performs
inside Colab.

---

## Exporting a pipeline to Colab

```bash
openpathai export-colab \
    --pipeline pipelines/supervised_synthetic.yaml \
    --out /tmp/demo.ipynb
```

The generated notebook has exactly seven cells:

1. **Markdown intro** — pipeline id, graph hash, source run id (if any),
   and the "OpenPathAI is not a medical device" disclaimer.
2. **`%pip install "openpathai==X.Y.Z"`** — pinned to the version that
   generated the notebook. Override with `--openpathai-version`.
3. **Runtime restart** — the Colab convention that picks up the
   freshly-installed wheel.
4. **Pipeline YAML write** — the exact YAML, embedded as a Python string
   literal (no `%%writefile` to avoid magic-command interactions).
5. **`!openpathai run … --no-audit`** — the same CLI you use locally,
   writing the manifest to `/content/run/manifest.json`.
6. **Markdown step 5** — instructions for downloading the manifest and
   running `openpathai sync` on the laptop.
7. **`files.download(...)`** — convenience download helper.

### Embedding source-run lineage

If the notebook is re-running a specific local audit row, pass
`--run-id <id>`. The notebook metadata records
`metadata.openpathai.source_run_id`, the intro cell mentions the run,
and the Colab manifest produced by Step 5 will differ only in
`environment.tier` (`colab` vs `local`).

```bash
openpathai export-colab \
    --pipeline pipelines/supervised_synthetic.yaml \
    --run-id run-abcdef012345 \
    --out /tmp/demo.ipynb
```

Because the local audit DB stores the pipeline **graph hash** but not
the YAML itself, `--run-id` alone is not enough — the CLI rejects
`--run-id` without `--pipeline` with a clear diagnostic.

### Version pinning

The install cell pins to the currently-installed `openpathai` version
by default. For pre-releases (no wheel on PyPI yet) the cell comment
shows the `git+https://…@<tag>` install form you can uncomment. Use
`--openpathai-version X.Y.Z` to override.

---

## Importing a Colab manifest

Once the Colab notebook finishes, Step 7 downloads `manifest.json`. On
your laptop:

```bash
# Dry-run: show what would be inserted.
openpathai sync ~/Downloads/manifest.json --show

# Commit: insert into ~/.openpathai/audit.db.
openpathai sync ~/Downloads/manifest.json
```

The importer:

* Validates the manifest as JSON and checks for required fields
  (`run_id`, `pipeline_id`, `pipeline_graph_hash`, `timestamp_start`).
* Preserves the manifest's original `run_id` — so `openpathai diff
  <local-run-id> <colab-run-id>` works out of the box.
* Is **idempotent** — re-importing the same manifest leaves the
  existing row untouched and logs a warning.
* Stores `environment.tier` (`colab`, `runpod`, …) on the audit row so
  you can filter by execution location in the Runs tab.

### What `sync` does *not* do

* It never fetches the manifest from a URL — the user is in charge of
  getting the file onto their machine.
* It never writes the pipeline YAML back to disk (we only store the
  graph hash in the audit DB — see Phase 8 master-plan §17).
* It never executes the manifest — re-running the pipeline is an
  explicit `openpathai run` step.

---

## GUI: "Export a run for Colab" accordion

The **Runs** tab in the Gradio GUI has an accordion (Phase 11 addition)
that wraps the same `render_notebook` helper:

1. Paste a run id from the Runs table (optional — only required for
   lineage).
2. Paste the pipeline YAML path the run was produced from.
3. Click **Export for Colab** — the notebook lands in
   `~/.openpathai/exports/<run_id>.ipynb` and the file is offered for
   download via the Gradio file component.

The same `--run-id without --pipeline` rejection applies: the GUI will
print the diagnostic rather than silently falling back.

---

## Reproducibility guarantees

| Guarantee | How it's enforced |
|---|---|
| Notebook installs the exact version that generated it | `openpathai_version` baked into cell 2 + `metadata.openpathai.pip_spec` |
| Pipeline YAML in the notebook matches the local run | YAML embedded as a Python string literal, graph hash pinned in metadata |
| Round-trip preserves `run_id` | `import_manifest` reuses the manifest's `run_id` verbatim |
| Manifest re-import is idempotent | `AuditDB.get_run` short-circuit + warning log |
| Notebook metadata records the generator | `metadata.openpathai.generator = "openpathai.export.colab.render_notebook"` |

---

## Troubleshooting

**"No audit run with id …"** — the `--run-id` you passed is not in the
local audit DB. Run `openpathai audit list` to see available ids, or
drop `--run-id` entirely.

**"--run-id alone is not enough to embed the pipeline YAML"** — the
audit row stores the pipeline **graph hash** (Phase 8 rule), not the
YAML itself. Pass `--pipeline PATH` pointing at the YAML.

**"not a valid JSON RunManifest"** — `manifest.json` is malformed.
Re-export from Colab or run `openpathai sync --show` to see the exact
parser error.

**"Manifest already imported as run …"** — the manifest has been
synced before. This is a warning, not an error; the existing row is
left untouched.
