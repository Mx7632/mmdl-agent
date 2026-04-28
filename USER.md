# USER

## 维护规则

- 每完成一个可独立验收的模块、阶段或重要修复后，立即追加一条记录到本文档。
- 每条记录至少包含：日期、模块名称、完成内容、影响范围、验证结果。
- 提交 Git 前，先检查本文档是否已同步更新；如未更新，先补齐记录再提交。
- 运行时产物、临时调试结论不记为正式模块记录；只记录可复现、可交付的开发结果。

## 开发记录

### 2026-04-26 | PostgreSQL durable state 与 checkpoint 持久化

- 完成内容：
  - 新增 `app/storage/postgres.py`，封装 PostgreSQL 运行时状态存取。
  - 新增 `app/core/runtime.py`，统一管理 LangGraph checkpoint backend 与线程态加载。
  - 扩展 `app/memory/checkpoint.py`、`app/config/settings.py`、`pyproject.toml`，支持 PostgreSQL 持久化配置与依赖。
  - 打通 graph state 加载、checkpoint 持久化与应用级 runtime state 镜像写入逻辑。
- 影响范围：
  - `app/core/agent.py`
  - `app/core/graph.py`
  - `app/memory/checkpoint.py`
  - `app/storage/postgres.py`
  - `app/core/runtime.py`
- 验证结果：
  - `tests/test_checkpoint_store.py`
  - `tests/test_graph_runtime.py`

### 2026-04-26 | 图像检测路由与专业模型接入

- 完成内容：
  - 扩展 `app/tools/image_anomaly_detection.py`，支持通用视觉模型与专业异常检测后端路由。
  - 增加专业模型服务配置项，允许通过项目配置切换 `qwen` 与 `anomalygpt`。
  - 补充异常区域定位结果结构，统一输出异常列表与定位信息。
- 影响范围：
  - `app/tools/image_anomaly_detection.py`
  - `app/core/tools.py`
  - `app/api/main.py`
  - `app/config/settings.py`
- 验证结果：
  - 图像检测请求与定位返回结构通过主链路测试。

### 2026-04-26 | 本地 AnomalyGPT sidecar 与 Docker 侧车

- 完成内容：
  - 新增 `services/anomalygpt_local/` 本地服务骨架。
  - 提供 `Dockerfile`、`docker-compose.yml`、`start_service.ps1` 与服务说明文档。
  - 支持项目侧通过 HTTP 调用本地部署的专业异常检测服务。
- 影响范围：
  - `services/anomalygpt_local/`
  - `README.md`
  - `app/config/settings.py`
- 验证结果：
  - 服务接线由主链路测试覆盖，配置说明已写入项目文档。

### 2026-04-26 | 前端工作台收敛为单页核心流程

- 完成内容：
  - 将前端收敛为单页核心流程，减少分散页面与重复交互。
  - `web/index.html` 调整为围绕检测、追问、报告生成的主工作流。
  - 保持后端 API 不变，前端仅做交互与展示层简化。
- 影响范围：
  - `web/index.html`
  - `README.md`
- 验证结果：
  - 前端主流程与后端接口联调通过。

### 2026-04-26 | 多 Agent Phase 1：受控监督式架构骨架

- 完成内容：
  - 新增 `supervisor`、`vision`、`knowledge`、`report` 四类 agent 骨架。
  - 新增 `AgentEnvelope` 作为主控与 specialist 间的统一通信契约。
  - 扩展 `DetectionState`，加入 `agent_outputs`、`agent_trace`、`active_agent`、`shared_context`。
  - 重写顶层 graph，将执行流升级为 supervisor 规划、执行、合并的受控流程。
- 影响范围：
  - `app/agents/*`
  - `app/core/graph.py`
  - `app/core/supervisor.py`
  - `app/memory/state.py`
- 验证结果：
  - `tests/test_phase1_multi_agent.py`
  - `tests/test_main_flow_smoke.py`

### 2026-04-26 | 主链路回归验证

- 完成内容：
  - 对 durable state、图像路由、多 Agent Phase 1 与主流程进行回归验证。
- 验证结果：
  - 主流程与多 Agent 相关测试通过。

### 2026-04-26 | 工作记忆文件治理（方案 B）

- 完成内容：
  - 将 `app/data/memory/working_memory.json` 定义为运行时文件，不再纳入 Git 跟踪。
  - 新增 `app/data/memory/working_memory.example.json` 作为可提交的结构样例。
  - 在 `.gitignore` 与 `README.md` 中补充运行时文件与样例文件的说明。
- 影响范围：
  - `.gitignore`
  - `README.md`
  - `app/data/memory/working_memory.example.json`
- 验证结果：
  - 运行时逻辑继续读取/写入 `working_memory.json`，仓库中仅保留 example 文件。

### 2026-04-26 | 多 Agent Phase 2：主控增强与下游状态切换

