# USER

## 维护规则

- 每完成一个可独立验收的模块、阶段或重要修复后，立即追加一条记录到本文件�?
- 每条记录至少包含：日期、模块名、完成内容、影响范围、验证结果�?
- 提交 Git 前，先检查本文件是否已同步更新；如果没有，需要先补齐记录再提交�?
- 运行时产物、临时调试结论不要写成正式模块记录；只记录可复现、可交付的开发结果�?

## 开发记�?

### 2026-04-26 | PostgreSQL durable state �?checkpoint 持久�?

- 完成内容�?
  - 新增 `app/storage/postgres.py`，封�?PostgreSQL 运行时状态存取�?
  - 新增 `app/core/runtime.py`，统一管理 LangGraph checkpoint backend 与线程态加载�?
  - 扩展 `app/memory/checkpoint.py`、`app/config/settings.py`、`pyproject.toml`，支�?PostgreSQL 持久化配置与依赖�?
  - 打�?graph state 加载、持久化 checkpoint 与应用级 runtime state 镜像写入逻辑�?
- 影响范围�?
  - `app/core/agent.py`
  - `app/core/graph.py`
  - `app/memory/checkpoint.py`
  - `app/storage/postgres.py`
  - `app/core/runtime.py`
- 验证结果�?
  - `tests/test_checkpoint_store.py`
  - `tests/test_graph_runtime.py`

### 2026-04-26 | 图像检测路由与专业模型接入

- 完成内容�?
  - 扩展 `app/tools/image_anomaly_detection.py`，支持通用视觉模型与专业异常检测后端路由�?
  - 增加专业模型服务配置项，允许通过项目配置切换 `qwen` �?`anomalygpt`�?
  - 补充异常区域定位结果结构，统一输出异常列表与定位信息�?
- 影响范围�?
  - `app/tools/image_anomaly_detection.py`
  - `app/core/tools.py`
  - `app/api/main.py`
  - `app/config/settings.py`
- 验证结果�?
  - `tests/test_image_anomaly_detection_router.py`

### 2026-04-26 | 本地 AnomalyGPT 服务�?Docker 侧车

- 完成内容�?
  - 新增 `services/anomalygpt_local/` 本地服务骨架�?
  - 提供 `Dockerfile`、`docker-compose.yml`、`start_service.ps1` 与服务说明文档�?
  - 支持项目侧通过 HTTP 调用本地部署的专业异常检测服务�?
- 影响范围�?
  - `services/anomalygpt_local/app.py`
  - `services/anomalygpt_local/Dockerfile`
  - `services/anomalygpt_local/docker-compose.yml`
  - `services/anomalygpt_local/README.md`
- 验证结果�?
  - 服务接线由主链路测试覆盖，配置说明已写入项目文档�?

### 2026-04-26 | 前端收敛为核心流程页

- 完成内容�?
  - 将前端收敛为单页核心流程，减少分散页面与重复交互�?
  - `web/index.html` 调整为围绕检测、追问、报告生成的主工作流�?
  - 保持后端 API 不变，前端仅做交互与展示层简化�?
- 影响范围�?
  - `web/index.html`
  - `README.md`
- 验证结果�?
  - `tests/test_main_flow_smoke.py`

### 2026-04-26 | �?Agent Phase 1：有主控的监督式架构骨架

- 完成内容�?
  - 新增 supervisor、vision、knowledge、report 四类 agent 骨架�?
  - 新增 `AgentEnvelope` 作为主控与专�?agent 的统一通信契约�?
  - 扩展 `DetectionState`，增�?`agent_outputs`、`agent_trace`、`active_agent`、`shared_context`�?
  - 重写顶层 graph，将执行流升级为 supervisor 规划、执行、合并的受控流程�?
  - 保持现有外部 API 与前端协议不变，先完成内部编排迁移�?
- 影响范围�?
  - `app/agents/`
  - `app/orchestration/envelope.py`
  - `app/core/supervisor.py`
  - `app/core/graph.py`
  - `app/core/agent.py`
  - `app/memory/state.py`
