# MMDL-Agent

MMDL-Agent 是一个面向工业视觉异常诊断的多 Agent 应用框架。项目以 FastAPI 提供 HTTP API，以 LangGraph 编排多步骤诊断流程，并集成视觉检测、RAG 知识检索、多轮问答、人工澄清、报告生成和运行状态持久化。

当前主流程是：

```text
上传图片 / 提交问题
  -> Supervisor 规划专家 Agent
  -> Vision Agent 检测与定位异常
  -> Knowledge Agent 检索相似案例
  -> Self Reflect 判断是否需要补充信息
  -> Answer / Wait User / Report
```

## 当前架构

```text
MMDL-Agent/
├── main.py                         # FastAPI app 导出入口
├── pyproject.toml                  # 项目依赖与构建配置
├── README.md                       # 当前唯一主文档
├── USER.md                         # 开发记录与交付记录
├── app/
│   ├── api/main.py                 # HTTP 路由、中间件、异常处理、静态文件挂载
│   ├── agents/                     # supervisor / vision / knowledge / clarification / report
│   ├── config/settings.py          # 环境变量配置
│   ├── core/                       # LangGraph 节点与运行入口
│   ├── exceptions/base.py          # 统一异常体系
│   ├── memory/                     # DetectionState、记忆、checkpoint
│   ├── orchestration/              # AgentEnvelope 与共享上下文模型
│   ├── rag/                        # 数据集分析、向量库、检索、在线反馈
│   ├── schemas/detection.py        # API 请求/响应模型
│   ├── storage/postgres.py         # PostgreSQL runtime state 镜像
│   └── tools/image_anomaly_detection.py
├── services/anomalygpt_local/      # 可选本地 AnomalyGPT sidecar 服务
├── tests/                          # 自动化测试
└── web/
    └── index.html                  # 单页核心工作台
```

## 核心模块

| 模块 | 职责 | 关键文件 |
|---|---|---|
| API 层 | 路由、CORS、Trace ID、异常响应、静态文件挂载 | `app/api/main.py` |
| 工作流 | LangGraph 节点、条件路由、挂起/恢复 | `app/core/graph.py`, `app/core/agent.py` |
| 多 Agent | 主控规划与专家执行 | `app/agents/` |
| 视觉检测 | Qwen 视觉模型或专业 HTTP 后端路由 | `app/tools/image_anomaly_detection.py` |
| RAG | 数据集建库、文本/图像检索、反馈入库 | `app/rag/` |
| 记忆与持久化 | 多轮上下文、长期记忆、checkpoint | `app/memory/`, `app/core/runtime.py` |
| 前端 | 图片上传、异常定位展示、多轮追问、报告展示 | `web/index.html` |
| AnomalyGPT sidecar | 本地专业异常检测服务封装 | `services/anomalygpt_local/` |

## 快速启动

### 1. 创建环境

```powershell
conda create -n MMDL-Agent python=3.12
conda activate MMDL-Agent
```

也可以使用 venv：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. 安装依赖

```powershell
pip install -e .
```

### 3. 配置环境变量

复制示例配置：

```powershell
Copy-Item .env.example .env
```

常用配置：

```env
APP_OPENAI_API_KEY=
APP_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
APP_LLM_MODEL=qwen3.5-plus
APP_LLM_VISION_MODEL=qwen3.5-plus

APP_CHECKPOINT_BACKEND=postgres
APP_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mmdl_agent
APP_DATABASE_SCHEMA=public

APP_VISION_DETECTOR_BACKEND=qwen
APP_PROFESSIONAL_VISION_DETECTOR_TYPE=anomalygpt
APP_PROFESSIONAL_VISION_DETECTOR_URL=http://127.0.0.1:9001/detect

APP_RAG_MULTIMODAL_EMBEDDING_MODEL=multimodal-embedding-v1
```

说明：

- `APP_OPENAI_API_KEY` 当前同时用于兼容 OpenAI 接口的 DashScope LLM 调用和 DashScope 多模态 embedding。
- `APP_CHECKPOINT_BACKEND=postgres` 时需要配置可访问的 PostgreSQL；未配置数据库或依赖不可用时，运行时会回退到内存 checkpoint。
- `APP_VISION_DETECTOR_BACKEND=qwen` 默认走通用视觉模型；设为 `anomalygpt` 时默认走专业 HTTP 后端。

