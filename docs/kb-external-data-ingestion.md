# KB External Data Ingestion

This project now supports external KB seed files as first-class inputs.

## What changed

- `core/retrieval/normalized_docs.py` now loads **all JSON files** under:
  - `seed_data/faq/*.json`
  - `seed_data/sop/*.json`
  - `seed_data/historical_cases/*.json`
- KB records now preserve and expose:
  - `updated_at`
  - `metadata` (e.g. `source_dataset`, `license`, `source_url`, `commercial_use`)

## Import script

Use:

```bash
python -m scripts.import_external_kb_seed \
  --include-project-sop \
  --use-bootstrap-samples \
  --write-manifest
```

Optional real dataset inputs:

```bash
python -m scripts.import_external_kb_seed \
  --faq-json /path/train_expanded.json \
  --history-csv /path/customer-support-tickets.csv \
  --uci-events-csv /path/uci_incident_events.csv \
  --mendeley-issues-csv /path/issues.csv \
  --mendeley-history-csv /path/issues_change_history.csv \
  --include-project-sop \
  --write-manifest
```

## Output files

- `seed_data/faq/faq_external_documents.json`
- `seed_data/historical_cases/history_external_documents.json`
- `seed_data/sop/sop_project_documents.json`
- `seed_data/external_sources_manifest.json` (optional)

## Governance notes

- FAQ (`MakTek`) metadata marks `Apache-2.0` and `commercial_use=true`.
- Ticket cases (`Tobi-Bueck`) metadata marks `CC-BY-NC-4.0` and `commercial_use=false`.
- Process logs (`UCI`/`Mendeley`) metadata marks `CC BY 4.0` and `commercial_use=true`.
- Import script applies basic PII redaction (`email`, `phone`, common ticket-like IDs) before writing seed docs.