- 验证结果�?
  - `tests/test_phase1_multi_agent.py`

### 2026-04-26 | 主链路回归验�?

- 完成内容�?
  - �?durable state、图像路由、多 Agent Phase 1 与主流程进行回归验证�?
- 验证结果�?
  - 执行�?
    - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py`
  - 结果�?
    - `19 passed in 10.44s`

### 2026-04-26 | 工作记忆文件治理（方�?B�?

- 完成内容�?
  - �?`app/data/memory/working_memory.json` 定义为运行时文件，不再纳�?Git 跟踪�?
  - 新增 `app/data/memory/working_memory.example.json` 作为可提交的结构样例�?
  - �?`.gitignore` �?`README.md` 中补充运行时文件与样例文件的使用说明�?
- 影响范围�?
  - `.gitignore`
  - `README.md`
  - `app/data/memory/working_memory.example.json`
- 验证结果�?
  - 运行时逻辑仍然读取/写入 `working_memory.json`，仓库中改为保留样例文件供参考�?

### 2026-04-26 | �?Agent Phase 2：主控增强与下游状态切�?

- 完成内容�?
  - �?`SupervisorAgent` 从纯规则路由升级为“LLM 结构化规�?+ 规则回退”的主控模式�?
  - `supervisor_merge_node` 现在会把 vision/knowledge/report 的结果同步回 `result` �?`shared_context`，减少对�?`tool_outputs` 的依赖�?
  - `answer_node` 改为优先消费 `shared_context["vision"]` �?`shared_context["knowledge"]`，确保回答真正建立在专家 Agent 输出上�?
  - 报告生成逻辑�?`app.core` 解耦到 `app/agents/report/service.py`，`ReportAgent` �?graph/report 入口统一复用新服务�?
  - `self_reflect_node` 改为优先基于共享视觉结果进行判断，与新的�?Agent 状态流保持一致�?
- 影响范围�?
  - `app/agents/supervisor/agent.py`
  - `app/core/supervisor.py`
  - `app/core/answer_node.py`
  - `app/core/self_reflect.py`
  - `app/agents/report/service.py`
  - `app/agents/report/agent.py`
  - `app/core/graph.py`
  - `app/core/agent.py`
  - `tests/test_phase1_multi_agent.py`
- 验证结果�?
  - `python -m pytest tests/test_phase1_multi_agent.py -q`
  - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py -q`
  - 结果：`22 passed`

### 2026-04-26 | �?Agent Phase 3：澄�?Agent、共享上下文 Schema、可中断挂起链路

- 完成内容�?
  - 新增 `ClarificationAgent`，当 `self_reflect` 判断需要人工补充时，由主控先生成结构化澄清请求，再进入等待用户节点�?
  - 新增 `app/orchestration/context.py`，将 `shared_context` 结构化为 `vision/knowledge/report/clarification` 四类上下文模型�?
  - 重写 graph 路由，使 `wait_user` 成为真正可中断节点：首次挂起直接结束，用户回复后再回�?supervisor 继续编排�?
  - `get_pending_task`、`run_detection`、`run_chat`、`continue_detection`、`generate_report` 统一暴露 `agent_trace`，便于前端展示和排障�?
  - 修正 `build_continue_state` 逻辑，避免继续执行时重复把用户回复直接写入历史，改为交由 `wait_user_node` 消费�?
