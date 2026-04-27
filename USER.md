# USER

## 维护规则

- 每完成一个可独立验收的模块、阶段或重要修复后，立即追加一条记录到本文件。
- 每条记录至少包含：日期、模块名、完成内容、影响范围、验证结果。
- 提交 Git 前，先检查本文件是否已同步更新；如果没有，需要先补齐记录再提交。
- 运行时产物、临时调试结论不要写成正式模块记录；只记录可复现、可交付的开发结果。

## 开发记录

### 2026-04-26 | PostgreSQL durable state 与 checkpoint 持久化

- 完成内容：
  - 新增 `app/storage/postgres.py`，封装 PostgreSQL 运行时状态存取。
  - 新增 `app/core/runtime.py`，统一管理 LangGraph checkpoint backend 与线程态加载。
  - 扩展 `app/memory/checkpoint.py`、`app/config/settings.py`、`pyproject.toml`，支持 PostgreSQL 持久化配置与依赖。
  - 打通 graph state 加载、持久化 checkpoint 与应用级 runtime state 镜像写入逻辑。
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
  - `tests/test_image_anomaly_detection_router.py`

### 2026-04-26 | 本地 AnomalyGPT 服务与 Docker 侧车

- 完成内容：
  - 新增 `services/anomalygpt_local/` 本地服务骨架。
  - 提供 `Dockerfile`、`docker-compose.yml`、`start_service.ps1` 与服务说明文档。
  - 支持项目侧通过 HTTP 调用本地部署的专业异常检测服务。
- 影响范围：
  - `services/anomalygpt_local/app.py`
  - `services/anomalygpt_local/Dockerfile`
  - `services/anomalygpt_local/docker-compose.yml`
  - `services/anomalygpt_local/README.md`
- 验证结果：
  - 服务接线由主链路测试覆盖，配置说明已写入项目文档。

### 2026-04-26 | 前端收敛为核心流程页

- 完成内容：
  - 将前端收敛为单页核心流程，减少分散页面与重复交互。
  - `web/index.html` 调整为围绕检测、追问、报告生成的主工作流。
  - 保持后端 API 不变，前端仅做交互与展示层简化。
- 影响范围：
  - `web/index.html`
  - `README.md`
- 验证结果：
  - `tests/test_main_flow_smoke.py`

### 2026-04-26 | 多 Agent Phase 1：有主控的监督式架构骨架

- 完成内容：
  - 新增 supervisor、vision、knowledge、report 四类 agent 骨架。
  - 新增 `AgentEnvelope` 作为主控与专家 agent 的统一通信契约。
  - 扩展 `DetectionState`，增加 `agent_outputs`、`agent_trace`、`active_agent`、`shared_context`。
  - 重写顶层 graph，将执行流升级为 supervisor 规划、执行、合并的受控流程。
  - 保持现有外部 API 与前端协议不变，先完成内部编排迁移。
- 影响范围：
  - `app/agents/`
  - `app/orchestration/envelope.py`
  - `app/core/supervisor.py`
  - `app/core/graph.py`
  - `app/core/agent.py`
  - `app/memory/state.py`
- 验证结果：
  - `tests/test_phase1_multi_agent.py`

### 2026-04-26 | 主链路回归验证

- 完成内容：
  - 对 durable state、图像路由、多 Agent Phase 1 与主流程进行回归验证。
- 验证结果：
  - 执行：
    - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py`
  - 结果：
    - `19 passed in 10.44s`

### 2026-04-26 | 工作记忆文件治理（方案 B）

- 完成内容：
  - 将 `app/data/memory/working_memory.json` 定义为运行时文件，不再纳入 Git 跟踪。
  - 新增 `app/data/memory/working_memory.example.json` 作为可提交的结构样例。
  - 在 `.gitignore` 与 `README.md` 中补充运行时文件与样例文件的使用说明。
- 影响范围：
  - `.gitignore`
  - `README.md`
  - `app/data/memory/working_memory.example.json`
- 验证结果：
  - 运行时逻辑仍然读取/写入 `working_memory.json`，仓库中改为保留样例文件供参考。

### 2026-04-26 | 多 Agent Phase 2：主控增强与下游状态切换

- 完成内容：
  - 将 `SupervisorAgent` 从纯规则路由升级为“LLM 结构化规划 + 规则回退”的主控模式。
  - `supervisor_merge_node` 现在会把 vision/knowledge/report 的结果同步回 `result` 与 `shared_context`，减少对旧 `tool_outputs` 的依赖。
  - `answer_node` 改为优先消费 `shared_context["vision"]` 与 `shared_context["knowledge"]`，确保回答真正建立在专家 Agent 输出上。
  - 报告生成逻辑从 `app.core` 解耦到 `app/agents/report/service.py`，`ReportAgent` 与 graph/report 入口统一复用新服务。
  - `self_reflect_node` 改为优先基于共享视觉结果进行判断，与新的多 Agent 状态流保持一致。
- 影响范围：
  - `app/agents/supervisor/agent.py`
  - `app/core/supervisor.py`
  - `app/core/answer_node.py`
  - `app/core/self_reflect.py`
  - `app/agents/report/service.py`
  - `app/agents/report/agent.py`
  - `app/core/graph.py`
  - `app/core/agent.py`
  - `tests/test_phase1_multi_agent.py`
- 验证结果：
  - `python -m pytest tests/test_phase1_multi_agent.py -q`
  - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py -q`
  - 结果：`22 passed`

### 2026-04-26 | 多 Agent Phase 3：澄清 Agent、共享上下文 Schema、可中断挂起链路

