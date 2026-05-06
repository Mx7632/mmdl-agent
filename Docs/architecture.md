# Architecture Overview

This project uses a supervisor-based multi-agent workflow for industrial anomaly
detection. The active runtime path is:

`API -> services -> graph/core -> orchestration -> specialist agents -> memory`

## Active Layers

- `app/api`
  - FastAPI endpoints, request parsing, HTTP/SSE responses.
- `app/services`
  - Task execution entrypoints (`detect`, `chat`, `continue`, `report`) and
    streaming adapters.
- `app/core`
  - Graph definition and compatibility facades for stable import paths.
- `app/orchestration`
  - Execution-plan runtime, step execution, merge adapters, and runtime events.
- `app/agents`
  - Specialist agents: `vision`, `knowledge`, `clarification`, `report`,
    plus the `supervisor` planner.
- `app/memory`
  - Durable task state, checkpoint helpers, and state models.
- `app/storage`
  - Persistence-facing abstractions.
- `web`
  - Frontend workspace with timeline observability for the multi-agent runtime.

## Active Graph

The active LangGraph flow is defined in
[`app/core/graph.py`](/E:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/app/core/graph.py):

1. `load_data`
2. `supervisor_plan`
3. `supervisor_execute`
4. `supervisor_merge`
5. `self_reflect` or `wait_user`
6. `answer`
7. optional `report`

The graph uses a structured execution plan with:

- `execution_plan`
- `step_status`
- `step_attempts`
- `step_outputs`
- `execution_events`

The current full runtime chain is:

```text
web/index.html or HTTP client
  -> app/api/main.py
  -> app/services/task_runner.py or app/services/streaming.py
  -> app/core/graph.py
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

Operational startup, RAG build, MMAD import, and PatchCore heatmap instructions
are documented in
[`Docs/runtime_guide.md`](/E:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/Docs/runtime_guide.md).

## Runtime Entry Points

The active task runtime lives in `app/services`:

- [`app/services/task_runner.py`](/E:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/app/services/task_runner.py)
  - `run_detection`
  - `run_chat`
  - `continue_detection`
  - `generate_report`
- [`app/services/streaming.py`](/E:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/app/services/streaming.py)
  - `stream_detection`
  - `stream_continue_detection`
  - SSE event shaping and final payload assembly
- [`app/services/state_rehydration.py`](/E:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/app/services/state_rehydration.py)
  - checkpoint restoration
  - follow-up turn reset
  - metadata extraction helpers

`app/core/agent.py` remains as a compatibility facade so older imports do not
break while the runtime structure is being cleaned up.

## Orchestration Contracts

The typed business context lives in
[`app/orchestration/context.py`](/E:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/app/orchestration/context.py)
and is the preferred place for shared domain outputs:

- `vision`
- `knowledge`
- `clarification`
- `report`

The long-term goal is for `shared_context` to hold core business context, while
the generic `context` dict becomes a compatibility/debug layer.

`knowledge` is now split into two typed analysis contracts:

- `defect_analysis`
  - similar cases
  - possible causes
  - risk notes
  - repair actions
  - analysis summary
- `object_analysis`
  - object profile
  - component scope
  - component findings
  - functional impact
  - object knowledge hits and summary

The flat knowledge fields (`possible_causes`, `component_scope`, and similar)
are compatibility mirrors. Active code should consume the nested contracts
first. `app/rag/knowledge_pipeline.py` coordinates the defect and object
analysis pipelines before `KnowledgeAgent` emits a unified `KnowledgeContext`.
Execution metadata also exposes these contracts under `analysis_contracts` so
SSE snapshots, final results, and frontend analysis panels share the same
shape.

The workflow also emits an MMAD-aligned seven-task analysis contract under
`shared_context.mmad_analysis` and `metadata.mmad_analysis`. It normalizes the
current vision and knowledge outputs into:

- `anomaly_discrimination`
- `defect_classification`
- `defect_localization`
- `defect_description`
- `defect_analysis`
- `object_classification`
- `object_analysis`

This contract is generated after specialist outputs are merged. It is intended
as the stable bridge between application results and MMAD-style evaluation or
annotation pipelines. Existing `defect_analysis` and `object_analysis`
contracts remain the source of deeper knowledge reasoning and are embedded in
the seven-task view.

## State Grouping

[`app/memory/state.py`](/E:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/app/memory/state.py)
still keeps `DetectionState` as the persisted top-level state, but it now also
exposes grouped runtime views:

- `task_runtime()`
  - task input, conversation, user reply, report/stage fields
- `orchestration_runtime()`
  - execution plan, retries, step status, events, suspend/proceed control
- `domain_runtime()`
  - shared context, result, tool outputs, agent outputs

These views are intended as the migration path toward a cleaner state model
without breaking the current serialized checkpoint shape.

At this point, the active workflow path already prefers grouped runtime access
in its main readers and writers:

- graph routing
- supervisor planning and execution
- wait/resume flow
- self reflection
- answer generation
- report generation
- follow-up state rehydration

Direct top-level field access still exists as a compatibility layer for
checkpoint shape stability and for legacy modules, but it is no longer the
preferred extension path for active workflow code.

## Legacy Modules

The following modules are retained only as legacy reference and are not part of
the active supervisor-based graph:

- `app/core/planner.py`
- `app/core/executor.py`
- `app/core/consolidate.py`
- `app/core/supplement.py`

They should not be used when extending the current multi-agent workflow unless
the project explicitly decides to revive the older orchestration model.