- 影响范围�?
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
- 验证结果�?
  - `python -m pytest tests/test_phase1_multi_agent.py -q`
  - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py -q`
  - 结果：`24 passed`
### 2026-04-27 | Multi-Agent Phase 4A/4B | structured execution plan + actionable retry
- 完成内容�?
  - �?supervisor 规划结果从扁�?`planned_agents` 升级为结构化 `execution_plan.steps`，每�?step 记录 `id / agent / goal / depends_on / retryable`�?
  - 扩展 `DetectionState`，新�?`execution_plan`、`step_status`、`step_attempts`、`step_outputs`、`last_failed_step` 以及 `retry_target / retry_reason / retry_strategy`�?
  - 改�?`supervisor_plan_node` �?`supervisor_execute_node`，按结构�?step 执行并把 step 级状态写�?runtime metadata�?
  - 改�?`self_reflect_node`，当判定需�?retry 时输出明确的 retry 目标和策略，不再只返回抽象的 `retry` 决策�?
  - 调整主运行时返回�?SSE 节点观测，补�?`execution_plan / step_status / step_attempts`，并切换到真�?supervisor 节点名�?
  - 在执行层新增按依赖分批执行能力：同一批无依赖 step 支持并发，跨批次保持顺序，作为后续更完整 DAG 编排的基础�?
  - �?`supervisor_merge_node` 重构�?agent-specific merge adapters，降低对 `vision / knowledge / clarification / report` 的硬编码耦合，为后续新增 specialist agent 预留稳定扩展点�?
  - 新增 `execution_events` 时间线，记录 `plan_created / step_started / step_completed / step_failed / task_suspended / task_resumed` 等事件，并同步暴露到 API metadata、pending 查询结果�?SSE `execution_event` / `final_result.metadata`�?
  - 前端主工作台新增 multi-agent timeline 面板，基�?`execution_plan / execution_events / step_status / step_attempts` 渲染 step 概览与事件流，帮助用户直接观�?supervisor 编排过程�?
  - 流式接口 `final_result` 补充 answer / anomalies / pending 信息，前端首轮检测与追问切换�?`/v1/stream`，执行过程中可实时滚动展�?execution events 与增量回答�?
  - `/v1/stream` 新增 continue 分支：表单携�?`user_reply` 时走流式继续澄清链路，前�?`continueTask()` 同步切换为实时执行模式，三条主路径（detect / chat / continue）现已统一到同一�?timeline 更新机制�?
- 影响范围�?
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
- 验证结果�?
  - `pytest tests/test_phase1_multi_agent.py -q`
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py -q`
  - `node` 解析 `web/index.html` 内联脚本语法检�?
  - `pytest tests/test_main_flow_smoke.py -q`
  - 结果：`22 passed`，前端主流程与流�?continue 分支通过

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

### 2026-04-27 | Architecture Convergence Phase 1 | services split and orchestration cleanup
- ������ݣ�
  - ������������ڴ� `app/core/agent.py` ��ֵ� `app/services/`���ֱ��䵽 `task_runner.py`��`streaming.py`��`state_rehydration.py`������������ڡ�SSE��״̬�ָ�֮�����ϡ�
  - �� supervisor ����ʱ�� `app/core/supervisor.py` ��ֵ� `app/orchestration/`������ `planner_runtime.py`��`step_executor.py`��`merge_adapters.py`��`events.py`��
  - ���� `app/core/agent.py` �� `app/core/supervisor.py` ��Ϊ�������棬�������� graph ����Ե���·������ʧЧ��
  - Ϊ `planner / executor / consolidate / supplement` ���� legacy ��ǣ���ȷ���ǲ��ǵ�ǰ supervisor ����·��һ���֡�
  - ���� `Docs/architecture.md`��˵�����۷ֲ㡢�����̡�������ڡ�shared context �� legacy ģ��߽硣
- Ӱ�췶Χ��
  - `app/services/`
  - `app/orchestration/`
  - `app/core/agent.py`
  - `app/core/supervisor.py`
  - `app/api/main.py`
  - `app/core/planner.py`
  - `app/core/executor.py`
  - `app/core/consolidate.py`
  - `app/core/supplement.py`
  - `tests/test_main_flow_smoke.py`
  - `tests/test_phase1_multi_agent.py`
  - `Docs/architecture.md`