- 完成内容：
  - 新增 `ClarificationAgent`，当 `self_reflect` 判断需要人工补充时，由主控先生成结构化澄清请求，再进入等待用户节点。
  - 新增 `app/orchestration/context.py`，将 `shared_context` 结构化为 `vision/knowledge/report/clarification` 四类上下文模型。
  - 重写 graph 路由，使 `wait_user` 成为真正可中断节点：首次挂起直接结束，用户回复后再回到 supervisor 继续编排。
  - `get_pending_task`、`run_detection`、`run_chat`、`continue_detection`、`generate_report` 统一暴露 `agent_trace`，便于前端展示和排障。
  - 修正 `build_continue_state` 逻辑，避免继续执行时重复把用户回复直接写入历史，改为交由 `wait_user_node` 消费。
- 影响范围：
  - `app/orchestration/context.py`
  - `app/memory/state.py`
  - `app/agents/clarification/`
  - `app/agents/factory.py`
  - `app/agents/supervisor/agent.py`
  - `app/core/supervisor.py`
  - `app/core/graph.py`
  - `app/core/wait_user.py`
  - `app/core/agent.py`
  - `app/core/answer_node.py`
  - `app/core/self_reflect.py`
  - `app/agents/report/service.py`
  - `tests/test_phase1_multi_agent.py`
- 验证结果：
  - `python -m pytest tests/test_phase1_multi_agent.py -q`
  - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py -q`
  - 结果：`24 passed`
### 2026-04-27 | Multi-Agent Phase 4A/4B | structured execution plan + actionable retry
- 完成内容：
  - 将 supervisor 规划结果从扁平 `planned_agents` 升级为结构化 `execution_plan.steps`，每个 step 记录 `id / agent / goal / depends_on / retryable`。
  - 扩展 `DetectionState`，新增 `execution_plan`、`step_status`、`step_attempts`、`step_outputs`、`last_failed_step` 以及 `retry_target / retry_reason / retry_strategy`。
  - 改造 `supervisor_plan_node` 与 `supervisor_execute_node`，按结构化 step 执行并把 step 级状态写回 runtime metadata。
  - 改造 `self_reflect_node`，当判定需要 retry 时输出明确的 retry 目标和策略，不再只返回抽象的 `retry` 决策。
  - 调整主运行时返回与 SSE 节点观测，补充 `execution_plan / step_status / step_attempts`，并切换到真实 supervisor 节点名。
  - 在执行层新增按依赖分批执行能力：同一批无依赖 step 支持并发，跨批次保持顺序，作为后续更完整 DAG 编排的基础。
  - 将 `supervisor_merge_node` 重构为 agent-specific merge adapters，降低对 `vision / knowledge / clarification / report` 的硬编码耦合，为后续新增 specialist agent 预留稳定扩展点。
  - 新增 `execution_events` 时间线，记录 `plan_created / step_started / step_completed / step_failed / task_suspended / task_resumed` 等事件，并同步暴露到 API metadata、pending 查询结果与 SSE `execution_event` / `final_result.metadata`。
  - 前端主工作台新增 multi-agent timeline 面板，基于 `execution_plan / execution_events / step_status / step_attempts` 渲染 step 概览与事件流，帮助用户直接观察 supervisor 编排过程。
  - 流式接口 `final_result` 补充 answer / anomalies / pending 信息，前端首轮检测与追问切换到 `/v1/stream`，执行过程中可实时滚动展示 execution events 与增量回答。
  - `/v1/stream` 新增 continue 分支：表单携带 `user_reply` 时走流式继续澄清链路，前端 `continueTask()` 同步切换为实时执行模式，三条主路径（detect / chat / continue）现已统一到同一套 timeline 更新机制。
- 影响范围：
  - `app/agents/supervisor/agent.py`
  - `app/agents/supervisor/__init__.py`
  - `app/core/supervisor.py`
  - `app/core/graph.py`
  - `app/core/self_reflect.py`
  - `app/core/agent.py`
  - `app/core/wait_user.py`
  - `app/memory/state.py`
  - `tests/test_phase1_multi_agent.py`
  - `tests/test_main_flow_smoke.py`
  - `web/index.html`
- 验证结果：
  - `pytest tests/test_phase1_multi_agent.py -q`
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py -q`
  - `node` 解析 `web/index.html` 内联脚本语法检查
  - `pytest tests/test_main_flow_smoke.py -q`
  - 结果：`22 passed`，前端主流程与流式 continue 分支通过

### 2026-04-27 | Frontend Timeline UX | filters, collapse, detail inspector
- ������ݣ�
  - Ϊ multi-agent timeline �������״̬ɸѡ��`ȫ�� / ������ / ʧ�� / �ȴ� / ���`������������ʱ���Կ��پ۽��쳣�͹���ڵ㡣
  - ���� `Steps / Events` �۵����أ��¼�������ʱ����������һ�࣬������ǰ�����ɨ��Ч�ʡ�
  - ����������壬��� step ���¼���ɲ鿴 `agent / step_id / attempt / depends_on` �ȹؼ��ֶκ�ԭʼ JSON�����㾫ȷ���ϡ�
  - timeline �ڲ���Ϊ������ + �¼��� + ����������������ṹ��ͬʱ�����ƶ��˵���չʾ��
- Ӱ�췶Χ��
  - `web/index.html`
- ��֤�����
  - `node` ���� `web/index.html` �����ű��﷨���
  - `pytest tests/test_main_flow_smoke.py tests/test_phase1_multi_agent.py tests/test_graph_runtime.py -q`
  - �����`22 passed`
