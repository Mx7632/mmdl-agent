# Runtime Guide

This document records the current runnable path, knowledge-base build path,
few-shot RAG path, and PatchCore heatmap path.

## Current Recommended Path

For day-to-day local debugging, use this order:

```text
1. Start backend with memory checkpoint
2. Open frontend workspace
3. Build RAG from MVTec with normal and anomaly samples
4. Train one PatchCore category, usually bottle
5. Run one PatchCore CLI smoke test
6. Use the frontend stream workflow to run detection
7. Inspect timeline, heatmap files, MMAD metadata, and few-shot metadata
```

The most useful frontend entry is:

```text
http://127.0.0.1:8000/web/index.html
```

The most useful debugging API is:

```text
POST /v1/stream
```

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

Recommended `.env` when testing PatchCore:

```env
APP_CHECKPOINT_BACKEND=memory
APP_VISION_DETECTOR_BACKEND=patchcore
APP_PATCHCORE_MODEL_ROOT=models/patchcore
APP_PATCHCORE_OUTPUT_ROOT=data/heatmaps
```

Recommended `.env` when testing RAG and few-shot:

```env
APP_RAG_VECTOR_DIR=data/rag/chroma
APP_RAG_MULTIMODAL_EMBEDDING_MODEL=multimodal-embedding-v1
APP_RAG_TOP_K=3
```

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
- `metadata.few_shot`

Key runtime outputs:

- Vision output is merged into `shared_context.vision`.
- Knowledge output is merged into `shared_context.knowledge`.
- MMAD seven-task analysis is exposed as `metadata.mmad_analysis`.
- Few-shot normal/anomaly selections are exposed as `metadata.few_shot`.
- PatchCore heatmap, overlay, and mask URLs are exposed from result metadata.

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
  -d "{\"dataset_root\":\"data_sets/mvtec_anomaly_detection\",\"include_normal\":true}"
```

Asynchronous build:

```powershell
curl -X POST http://127.0.0.1:8000/v1/rag/build/start `
  -H "Content-Type: application/json" `
  -d "{\"dataset_root\":\"data_sets/mvtec_anomaly_detection\",\"include_normal\":true}"
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
5. `FewShotSelector` selects balanced normal/anomaly examples.
6. `FewShotPromptBuilder` builds a compact few-shot context block.
7. `knowledge_pipeline` turns retrieved rows and few-shot context into:
   - `defect_analysis`
   - `object_analysis`
8. `mmad_pipeline` embeds those outputs into the seven-task MMAD view.

Use `include_normal=true` for the current main path. The few-shot selector needs
both normal and abnormal examples so VisionAgent and KnowledgeAgent can calibrate
against reference cases.

The active KnowledgeAgent path is:

```text
KnowledgeAgent
  -> RAG similar-case retrieval
  -> FewShotSelector normal/anomaly selection
  -> FewShotPromptBuilder few-shot context
  -> knowledge_pipeline defect/object analysis
```

The active VisionAgent few-shot path is:

```text
Supervisor step executor
  -> RAG similar-case retrieval
  -> FewShotSelector normal/anomaly selection
  -> FewShotPromptBuilder few-shot context
  -> VisionAgent
  -> ImageAnomalyDetectionTool prompt / metadata
```

Few-shot metadata appears in the final stream payload:

```text
metadata.few_shot.vision
metadata.few_shot.vision_context
metadata.few_shot.knowledge
metadata.few_shot.knowledge_context
```

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

### AutoDL Training Record For Bottle

The first AutoDL validation used an RTX 5090 instance. The existing PyTorch
installation did not support `sm_120`, so CUDA training failed with:

```text
RuntimeError: CUDA error: no kernel image is available for execution on the device
```

The working fallback was CPU training. The first lightweight run succeeded but
used `pretrained_backbone=false`, which produced unstable heatmaps and false
positives on normal samples. The useful training run was:

```bash
python scripts/patchcore_train.py \
  --category bottle \
  --dataset-root /root/autodl-tmp/mmdl-agent/data_sets/mvtec_anomaly_detection \
  --model-root /root/autodl-tmp/models/patchcore \
  --image-size 256 \
  --device cpu \
  --backbone resnet18 \
  --max-memory-bank 10000 \
  --pretrained-backbone