- 完成内容：
  - `SupervisorAgent` 从纯规则路由升级为“LLM 结构化规划 + 规则回退”的主控模式。
  - `supervisor_merge_node` 把 `vision / knowledge / report` 的结果同步回 `result` 与 `shared_context`。
  - `answer_node` 改为优先消费共享视觉与知识上下文。
  - 报告生成逻辑从 `app.core` 解耦到 `app/agents/report/service.py`。
  - `self_reflect_node` 改为优先基于共享视觉结果判断。
- 影响范围：
  - `app/agents/supervisor/agent.py`
  - `app/core/supervisor.py`
  - `app/core/answer_node.py`
  - `app/agents/report/service.py`
  - `app/core/self_reflect.py`
- 验证结果：
  - 多 Agent 与主流程回归测试通过。

### 2026-04-26 | 多 Agent Phase 3：澄清 Agent、共享上下文 Schema、可中断挂起链路

- 完成内容：
  - 新增 `ClarificationAgent`，在需要人工补充时先生成结构化澄清请求。
  - 新增 `app/orchestration/context.py`，将 `shared_context` 结构化为 `vision / knowledge / clarification / report`。
  - 重写 graph 路由，使 `wait_user` 成为可中断挂起节点。
  - `get_pending_task`、`run_detection`、`run_chat`、`continue_detection`、`generate_report` 统一暴露 `agent_trace`。
  - 修正继续执行时的用户回复写入逻辑，交由 `wait_user_node` 消费。
- 影响范围：
  - `app/core/wait_user.py`
  - `app/orchestration/context.py`
  - `app/core/agent.py`
  - `app/core/graph.py`
- 验证结果：
  - 多 Agent、pending/continue 与主流程测试通过。

### 2026-04-26 至 2026-04-27 | 多 Agent Phase 4：编排、时间线与流式执行

- 完成内容：
  - 将 supervisor 规划结果从扁平 `planned_agents` 升级为结构化 `execution_plan.steps`。
  - 扩展 `DetectionState`，加入 `execution_plan`、`step_status`、`step_attempts`、`step_outputs`、`retry_*` 等运行时字段。
  - 引入 actionable retry，明确 `retry_target / retry_reason / retry_strategy`。
  - 执行层支持按依赖分批推进，为无依赖 step 并发留出能力。
  - `supervisor_merge_node` 重构为按 agent 的 merge adapters。
  - 新增 `execution_events` 时间线，并同步暴露到 API metadata、pending 查询与 SSE。
  - 前端新增 multi-agent timeline，并接入 detect/chat/continue 三条流式主路径。
  - 时间线继续增强为支持筛选、折叠与详情面板。
- 影响范围：
  - `app/agents/supervisor/agent.py`
  - `app/core/supervisor.py`
  - `app/core/self_reflect.py`
  - `app/core/agent.py`
  - `app/core/wait_user.py`
  - `app/memory/state.py`
  - `web/index.html`
- 验证结果：
  - `tests/test_phase1_multi_agent.py`
  - `tests/test_main_flow_smoke.py`
  - `tests/test_graph_runtime.py`
  - 结果：`22 passed`

### 2026-04-27 | 架构收敛 Phase 1：services 与 orchestration 拆分

- 完成内容：
  - 将运行入口从 `app/core/agent.py` 拆分到 `app/services/`。
  - 将 supervisor 运行时拆分到 `app/orchestration/` 下的 planner、executor、merge、events 子模块。
  - 标记 legacy 编排模块，补充 `Docs/architecture.md`。
- 影响范围：
  - `app/services/*`
  - `app/orchestration/*`
  - `app/core/agent.py`
  - `app/core/supervisor.py`
  - `Docs/architecture.md`
- 验证结果：
  - `pytest tests/test_agent.py tests/test_main_flow_smoke.py tests/test_phase1_multi_agent.py tests/test_graph_runtime.py -q`
  - 结果：`37 passed, 1 skipped`

### 2026-04-27 | 架构收敛 Phase 2：grouped runtime views 与 active-path 收口

- 完成内容：
  - 在 `DetectionState` 中引入 `TaskRuntimeState`、`OrchestrationRuntimeState`、`DomainRuntimeState`。
  - 新增 `task_runtime()`、`orchestration_runtime()`、`domain_runtime()` 与对应 `apply_*` 回写入口。
  - 主链路读写逐步切到 grouped runtime，包括 graph、self_reflect、wait_user、planner_runtime、merge_adapters、answer、report。
  - 继续收敛 `context` 与 `shared_context` 的职责边界。
- 影响范围：
  - `app/memory/state.py`
  - `app/services/state_rehydration.py`
  - `app/orchestration/planner_runtime.py`
  - `app/orchestration/merge_adapters.py`
  - `app/core/answer_node.py`
  - `app/agents/report/service.py`
- 验证结果：
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - 结果：`38 passed, 1 skipped`

### 2026-04-27 | Memory Convergence：short-term、tool context 与会话压缩

