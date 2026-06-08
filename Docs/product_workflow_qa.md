# Product Workflow QA

This checklist records the Phase 2 product-closure verification path for
MMDL-Agent.

## Verified On 2026-06-08

Backend short-run health check:

```powershell
APP_CHECKPOINT_BACKEND=memory
APP_REQUIRE_API_TOKEN=false
python -m uvicorn main:app --host 127.0.0.1 --port 8000
GET http://127.0.0.1:8000/v1/system/health
```

Observed result:

- API status: `ok`
- RAG vector directory: `data/rag/chroma`, status `ok`
- Checkpoint backend: `memory`
- PatchCore status: `not_trained`
- GRAD sidecar: `not_configured`
- AnomalyGPT/professional sidecar: `not_configured`
- API token required: `false`

Frontend static workspace check:

```text
GET http://127.0.0.1:8000/web/index.html
```

Observed result:

- Status code: `200`
- Content type: `text/html; charset=utf-8`
- Page title marker: `<title>MMDL-Agent</title>`

Interpretation:

- The backend application can start.
- The frontend workspace is correctly mounted by the backend.
- The health endpoint is suitable as the frontend/system status source.
- This local environment is not ready for a real visual detection demo until at
  least one detector backend is available.

## Manual Frontend QA Checklist

Use this checklist after the backend is running:

1. Open `http://127.0.0.1:8000/web/index.html`.
2. Confirm the backend status indicator becomes online.
3. Upload a small industrial image and confirm preview rendering.
4. Select a detector backend that is actually configured:
   - `qwen` requires `APP_OPENAI_API_KEY`;
   - `patchcore` requires a trained category under `models/patchcore`;
   - `grad` requires a reachable GRAD sidecar or local checkpoint;
   - `anomalygpt` requires a configured professional detector URL.
5. Start detection.
6. Confirm the execution timeline shows planned/running/completed or failed
   agent steps.
7. Confirm visual output renders original image and any available bbox,
   heatmap, overlay, or mask.
8. Ask one follow-up question after a successful detection.
9. Generate a report after a successful detection.
10. Refresh task history and confirm the task appears.
11. If a low-confidence anomaly is returned, confirm it appears in the review
    queue.

## Current Blocker For Full Detection QA

The local health check shows no ready visual backend. Full image detection QA
should continue after one of these is true:

- `APP_OPENAI_API_KEY` is configured for Qwen vision;
- PatchCore has at least one trained category;
- GRAD sidecar is running and `APP_GRAD_DETECTOR_URL` is configured;
- a professional detector sidecar is configured.

Until then, use mock-based integration tests for API contracts and timeline
payloads, and use `/v1/system/health` to surface the missing detector readiness
in the frontend.