- ��֤�����
  - `pytest tests/test_agent.py tests/test_main_flow_smoke.py tests/test_phase1_multi_agent.py tests/test_graph_runtime.py -q`
  - `node` ���� `web/index.html` �����ű��﷨���
  - �����`37 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2A | shared context access helpers
- ������ݣ�
  - ���� `app/orchestration/context_store.py`��ͳһ���� `pending_clarification / pending_question / rag_context` �������ҵ�������ĵĶ�д����� shadow ͬ����
  - `merge_adapters`��`wait_user`��`state_rehydration`��`answer_node` ��Ϊͨ�� helper ���ʹ��������ģ����� `state.context[...]` �ķ�ɢ��д��
  - ���� `context` �����ֶ���������� `shared_context` ��Ϊ���ȶ�ȡ��Դ��Ϊ������������ `context` ��׼����
- Ӱ�췶Χ��
  - `app/orchestration/context_store.py`
  - `app/orchestration/merge_adapters.py`
  - `app/core/wait_user.py`
  - `app/core/answer_node.py`
  - `app/services/state_rehydration.py`
  - `tests/test_phase1_multi_agent.py`
- ��֤�����
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - `node` ���� `web/index.html` �����ű��﷨���
  - �����`37 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2B | state runtime grouping views
- ������ݣ�
  - �� `app/memory/state.py` ������ `TaskRuntimeState`��`OrchestrationRuntimeState`��`DomainRuntimeState`��Ϊ `DetectionState` �ṩ��ʽ�ķ�����ͼ��
  - ���� `task_runtime()`��`orchestration_runtime()`��`domain_runtime()`������������/�Ự����������̬�������������İ�ְ����������
  - �������� checkpoint ����ṹ���䣬������ͼ��ʽΪ���������׵�״̬�����·������һ�����ع����ա�
  - �� `Docs/architecture.md` �в��� state grouping ˵������ȷ����δ��״̬ģ��������Ǩ��·����
- Ӱ�췶Χ��
  - `app/memory/state.py`
  - `tests/test_phase1_multi_agent.py`
  - `Docs/architecture.md`
- ��֤�����
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - �����`37 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2C | runtime views consumed in core paths
- ������ݣ�
  - �� graph ·���жϸ�Ϊ���ȶ�ȡ `task_runtime()`��`orchestration_runtime()`��`domain_runtime()`���� `execution_plan / reflection_decision / report_requested / clarification` ����ֲ�߽��ں������������������ѡ�
  - `self_reflect_node` ��Ϊͨ�� runtime view ��ȡ `loop_count` �� task parameters�����ٶ� `DetectionState` �����ֶε�ֱ����ϡ�
  - `answer_node` ��Ϊͨ�� `task_runtime()` ��ȡ������Ự��ʷ����ʼ�����ջش�ڵ�Զ��� state ƽ���������խ��
  - `planner_runtime` ��ִ����ڸ�Ϊͨ�� `orchestration_runtime()` ��ȡ�ƻ��� step ���̬�������������׵�״̬��ּ�����·��
- Ӱ�췶Χ��
  - `app/core/graph.py`
  - `app/core/self_reflect.py`
  - `app/core/answer_node.py`
  - `app/orchestration/planner_runtime.py`
- ��֤�����
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - �����`37 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2D | runtime apply helpers for write paths
- ������ݣ�
  - �� `DetectionState` ������ `apply_task_runtime()`��`apply_orchestration_runtime()`��`apply_domain_runtime()`��Ϊ grouped runtime �ṩ��ʽд����ڡ�
  - `prepare_followup_state()` ��Ϊͨ�� runtime apply helpers ���� follow-up �ִ������ֶΣ����ٶԶ��� state �ֶε�ɢд��
  - `wait_user_node()` ��Ϊͨ�� `task_runtime` / `orchestration_runtime` ���»Ự������ָ��¼��� `needs_user_input` ״̬���� grouped runtime ��ʼ�е�д·��ְ��
  - �������Ը��� runtime apply helpers��ȷ�Ϸ�����ͼ�����ɶ���Ҳ���ȶ�д���� state��
- Ӱ�췶Χ��
  - `app/memory/state.py`
  - `app/services/state_rehydration.py`
  - `app/core/wait_user.py`
  - `tests/test_phase1_multi_agent.py`