- 完成内容：
  - `answer_node` 在首次回答后补齐 `ShortTermMemory` 写入，并将 `tool_effect` 纳入回答上下文。
  - `planner_runtime` 在 specialist step 成功后写入 `ToolContextMemory`。
  - 新增 `app/memory/conversation.py`，对会话历史执行轻量压缩，保留近期轮次并生成 `conversation_summary`。
  - `state_rehydration`、`wait_user`、`report` 等路径接入会话压缩与摘要读取。
  - 将 `tool_context.json`、`long_term_memory.json`、`short_term_memory.json` 调整为 runtime-only，仓库保留 example 文件。
- 影响范围：
  - `app/core/answer_node.py`
  - `app/orchestration/planner_runtime.py`
  - `app/memory/config.py`
  - `app/memory/memory_manager.py`
  - `app/memory/conversation.py`
  - `.gitignore`
  - `app/data/memory/*.example.json`
- 验证结果：
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - 结果：`38 passed, 1 skipped`

### 2026-04-27 | Documentation Update：启动与调试指南刷新

- 完成内容：
  - 更新 `README.md`，补充“本地快速联调”和“完整运行态”两种模式。
  - 增加 `anomalygpt` sidecar、RAG 初始化、健康检查、OpenAPI、SSE 与前端时间线的调试路径。
  - 增加常用测试命令和常见问题处理。
- 影响范围：
  - `README.md`
  - `USER.md`
- 验证结果：
  - 文档更新后继续做本地 smoke 验证。

### 2026-04-27 | README Smoke Verification：本地启动路径验证

- 完成内容：
  - 按 README 实际启动后端并验证 `GET /health`、`GET /openapi.json`、`/web/index.html` 可用。
  - 在 `APP_CHECKPOINT_BACKEND=memory` 模式下，走通 `detect -> chat -> generate_report` 主链路。
  - 修正文档中的 Windows 本地联调说明与 `Invoke-RestMethod` 示例。
- 影响范围：
  - `README.md`
  - `USER.md`
- 验证结果：
  - `GET http://127.0.0.1:8000/health`
  - `GET http://127.0.0.1:8000/openapi.json`
  - `GET http://127.0.0.1:8000/web/index.html`
  - `POST http://127.0.0.1:8001/v1/detect`
  - `POST http://127.0.0.1:8001/v1/chat`
  - `POST http://127.0.0.1:8001/v1/generate_report`

### 2026-04-27 | PatchCore Bootstrap：本地 MVTec-first backend 与训练脚本

- 完成内容：
  - 新增 `app/tools/patchcore_detection.py`，实现轻量本地 PatchCore 风格训练/推理管线。
  - 将 PatchCore 作为第三个视觉 backend 接入 `ImageAnomalyDetectionTool`。
  - 在 `VisionAgent` payload 中透传 `heatmap_path`、`overlay_path`、`mask_path` 与 `category`。
  - 新增 `scripts/patchcore_train.py` 与 `scripts/patchcore_eval.py`，先围绕 `data_sets/mvtec_anomaly_detection` 做离线训练与单图评估。
  - 扩展 `settings.py` 中的 PatchCore 配置，并将 `data/heatmaps/`、`models/patchcore/` 视为运行/训练产物。
- 影响范围：
  - `app/config/settings.py`
  - `app/tools/patchcore_detection.py`
  - `app/tools/image_anomaly_detection.py`
  - `app/agents/vision/agent.py`
  - `scripts/patchcore_train.py`
  - `scripts/patchcore_eval.py`
  - `.gitignore`
- 验证结果：
  - `python scripts/patchcore_train.py --category bottle --dataset-root data_sets\\mvtec_anomaly_detection --model-root models\\patchcore --image-size 128 --device cpu --max-memory-bank 2000`
  - `python scripts/patchcore_eval.py --image data_sets\\mvtec_anomaly_detection\\bottle\\test\\broken_small\\000.png --category bottle --task-id patchcore-bottle-demo --threshold 0.5`
  - `LocalPatchCoreImageAnomalyDetectionTool` 成功返回 `selected_backend=patchcore`、heatmap 路径与异常列表。

### 2026-04-28 | PatchCore Frontend Integration：热力图预览与日志编码治理

- 完成内容：
  - 在 `web/index.html` 的现有预览区域接入 `Original / BBox / Heatmap / Overlay` 四种查看模式。
  - 新增透明度滑块，并让前端自动解析 `heatmap_path`、`overlay_path`、`mask_path` 等可视化资源。
  - 在 `app/api/main.py` 新增 `/data/heatmaps` 静态挂载，保证前端可直接访问后端生成的热力图。
  - 将 `USER.md` 重写为干净的 UTF-8 版本，并按当前项目真实里程碑重新整理记录。
- 影响范围：
  - `web/index.html`
  - `app/api/main.py`
  - `USER.md`
- 验证结果：
  - `python -m py_compile app/api/main.py`
  - `node` 校验 `web/index.html` 内联脚本语法通过
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