### 推荐启动模式

#### 模式 A：本地快速联调

适合先把 API、LangGraph、多 Agent 流程和前端工作台跑起来。

建议 `.env` 最少这样配：

```env
APP_OPENAI_API_KEY=your_key
APP_CHECKPOINT_BACKEND=memory
APP_VISION_DETECTOR_BACKEND=qwen
```

这套模式不依赖 PostgreSQL，也不要求先启动本地 AnomalyGPT sidecar。

> 在 Windows 本地联调时，推荐优先使用这一模式。当前 `postgres` checkpoint
> 后端在 Windows 默认事件循环下可能触发 psycopg async 兼容问题，此时先切到
> `APP_CHECKPOINT_BACKEND=memory` 更稳。

#### 模式 B：完整运行态

适合验证持久化 checkpoint、RAG 数据和专业检测后端联动。

建议额外准备：

- PostgreSQL
- `data_sets/mvtec_anomaly_detection` 数据集
- 可选的 `services/anomalygpt_local/` sidecar

常见配置：

```env
APP_CHECKPOINT_BACKEND=postgres
APP_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mmdl_agent
APP_VISION_DETECTOR_BACKEND=anomalygpt
APP_PROFESSIONAL_VISION_DETECTOR_URL=http://127.0.0.1:9001/detect
```

### 4. 启动后端

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

打开前端：

```text
http://127.0.0.1:8000/web/index.html
```

也可以直接用浏览器打开 `web/index.html`，页面会调用同源或本地后端 API。

### 5. 启动可选的本地专业检测 sidecar

如果你要联调 `anomalygpt` 专业检测后端，可以进入：

```powershell
cd services/anomalygpt_local
```

然后按该目录下的 [README](services/anomalygpt_local/README.md) 或 `docker-compose.yml` 启动。

### 6. 初始化 RAG（可选）

如果要验证知识检索链路，可以先建库：

```powershell
curl -X POST http://127.0.0.1:8000/v1/rag/build `
  -H "Content-Type: application/json" `
  -d "{\"dataset_root\":\"data_sets/mvtec_anomaly_detection\",\"include_normal\":false}"
```

RAG 构建是可选的；不建库也可以先调通检测、澄清和报告主流程。

## 前端工作流

当前前端只维护一个主入口：`web/index.html`。

主要操作：

1. 填写 `asset_id`、问题描述并上传图片。
2. 点击“开始检测”，调用 `POST /v1/detect`。
3. 查看回答、异常标签、bbox 或异常热区 mask。
4. 如果任务进入 `pending`，输入补充信息并调用 `POST /v1/continue`。
5. 对已有任务继续追问，调用 `POST /v1/chat`。
6. 点击“生成报告”，调用 `POST /v1/generate_report`。

## 调试指南

### 最短调试路径

建议按这个顺序排查：

1. 启动后端：

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

2. 健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

3. 看 OpenAPI schema：

```text
http://127.0.0.1:8000/openapi.json
```

4. 打开前端工作台：

```text
http://127.0.0.1:8000/web/index.html
```

5. 先走一次最小检测请求，再看日志和响应中的 `metadata.agent_trace / execution_events`。

### 推荐调试入口

- 接口联调：`/v1/detect`、`/v1/chat`、`/v1/continue`
- 实时流程调试：`/v1/stream`
- 待澄清任务排查：`/v1/pending/{task_id}`
- 报告链路验证：`/v1/generate_report`
- RAG 验证：`/v1/rag/build`、`/v1/rag/query`

### 调试多 Agent 流程时重点看什么

当前后端已经暴露这些运行态信息：

- `metadata.agent_trace`
- `metadata.execution_plan`
- `metadata.step_status`
- `metadata.step_attempts`
- `metadata.execution_events`

前端 `web/index.html` 也已经有时间线面板，适合排查：

- supervisor 实际规划了哪些 specialist
- 哪一步失败或重试
- 是否进入 `pending`
- 继续澄清后是否恢复执行

### 常用测试命令

回归主链路：

```powershell
pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q
```

只看多 Agent 编排：

```powershell
pytest tests/test_phase1_multi_agent.py -q
```

只看 API 主流程：

```powershell
pytest tests/test_main_flow_smoke.py -q
```

### 常见问题

#### 1. 后端启动时报静态目录或上传目录错误