```

Returned metadata:

```json
{
  "category": "bottle",
  "dataset_root": "/root/autodl-tmp/mmdl-agent/data_sets/mvtec_anomaly_detection",
  "image_size": 256,
  "backbone": "resnet18",
  "pretrained_backbone": true,
  "device": "cpu",
  "memory_bank_size": 10000,
  "feature_dim": 384,
  "recommended_threshold": 5.2034941800961345
}
```

Important notes:

- The server dataset root was
  `/root/autodl-tmp/mmdl-agent/data_sets/mvtec_anomaly_detection`.
- Training output was written to `/root/autodl-tmp/models/patchcore`.
- CLI eval currently reads `APP_PATCHCORE_MODEL_ROOT`; set it when model output
  is outside the project directory.
- `--pretrained-backbone` is required for usable heatmap quality.
- `threshold=0.8` detected the abnormal `broken_small/000.png` as one local
  region, but still produced small false positives on `test/good/000.png`.
- Next threshold candidates are `0.9` and `0.95`.
- Current implementation normalizes every heatmap before scoring, so
  `confidence=1.0` can appear even on normal images. Future code should separate
  raw image-level score from normalized visualization score.

Useful eval commands:

```bash
APP_PATCHCORE_MODEL_ROOT=/root/autodl-tmp/models/patchcore \
python scripts/patchcore_eval.py \
  --image /root/autodl-tmp/mmdl-agent/data_sets/mvtec_anomaly_detection/bottle/test/broken_small/000.png \
  --category bottle \
  --task-id patchcore-bottle-bad-pretrained-t08 \
  --threshold 0.8
```

```bash
APP_PATCHCORE_MODEL_ROOT=/root/autodl-tmp/models/patchcore \
python scripts/patchcore_eval.py \
  --image /root/autodl-tmp/mmdl-agent/data_sets/mvtec_anomaly_detection/bottle/test/good/000.png \
  --category bottle \
  --task-id patchcore-bottle-good-pretrained-t09 \
  --threshold 0.9
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

Frontend usage:

1. Open `http://127.0.0.1:8000/web/index.html`.
2. Upload an image from the same category that has a trained PatchCore memory bank.
3. Select PatchCore in the detector control, or set request parameter `tool_type=patchcore`.
4. Set the category, for example `bottle`.
5. Start detection and watch the multi-agent timeline.
6. Check the visual panel for original, bbox, heatmap, overlay, and mask views.

If PatchCore fails, do not treat the result as normal. The expected behavior is:

- Vision step status becomes failed.
- `answer` explains that the visual analysis failed.
- `mmad_analysis.anomaly_discrimination.status` stays unknown or failed.
- The frontend timeline should show the failed specialist step.

## Recommended End-To-End Debug Order

1. Start backend and open frontend.
2. Run `/health`.
3. Build RAG from MVTec with `include_normal=true`.
4. Train PatchCore for one category, usually `bottle`.
5. Run `patchcore_eval.py` once to verify heatmap files are generated.
6. In the frontend, select PatchCore and the same category.
7. Upload an image and start detection.
8. Watch the multi-agent timeline and final metadata:
   - `selected_backend=patchcore`
   - `heatmap_path`
   - `analysis_contracts`
   - `mmad_analysis`
   - `few_shot`

## Common Troubleshooting Checks

Backend starts but frontend cannot call APIs:

- Confirm backend is running on `http://127.0.0.1:8000`.
- Open `http://127.0.0.1:8000/health`.
- Open the frontend through `/web/index.html` to avoid cross-origin surprises.

RAG returns no useful few-shot examples:

- Rebuild with `include_normal=true`.
- Confirm dataset path points to the real MVTec root.
- Query `/v1/rag/query` with a category that exists in the dataset.
- Check `data/rag/chroma` exists after build.

PatchCore produces no heatmap:

- Confirm `models/patchcore/{category}/memory_bank.pt` exists.
- Confirm request category matches the trained category.
- Run `scripts/patchcore_eval.py` directly before testing through the frontend.
- Check `data/heatmaps/{category}` for generated files.

Follow-up questions repeat the original answer:

- Use `/v1/stream` or `/v1/chat` with the same `task_id`.
- Confirm checkpoint backend is `memory` in the same backend process, or use PostgreSQL for durable recovery.
- Inspect `metadata.agent_trace` and `metadata.execution_events` to see whether KnowledgeAgent or ClarificationAgent ran again.

## Focused Test Commands

Core multi-agent and few-shot loop:

```powershell
pytest tests\test_phase1_multi_agent.py -q
```

MMAD importer:

```powershell
pytest tests\test_mmad_importer.py -q
```

Recommended focused regression before committing runtime changes:

```powershell
pytest tests\test_phase1_multi_agent.py tests\test_mmad_importer.py -q
```

## Current Caveats

- `README.md` currently contains mojibake in parts of the Chinese text. Prefer
  this guide and `Docs/architecture.md` until README is cleaned.
- `data/rag/chroma/chroma.sqlite3` is a local runtime artifact and should not be
  committed.
- PatchCore requires the category model to be trained before it can be selected
  successfully at runtime.
- MMAD import is available, but direct MMAD-to-RAG ingestion is the next step.