- ��֤�����
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - �����`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2E | orchestration writes via grouped runtime
- ������ݣ�
  - `supervisor_plan_node()` �� `supervisor_execute_node()` ��ʼͨ�� `apply_orchestration_runtime()` / `apply_domain_runtime()` ��дִ�мƻ���step ״̬��attempt��step outputs �� agent outputs��
  - `supervisor_merge_node()` ��� adapters ��ʼͨ�� grouped runtime д�� `tool_outputs`��`shared_context`��`unknown_anomaly_types` �� `needs_user_input`������ orchestration ��� `DetectionState` �����ֶε�ɢд��
  - ���� `execution_events` �ڶ��� state �� orchestration runtime ��ͼ֮���ͬ���������¼� append �󱻾���ͼ���ǡ�
- Ӱ�췶Χ��
  - `app/orchestration/planner_runtime.py`
  - `app/orchestration/merge_adapters.py`
- ��֤�����
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - �����`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2F | result-side writes via grouped runtime
- ������ݣ�
  - ��д `app/core/answer_node.py` Ϊ�ɾ��� ASCII-safe ʵ�֣����ûش�ڵ�ͨ�� `task_runtime()` / `apply_task_runtime()` �� `domain_runtime()` ���»Ự�����������������ش����̡�
  - ��д `app/agents/report/service.py` Ϊ�ɾ�ʵ�֣����ñ�������·��ͨ�� grouped runtime ��ȡ task/orchestration/domain ��Ϣ������ͨ�� `apply_domain_runtime()` ��д report ����� shared context��
  - ���� answer/report �������������ļ�����ʷ�������������ͺ��������ع�ʱ���﷨���ı��𻵷��ա�
- Ӱ�췶Χ��
  - `app/core/answer_node.py`
  - `app/agents/report/service.py`
- ��֤�����
  - `python -m py_compile app/core/answer_node.py app/agents/report/service.py`
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - �����`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2G | top-level compatibility clarified and supervisor reads tightened
- ������ݣ�
  - Ϊ `DetectionState` ���䶥��״̬˵������ȷ flat state ������������ checkpoint ���ݣ����´���Ӧ������ grouped runtime ��ͼ��
  - `SupervisorAgent` ��Ϊ����ͨ�� `task_runtime()`��`orchestration_runtime()`��`domain_runtime()` ��ȡ `report_requested`��`needs_user_input`��`retry_*`��`agent_outputs`��`shared_context` �ȹؼ�״̬��
  - �� supervisor �滮���Ϊ����ȷ�ġ�runtime view first�� �����ߣ����ٶ� `DetectionState` �����ֶε�ֱ�Ӷ�ȡ��ϡ�
- Ӱ�췶Χ��
  - `app/memory/state.py`
  - `app/agents/supervisor/agent.py`
- ��֤�����
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - �����`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2H | active path runtime-view-first completion
- ������ݣ�
  - `self_reflect`��`wait_user`��`step_executor`��`task_runner.generate_report` ��ʣ������ģ����������� grouped runtime ��д��ʽ��
  - `planner_runtime` �� agent trace ��д��Ҳ���� `apply_domain_runtime()` ·�������� active path �϶Զ��� state ��ɢд������
  - `Docs/architecture.md` �������̬˵������������·�Ѿ��ﵽ runtime-view-first�������ֶ���Ҫ�е� checkpoint �����ְ��
- Ӱ�췶Χ��
  - `app/core/self_reflect.py`
  - `app/core/wait_user.py`
  - `app/orchestration/step_executor.py`
  - `app/orchestration/planner_runtime.py`
  - `app/services/task_runner.py`
  - `Docs/architecture.md`
- ��֤�����
  - `python -m py_compile app/core/self_reflect.py app/core/wait_user.py app/orchestration/step_executor.py app/orchestration/planner_runtime.py app/services/task_runner.py`
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - �����`38 passed, 1 skipped`

