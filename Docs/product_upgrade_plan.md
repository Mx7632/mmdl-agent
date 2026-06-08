# Product Upgrade Plan

This document tracks the upgrade from a graduation-project prototype to a
product-like industrial anomaly detection workspace.

## Product Positioning

MMDL-Agent should become a runnable industrial visual inspection assistant:

```text
image upload
  -> anomaly detection and localization
  -> multi-agent diagnosis
  -> RAG-enhanced explanation
  -> report generation
  -> task history, review, and follow-up conversation
```

The near-term product target is not a large SaaS system. The priority is a
stable, explainable, locally demonstrable product prototype with clear APIs,
traceable runtime state, and a polished frontend workflow.

## Current Capability Baseline

The project already has these product-building blocks:

- FastAPI backend in `app/api/main.py`.
- Static frontend workspace in `web/index.html`.
- Detection, streaming, chat, continuation, and report service layer in
  `app/services/`.
- LangGraph-based multi-agent workflow under `app/core/`, `app/agents/`, and
  `app/orchestration/`.
- Vision backends routed through `app/tools/image_anomaly_detection.py`.
- RAG build/query/feedback endpoints under `/v1/rag/*`.
- Task history, batch detection, review queue, runtime metrics, and session
  persistence in `app/services/industrial_runtime.py`.
- Focused tests for the industrial pilot flow and image anomaly router.

## Upgrade Order

### Phase 1: Architecture And Baseline Stabilization

Goal: make the existing runnable path easier to trust before adding new
features.

Completed in the first pass:

- Verified focused tests:
  - `tests/test_industrial_pilot.py`
  - `tests/test_image_anomaly_detection_router.py`
- Removed severe Ruff issues from app/test code:
  - fixed the unresolved `SupervisorAgent` type reference in
    `app/agents/factory.py`;
  - converted legacy core node files to valid UTF-8;
  - removed unused imports and variables from affected modules/tests.

Completed in the second pass:

- Verified the backend can start and return `/v1/system/health`.
- Added an integration test for the product runtime health contract.
- Added a manual product workflow QA checklist with detector-readiness notes.

Next recommended checks:

- Verify one frontend detection workflow through `/web/index.html`.
- Run a broader test subset around streaming and graph runtime.

### Phase 2: Main Workflow Product Closure

Goal: make the first-screen workflow reliable:

```text
upload image -> stream detection -> show timeline -> show heatmap/result
-> ask follow-up -> generate report -> save/restore session
```

Recommended tasks:

- Confirm frontend uses `/v1/stream` as the default primary workflow.
- Add a short manual QA checklist for upload, timeline, result, report, and
  failure states.
- Make `/v1/system/health` the frontend system health source, because it exposes
  detector/RAG/security component status.
- Ensure failed vision backends are displayed as failed analysis instead of
  being interpreted as normal samples.

### Phase 3: Structured Product Contracts

Goal: reduce fragile ad hoc payload handling.

Started:

- Added Pydantic runtime schemas for health, metrics, task list, and pending
  review list responses.
- Bound `/v1/system/health`, `/v1/metrics`, `/v1/tasks`, and
  `/v1/reviews/pending` to response models without changing their JSON field
  names.
- Added Pydantic runtime schemas for task detail, task deletion, task review,
  batch detection, batch report, and RAG feedback review responses.
- Added product analysis/report response schemas for `/v1/generate_report` and
  `/v1/detect_with_report`.
- Added a structured RAG source metadata schema for `/v1/rag/query` and
  `/v1/rag/query-image`, while preserving extension fields for future dataset
  provenance.
- Added OpenAPI regression coverage for health, task detail, and batch report
  response schemas, report-facing response schemas, and RAG source metadata.

Recommended tasks:

- Add or refine Pydantic response schemas for:
  - task history rows;
  - industrial normalized result;
  - execution timeline events;
  - review queue items;
  - RAG source items;
  - report responses.
- Keep response shape backward compatible with the frontend.
- Document any new schema in `Docs/`.

### Phase 4: Frontend Workbench Polish

Goal: turn the frontend into a clear inspection workbench.

Recommended tasks:

- Keep the first screen focused on upload, detector settings, preview, result,
  timeline, RAG, and report.
- Improve empty, loading, failed, pending, and completed states.
- Keep task history and review actions visible but secondary.
- Verify layout at desktop and mobile widths after changes.

### Phase 5: Test And Demo Hardening

Goal: make the product demo repeatable.

Recommended tasks:

- Move focused tests into the target directory structure from `AGENTS.md`
  over time:
  - `tests/unit/`
  - `tests/integration/`
  - `tests/rag/`
  - `tests/fixtures/`
- Add a smoke test for `/v1/system/health`.
- Add a mock-based streaming test for timeline payload shape.
- Add a manual frontend verification record after UI changes.

## Immediate Next Work Item

The next best implementation step is Phase 2:

1. Start the backend locally.
2. Verify `/v1/system/health`.
3. Open `/web/index.html`.
4. Run one image detection with the default configured backend.
5. Record any frontend/runtime breakage before adding new features.

This keeps the product upgrade grounded in the actual runnable path.