确认这些目录存在：

- `web/`
- `data/uploads/`
- `data/rag/`（如果启用了 RAG）

#### 2. PostgreSQL 没起好，项目无法保存 checkpoint

本地开发可以先把：

```env
APP_CHECKPOINT_BACKEND=memory
```

先切到内存模式，把主流程跑通之后再接回 PostgreSQL。

#### 3. `pending` 之后不知道怎么继续

先查：

```text
GET /v1/pending/{task_id}
```

确认 `pending_question`，再调用：

```text
POST /v1/continue
```

#### 4. 想看执行过程而不是只看最终答案

优先用：

```text
POST /v1/stream
```

或者直接看前端时间线面板。

## 工作流细节

主图定义在 `app/core/graph.py`：

```text
load_data
  -> supervisor_plan
  -> supervisor_execute 或 supervisor_merge
  -> supervisor_merge
  -> wait_user 或 self_reflect
  -> supervisor_plan 或 answer
  -> report 或 END
```

专家 Agent：

- `SupervisorAgent`：根据任务状态、图像输入、问题意图和已有输出规划专家。
- `VisionAgent`：调用图像异常检测工具，返回异常列表、定位信息和元数据。
- `KnowledgeAgent`：从 RAG 检索相似工业异常案例。
- `ClarificationAgent`：当置信度或异常类型不明确时生成待澄清问题。
- `ReportAgent`：复用报告生成服务输出完整诊断报告。

## 主流程 API

### `GET /`

返回应用基本信息。

> 当前 FastAPI 配置中 `docs_url=None`，不要把 `/docs` 当作可靠入口；可使用 `/openapi.json` 查看 OpenAPI schema。

### `GET /health`

健康检查。

响应示例：

```json
{
  "status": "ok",
  "timestamp": 1770000000.0
}
```

### `POST /v1/detect`

首次检测接口。当前支持 `multipart/form-data`。

表单字段：

| 字段 | 必填 | 说明 |
|---|---:|---|
| `task_id` | 是 | 任务 ID |
| `asset_id` | 是 | 设备或资产 ID |
| `start_time` | 是 | 开始时间，字符串即可，建议 ISO8601 |
| `end_time` | 是 | 结束时间，字符串即可，建议 ISO8601 |
| `question` | 否 | 用户问题 |
| `data_source` | 否 | 数据来源 |
| `parameters` | 否 | JSON 字符串 |
| `image` | 否 | 图片文件；不传则为文本模式 |

示例：

```powershell
curl -X POST http://127.0.0.1:8000/v1/detect `
  -F "task_id=test-001" `
  -F "asset_id=pump-001" `
  -F "start_time=2026-04-27T10:00:00+08:00" `
  -F "end_time=2026-04-27T10:05:00+08:00" `
  -F "question=这张图片是否存在裂纹或破损？" `
  -F "parameters={\"tool_type\":\"qwen\",\"require_localization\":true}" `
  -F "image=@C:\path\to\image.jpg"
```

如果你在 Windows PowerShell 下遇到 `parameters must be valid JSON string`，
最简单的做法是先省略 `parameters`，把主链路跑通后再逐步补调参字段。

成功响应字段通常包括：

- `task_id`
- `status`: `success` 或 `pending`
- `answer`
- `anomalies`
- `metadata.logs`
- `metadata.agent_trace`
- `metadata.result_metadata`

`pending` 响应会额外包含：

- `pending_clarification`
- `pending_question`
- `conversation_history`
- `agent_trace`

### `POST /v1/chat`

基于已有任务继续追问。

请求体：

```json
{
  "task_id": "test-001",
  "question": "这个异常可能是什么原因导致的？"
}
```

PowerShell 推荐写法：

```powershell
$payload = @{
  task_id = "test-001"
  question = "这个异常可能是什么原因导致的？"
} | ConvertTo-Json -Compress

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/v1/chat" `
  -ContentType "application/json" `
  -Body $payload
```

### `POST /v1/continue`

为 pending 任务提交人工澄清。

请求体：

```json
{
  "task_id": "test-001",
  "user_reply": "异常位于图像右下角，现场观察到轻微裂纹。"
}
```

PowerShell 推荐写法：

```powershell
$payload = @{
  task_id = "test-001"
  user_reply = "异常位于图像右下角，现场观察到轻微裂纹。"
} | ConvertTo-Json -Compress

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/v1/continue" `
  -ContentType "application/json" `
  -Body $payload
```