### 2026-04-27 | 主文档收口与接口说明统一

- 完成内容�?
  - �?`README.md` 重写为当前项目唯一主文档，统一描述现有 FastAPI 路由、LangGraph �?Agent 流程、前端入口、RAG、视觉后端路由、checkpoint 与记忆策略�?
  - 移除 README 中旧�?JSON 检测示例、旧链式 `anomaly_detect/summarize` 流程、旧多页面前端描述等过时内容�?
  - �?README 中明确列出建议删除或归档的冗余文档，作为后续文档清理依据�?
- 影响范围�?
  - `README.md`
  - `USER.md`
- 验证结果�?
  - 本次为文档整理，未改变运行时代码�?

### 2026-04-27 | 过时文档清理

- 完成内容�?
  - 删除已由�?README 合并覆盖或与当前接口不匹配的旧文档�?
  - 保留 `Docs/01-LangChain.ipynb`、`Docs/02-LangGraph.ipynb`、`Docs/03-LangSmith.ipynb` 作为学习笔记�?
  - 更新 README 文档维护策略，改为记录当前实际保留文档�?
- 影响范围�?
  - `README.md`
  - `USER.md`
  - `web/README.md`
  - `Docs/api_docs.md`
  - `Docs/function_docs.md`
  - `Docs/开发指�?md`
  - `Docs/2026-04-21-architecture_review.md`
  - `Docs/2026-04-21-implementation_update.md`
  - `Docs/agent_engineering_review.md`
- 验证结果�?
  - 已确认目标文档删除完成，三个 notebook 未删除�?

### 2026-04-27 | 前端入口收敛为单�?

- 完成内容�?
  - 审查 `web/` 下所�?HTML 页面，确认除 `index.html` 外均为跳转到主页面的兼容壳�?
  - 搜索项目代码、测试和文档引用，确认旧 HTML 页面未被运行时代码依赖�?
  - 删除 `chat.html`、`detection.html`、`expert_inspection.html`、`frontend_chat.html`、`rag.html`，只保留 `web/index.html`�?
  - 更新 README 中的前端目录结构和说明�?
- 影响范围�?
  - `web/index.html`
  - `web/chat.html`
  - `web/detection.html`
  - `web/expert_inspection.html`
  - `web/frontend_chat.html`
  - `web/rag.html`
  - `README.md`
  - `USER.md`
- 验证结果�?
  - `web/` 目录下仅�?`index.html` 一�?HTML 页面�?

### 2026-04-27 | Memory Convergence | short-term writes, tool audit, and conversation compaction
- ������ݣ�
  - nswer_node ���״λش���� ShortTermMemory д�룬���� 	ool_effect �������ջش������ġ�
  - planner_runtime �� specialist step �ɹ���д�� ToolContextMemory���ù��������·������ء�
  - ���� pp/memory/conversation.py���ԻỰ��ʷִ������ѹ����������������֣������۵�Ϊ conversation_summary��
  - state_rehydration��wait_user��eport ·������Ựѹ��/ժҪ��ȡ�����ٳ��������������͡�
  - �� 	ool_context.json Ҳ����Ϊ runtime-only �ļ����ֿ�ֻ���� 	ool_context.example.json ʾ����
- Ӱ�췶Χ��
  - pp/core/answer_node.py
  - pp/orchestration/planner_runtime.py
  - pp/core/wait_user.py
  - pp/services/state_rehydration.py
  - pp/agents/report/service.py
  - pp/memory/config.py
  - pp/memory/memory_manager.py
  - pp/memory/conversation.py
  - .gitignore
  - pp/data/memory/tool_context.example.json
  - 	ests/test_phase1_multi_agent.py
- ��֤�����
  - python -m py_compile app/memory/config.py app/memory/memory_manager.py app/memory/conversation.py app/core/answer_node.py app/agents/report/service.py app/orchestration/planner_runtime.py app/services/state_rehydration.py app/core/wait_user.py app/core/self_reflect.py
  - pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q
  - �����38 passed, 1 skipped