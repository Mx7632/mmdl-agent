# Runtime Guide

This document records the current runnable path, knowledge-base build path, and
PatchCore heatmap path.

## Can The Project Run Now?

Yes, the current project can run locally if the required Python dependencies and
environment variables are available.

Recommended local smoke mode:

```powershell
conda activate MMDL-Agent
pip install -e .
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/web/index.html
```

Quick health check:

```powershell
curl http://127.0.0.1:8000/health
```

Recommended `.env` for first local run:

```env
APP_OPENAI_API_KEY=your_key
APP_CHECKPOINT_BACKEND=memory
APP_VISION_DETECTOR_BACKEND=qwen
```

Use `memory` checkpoint first. PostgreSQL can be enabled later when durable
multi-turn task recovery is needed.

## Main Runtime Chain

The primary user-facing chain is:

```text
Frontend / API
  -> app/api/main.py
  -> app/services/task_runner.py or app/services/streaming.py
  -> app/core/graph.py
  -> load_data
  -> supervisor_plan
  -> supervisor_execute
      -> VisionAgent
      -> KnowledgeAgent
      -> ClarificationAgent when needed
      -> ReportAgent when requested
  -> supervisor_merge
      -> shared_context.vision
      -> shared_context.knowledge
      -> shared_context.mmad_analysis
      -> metadata.analysis_contracts
      -> metadata.mmad_analysis
  -> self_reflect or wait_user
  -> answer
  -> optional report
```

For real-time debugging, prefer:

```text
POST /v1/stream
```

The frontend timeline reads:

- `metadata.execution_plan`
- `metadata.step_status`
- `metadata.step_attempts`
- `metadata.execution_events`
- `metadata.analysis_contracts`
- `metadata.mmad_analysis`

## How To Build The Knowledge Base

The RAG knowledge base is built from an MVTec-style dataset directory. The
default vector store writes to:

```text
data/rag/chroma
```

Synchronous build:

```powershell
curl -X POST http://127.0.0.1:8000/v1/rag/build `
  -H "Content-Type: application/json" `
  -d "{\"dataset_root\":\"data_sets/mvtec_anomaly_detection\",\"include_normal\":false}"
```

Asynchronous build:

```powershell
curl -X POST http://127.0.0.1:8000/v1/rag/build/start `
  -H "Content-Type: application/json" `
  -d "{\"dataset_root\":\"data_sets/mvtec_anomaly_detection\",\"include_normal\":false}"
```

Then poll:

```text
GET /v1/rag/build/status/{task_id}
```

Query by text:

```powershell
curl -X POST http://127.0.0.1:8000/v1/rag/query `
  -H "Content-Type: application/json" `
  -d "{\"query_text\":\"bottle rim crack with jagged edge\",\"category\":\"bottle\",\"top_k\":3}"
```

Query by image path:

```powershell
curl -X POST http://127.0.0.1:8000/v1/rag/query-image `
  -H "Content-Type: application/json" `
  -d "{\"image_path\":\"data_sets/mvtec_anomaly_detection/bottle/test/broken_small/000.png\",\"category\":\"bottle\",\"top_k\":3}"
```

What the builder does:

1. `DatasetAnalyzer` scans category/split/defect metadata.
2. `AnomalyTextGenerator` creates a description for each row.
3. `VectorStore` embeds and stores rows into Chroma.
4. `KnowledgeAgent` retrieves similar cases at runtime.
5. `knowledge_pipeline` turns retrieved rows into:
   - `defect_analysis`
   - `object_analysis`
6. `mmad_pipeline` embeds those outputs into the seven-task MMAD view.

## How MMAD Data Fits In

The MMAD importer does not build the RAG store directly yet. It converts the
official MMAD metadata into project JSONL files for evaluation and future RAG
ingestion.

Example:

```powershell
python scripts\import_mmad_dataset.py `
  --source-root E:\Computer\Projects\30_research\mmad `
  --metadata-file "mmad.json" `
  --output-root data\mmad_sample `
  --dataset DS-MVTec `
  --category bottle `
  --limit 3
```

Outputs:

- `data/mmad_sample/annotations.jsonl`
- `data/mmad_sample/qa.jsonl`

These are ignored by Git because they are generated data artifacts.

## How PatchCore Heatmaps Work

PatchCore is available as a local vision backend. It works in two phases.

### 1. Train One Category

```powershell
python scripts\patchcore_train.py `
  --category bottle `
  --dataset-root data_sets\mvtec_anomaly_detection `
  --model-root models\patchcore `
  --image-size 128 `
  --device cpu `
  --max-memory-bank 2000
```

This writes:

```text
models/patchcore/{category}/memory_bank.pt
models/patchcore/{category}/metadata.json
```

### 2. Run One Image

```powershell
python scripts\patchcore_eval.py `
  --image data_sets\mvtec_anomaly_detection\bottle\test\broken_small\000.png `
  --category bottle `
  --task-id patchcore-bottle-demo `
  --threshold 0.5
```

This produces:

```text
data/heatmaps/{category}/{task_id}_heatmap.png
data/heatmaps/{category}/{task_id}_overlay.png
data/heatmaps/{category}/{task_id}_mask.png
```

The API mounts these files at:

```text
/data/heatmaps
```

At runtime:

1. Frontend selects PatchCore or request parameters set `tool_type=patchcore`.
2. `ImageAnomalyDetectionTool` routes to `LocalPatchCoreImageAnomalyDetectionTool`.
3. PatchCore compares image patch embeddings against the category memory bank.
4. Distances are converted to an anomaly score map.
5. The score map is normalized and resized into a heatmap.
6. Connected components above the threshold become anomaly regions.
7. The result returns:
   - `anomalies`
   - `bbox`
   - `location`
   - `appearance`
   - `severity_hint`
   - `heatmap_path`
   - `overlay_path`
   - `mask_path`
8. The frontend can switch between original, bbox, heatmap, and overlay views.
9. `mmad_analysis.defect_localization` records whether heatmap/mask evidence is available.

## Recommended End-To-End Debug Order

1. Start backend and open frontend.
2. Run `/health`.
3. Build RAG from MVTec with `include_normal=false`.
4. Train PatchCore for one category, usually `bottle`.
5. Run `patchcore_eval.py` once to verify heatmap files are generated.
6. In the frontend, select PatchCore and the same category.
7. Upload an image and start detection.
8. Watch the multi-agent timeline and final metadata:
   - `selected_backend=patchcore`
   - `heatmap_path`
   - `analysis_contracts`
   - `mmad_analysis`

## Current Caveats

- `README.md` currently contains mojibake in parts of the Chinese text. Prefer
  this guide and `Docs/architecture.md` until README is cleaned.
- `data/rag/chroma/chroma.sqlite3` is a local runtime artifact and should not be
  committed.
- PatchCore requires the category model to be trained before it can be selected
  successfully at runtime.
- MMAD import is available, but direct MMAD-to-RAG ingestion is the next step.