### `GET /v1/pending/{task_id}`

查询某个任务是否处于待澄清状态。

### `POST /v1/generate_report`

基于已有任务状态生成完整报告。

PowerShell 推荐写法：

```powershell
$payload = @{
  task_id = "test-001"
} | ConvertTo-Json -Compress

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/v1/generate_report" `
  -ContentType "application/json" `
  -Body $payload
```

请求体：

```json
{
  "task_id": "test-001"
}
```

### `POST /v1/detect_with_report`

一次性执行检测并生成报告。请求格式与 `/v1/detect` 相同；如果检测结果为 `pending`，会直接返回 pending，不生成报告。

### `POST /v1/stream`

SSE 流式接口，使用 `multipart/form-data`。

常见事件：

- `node_start`
- `tool_start`
- `tool_end`
- `stream`
- `final_result`
- `error`
- `close`

## RAG API

RAG 由 `app/rag/service.py` 统一管理，向量库默认写入 `data/rag/chroma`。

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/v1/rag/build` | 同步扫描数据集并构建向量索引 |
| `POST` | `/v1/rag/build/start` | 异步启动建库任务 |
| `GET` | `/v1/rag/build/status/{task_id}` | 查询异步建库进度 |
| `POST` | `/v1/rag/query` | 按文本检索相似异常案例 |
| `POST` | `/v1/rag/query-image` | 按图片路径检索相似异常案例 |
| `POST` | `/v1/rag/generate-descriptions` | 为数据集异常样本生成描述 |
| `POST` | `/v1/rag/ingest-feedback` | 将高置信用户反馈写入向量库 |

文本检索示例：

```json
{
  "query_text": "表面划痕，靠近边缘",
  "category": "capsule",
  "top_k": 3
}
```

反馈入库示例：

```json
{
  "image_path": "data/uploads/case-001.png",
  "category": "capsule",
  "user_description": "右侧边缘存在细长裂纹",
  "model_confidence": 0.93,
  "is_anomaly": true,
  "anomaly_type": "crack",
  "severity": "medium"
}
```

只有 `model_confidence >= APP_RAG_LEARNING_THRESHOLD` 的反馈会被接受。

## 视觉后端路由

视觉检测入口是 `ImageAnomalyDetectionTool`。

可选后端：

- `qwen`：调用兼容 OpenAI 接口的视觉模型，默认模型来自 `APP_LLM_VISION_MODEL`。
- `anomalygpt` / `professional`：调用 `APP_PROFESSIONAL_VISION_DETECTOR_URL` 指向的专业 HTTP 服务。

全局默认：

```env
APP_VISION_DETECTOR_BACKEND=qwen
```

单次请求覆盖：

```json
{
  "tool_type": "anomalygpt",
  "require_localization": true,
  "detector_params": {
    "mask_threshold": 0.5
  }
}
```

本地 AnomalyGPT sidecar 的部署细节见 `services/anomalygpt_local/README.md`。

## 状态与记忆

### Checkpoint

运行时通过 `app/core/runtime.py` 创建 LangGraph session。

- `APP_CHECKPOINT_BACKEND=memory`：进程内保存，多轮任务只在当前后端进程生命周期内有效。
- `APP_CHECKPOINT_BACKEND=postgres`：使用 LangGraph Postgres saver；同时把应用级状态镜像写入 `agent_run_state` 表。

### Memory

`app/memory/memory_manager.py` 管理工作记忆、短期记忆、长期记忆和工具上下文。

运行时文件策略：

- `app/data/memory/working_memory.json` 是运行时生成文件，不应提交。
- `app/data/memory/working_memory.example.json` 是结构示例。

## 测试与检查

```powershell
python -m compileall app -q
python -m compileall services -q
python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py -q
```

完整测试：

```powershell
pytest -q
```

## 文档维护策略

当前项目以 `README.md` 作为唯一主文档，避免接口说明分散后再次过时。

保留文档：

- 保留：`README.md`、`USER.md`、`services/anomalygpt_local/README.md`
- 可保留为模块说明：`app/prompts/README.md`
- 保留学习笔记：`Docs/01-LangChain.ipynb`、`Docs/02-LangGraph.ipynb`、`Docs/03-LangSmith.ipynb`
