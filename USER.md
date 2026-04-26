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
