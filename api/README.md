# OpenTune Knowledge API

Self-hosted REST API for the OpenTune diagnostic procedure knowledge base.
Semantic search powered by `sentence-transformers` (all-MiniLM-L6-v2).
SQLite backend — no external services required.

## Setup

```bash
pip install fastapi uvicorn sentence-transformers numpy
```

## Seed the knowledge base

```bash
python -m api.seed
```

Reads all JSON files from `knowledge/` recursively, parses them into the
procedure schema, and generates semantic embeddings stored in `opentune_kb.db`.

## Run the server

```bash
uvicorn api.main:app --reload --port 8765
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status, procedure count, version |
| GET | `/search?q=&make=&system=&limit=10` | Semantic search with optional filters |
| GET | `/procedure/{id}` | Full procedure detail |
| GET | `/browse?make=&system=&limit=50` | Filtered list (no semantic ranking) |
| POST | `/submit` | Submit a new community procedure |
| POST | `/verify/{id}` | Confirm a procedure worked on a vehicle |
| GET | `/stats` | Totals, top makes, top systems |

## Self-host philosophy

All data stays local. No cloud calls for search or storage.
The embedding model downloads once (~23 MB) and runs entirely offline.
Community submissions go into the same local SQLite file.
