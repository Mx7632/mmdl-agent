# MMDL-Agent

MMDL-Agent 是一个面向工业视觉质检场景的异常检测 Agent 系统。本项目不是单独训练或调用某一个异常检测算法，而是把 **图像异常检测、热力图定位、多 Agent 协同分析、RAG 知识检索、追问续接、会话记忆和报告生成** 整合成一个可以运行、可以演示、可以继续扩展的毕业设计原型系统。

一句话概括：

```text
上传工业图像
  -> 视觉检测模型定位异常
  -> 多 Agent 组织分析流程
  -> RAG 检索相似案例和知识
  -> 前端展示热力图、异常区域、解释和报告
  -> 支持继续追问和会话恢复
```

## 项目定位

工业异常检测如果只返回“是否异常”或一个分数，实际使用价值有限。真实质检场景更关心：

- 异常在哪里。
- 异常可能属于什么类型。
- 模型为什么这样判断。
- 是否有相似案例或知识可以参考。
- 检测结果能否继续追问、保存和生成报告。

所以本项目把传统异常检测模型封装为 Agent 工具，再通过 LangGraph 编排视觉检测、知识检索、澄清追问和报告生成流程。项目重点是形成一条可解释、可追踪、可演示的工业异常诊断链路。

## 当前能力

- FastAPI 后端接口和静态前端工作台。
- LangGraph 多 Agent 工作流。
- VisionAgent 视觉异常检测。
- KnowledgeAgent RAG 知识检索和相似案例分析。
- ClarificationAgent 信息不足时生成追问。
- ReportAgent 检测报告生成。
- PatchCore 本地异常检测与热力图输出。
- GRAD 算法 sidecar 服务接入。
- MVTec-AD 标准数据集实验链路。
- 蕾丝数据集转换、GRAD 训练与评估链路。
- 前端展示异常列表、bbox、heatmap、overlay、mask、Agent 时间线和会话记忆。

## 架构总览

当前主链路如下：

```text
web/index.html
  -> app/api/main.py
  -> app/services/task_runner.py 或 app/services/streaming.py
  -> app/core/graph.py
  -> SupervisorAgent
  -> VisionAgent / KnowledgeAgent / ClarificationAgent / ReportAgent
  -> app/tools/*
  -> app/rag/*
  -> app/memory/* 和 runtime store
  -> 返回前端展示
```

目录结构：

```text
MMDL-Agent/
├── app/
│   ├── api/             # FastAPI 接口入口
│   ├── agents/          # Supervisor / Vision / Knowledge / Clarification / Report
│   ├── analysis/        # MMAD 七任务结构化分析
│   ├── config/          # pydantic-settings 配置
│   ├── core/            # LangGraph 工作流
│   ├── memory/          # DetectionState、记忆和 checkpoint
│   ├── orchestration/   # 执行计划、事件时间线、Agent 输出合并
│   ├── rag/             # ChromaDB 向量库、样本检索、知识分析
│   ├── schemas/         # Pydantic 请求/响应模型
│   ├── services/        # detect/chat/continue/report 任务运行层
│   └── tools/           # Qwen、PatchCore、GRAD、专业 HTTP 检测工具
├── services/
│   ├── anomalygpt_local/ # 可选 AnomalyGPT sidecar
│   └── grad_local/       # GRAD sidecar 服务
├── scripts/              # 数据准备、评估、论文辅助脚本
├── tests/                # 自动化测试
├── Docs/                 # 架构、运行、GRAD、交接和论文文档
└── web/                  # 单页前端工作台
```

更完整的架构说明见：

- [Docs/system_overview.md](Docs/system_overview.md)
- [Docs/architecture.md](Docs/architecture.md)
- [Docs/project_handover_introduction.md](Docs/project_handover_introduction.md)

## GRAD 接入设计

GRAD 是老师提供的异常检测算法，原始算法仓库位于服务器：

```text
/root/autodl-tmp/gradcn
```

主项目位于：

```text
/root/autodl-tmp/mmad-agent
```

GRAD 没有被硬编码进主后端，而是封装成独立 sidecar 服务：

```text
MMDL-Agent 主后端
  -> HTTP 调用
  -> GRAD sidecar
  -> gradcn 算法仓库
  -> 返回 anomaly_score、bbox、heatmap、overlay、mask
```

这样设计的原因是 GRAD 有自己的 Python、PyTorch、CUDA、EfficientNet、config 和 checkpoint 依赖。主系统只通过 HTTP JSON 与 GRAD 通信，可以避免因为 CUDA 或 PyTorch 版本问题导致整个主后端无法启动。

关键文件：

```text
services/grad_local/app.py
app/tools/image_anomaly_detection.py
app/tools/grad_detection.py
Docs/grad_sidecar_runbook.md
```

主后端通过这些配置选择 GRAD：

```env
APP_VISION_DETECTOR_BACKEND=grad
APP_GRAD_DETECTOR_URL=http://127.0.0.1:9011/detect
APP_GRAD_DETECTOR_TIMEOUT=180
```

GRAD sidecar 启动后会读取：

```text
GRAD_SERVICE_REPO_DIR
GRAD_SERVICE_CONFIG
GRAD_SERVICE_CHECKPOINT
GRAD_SERVICE_OUTPUT_DIR
GRAD_SERVICE_THRESHOLD
```

蕾丝实验相关路径：

```text
/root/autodl-tmp/all/lace
/root/autodl-tmp/gradcn/data/Lace-AD
/root/autodl-tmp/gradcn/experiments/exp/GRAD/LaceAD/checkpoints/ckpt_best.pth.tar
```

## 快速启动

### 1. 创建 Conda 环境

```powershell
conda create -n MMDL-Agent python=3.12.12
conda activate MMDL-Agent
```

### 2. 安装依赖

```powershell
pip install -e .
```

如果服务器上只需要运行而不是开发，也可以根据实际环境先安装 `requirements` 或项目依赖，再启动服务。

### 3. 配置 `.env`

复制示例配置：

```powershell
Copy-Item .env.example .env
```

本地最小联调推荐：

```env
APP_OPENAI_API_KEY=your_key
APP_CHECKPOINT_BACKEND=memory
APP_VISION_DETECTOR_BACKEND=qwen
```

服务器 GRAD 路线推荐：

```env
APP_CHECKPOINT_BACKEND=memory
APP_OPENAI_API_KEY=your_key
APP_VISION_DETECTOR_BACKEND=grad
APP_GRAD_DETECTOR_URL=http://127.0.0.1:9011/detect
APP_GRAD_DETECTOR_TIMEOUT=180
```

说明：

- `APP_OPENAI_API_KEY` 当前用于兼容 OpenAI 接口的大模型调用。
- `APP_CHECKPOINT_BACKEND=memory` 适合毕业演示和快速联调。
- `APP_CHECKPOINT_BACKEND=postgres` 适合验证持久化 checkpoint，但需要 PostgreSQL。
- `.env` 不应提交到 Git。

## 启动方式

### 模式 A：只启动主后端

适合先验证 API、前端、Agent 和 RAG 主流程。

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

打开前端：

```text
http://127.0.0.1:8000/web/index.html
```

健康检查：

```powershell
curl http://127.0.0.1:8000/v1/system/health
```

### 模式 B：启动 GRAD sidecar + 主后端

适合服务器上验证 GRAD 检测路线。

先启动 GRAD sidecar：

```bash
cd /root/autodl-tmp/mmad-agent
python -m uvicorn services.grad_local.app:app --host 0.0.0.0 --port 9011
```

检查 GRAD：

```bash
curl http://127.0.0.1:9011/health
```

再启动主后端：

```bash
cd /root/autodl-tmp/mmad-agent
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

检查主系统：

```bash
curl http://127.0.0.1:8000/v1/system/health
```

如果返回中 `grad_sidecar.status` 为 `configured`，说明主系统已经识别 GRAD 服务。

## 一次 GRAD 检测示例

```bash
curl -X POST http://127.0.0.1:8000/v1/detect \
  -F "task_id=grad-main-demo" \
  -F "asset_id=bottle-demo" \
  -F "start_time=2026-06-02T00:00:00" \
  -F "end_time=2026-06-02T00:00:00" \
  -F "question=请判断图片是否存在异常，并给出异常位置" \
  -F 'parameters={"tool_type":"grad","require_localization":true,"detector_params":{"category":"bottle","threshold":0.5}}' \
  -F "image=@/root/autodl-tmp/gradcn/data/MVTec-AD/mvtec_anomaly_detection/bottle/test/broken_large/000.png"
```

成功响应中重点看：

```text
anomalies
metadata.selected_backend
metadata.anomaly_score
metadata.heatmap_path
metadata.overlay_path
metadata.mask_path
```

## 视觉后端路由

视觉检测统一入口是：

```text
app/tools/image_anomaly_detection.py
```

当前支持：

| 后端 | 说明 | 关键配置 |
|---|---|---|
| `qwen` | 通用视觉大模型 | `APP_LLM_VISION_MODEL` |
| `patchcore` | 本地 PatchCore 异常定位 | `APP_PATCHCORE_*` |
| `grad` | GRAD sidecar 或本地 GRAD 工具 | `APP_GRAD_DETECTOR_URL` |
| `anomalygpt` / `professional` | 专业 HTTP 视觉检测服务 | `APP_PROFESSIONAL_VISION_DETECTOR_URL` |

单次请求可以通过 `parameters.tool_type` 覆盖默认后端：

```json
{
  "tool_type": "grad",
  "require_localization": true,
  "detector_params": {
    "category": "bottle",
    "threshold": 0.5
  }
}
```

## RAG 与知识库

RAG 由 `app/rag/` 负责，向量库默认写入：

```text
data/rag/chroma
```

常用接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/v1/rag/build` | 同步构建知识库 |
| `POST` | `/v1/rag/build/start` | 异步构建知识库 |
| `GET` | `/v1/rag/build/status/{task_id}` | 查询构建进度 |
| `POST` | `/v1/rag/query` | 文本检索相似案例 |
| `POST` | `/v1/rag/query-image` | 图片路径检索相似案例 |
| `POST` | `/v1/rag/ingest-feedback` | 高置信反馈入库 |

RAG 的作用是给 KnowledgeAgent 提供相似案例、缺陷解释和对象知识，使最终回答不只是视觉模型结果。

## 会话记忆

当前前端支持会话记忆，后端接口包括：

```text
GET    /v1/memory/sessions
POST   /v1/memory/sessions
GET    /v1/memory/sessions/{session_id}
DELETE /v1/memory/sessions/{session_id}
```

实现位置：

```text
app/api/main.py
app/services/industrial_runtime.py
web/index.html
```

它保存检测对话历史、任务 ID、资产 ID、摘要和最近结果，方便用户恢复之前的分析过程。

## 主流程 API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/v1/system/health` | 系统健康检查 |
| `POST` | `/v1/detect` | 首次检测 |
| `POST` | `/v1/stream` | SSE 流式检测 |
| `POST` | `/v1/chat` | 基于已有任务追问 |
| `POST` | `/v1/continue` | 为 pending 任务提交澄清 |
| `GET` | `/v1/pending/{task_id}` | 查询待澄清任务 |
| `POST` | `/v1/generate_report` | 基于已有任务生成报告 |
| `POST` | `/v1/detect_with_report` | 检测并尝试生成报告 |

`/v1/stream` 更适合演示 Agent 时间线，`/v1/detect` 更适合 curl 和脚本验证。

## 测试与检查

常用测试：

```powershell
python -m pytest tests/test_industrial_pilot.py -q
python -m pytest tests/test_image_anomaly_detection_router.py -q
```

Ruff 检查：

```powershell
python -m ruff check app tests scripts
```

完整测试：

```powershell
pytest -q
```

如果只修改文档，可以不运行代码测试，但需要确认 Markdown 可正常读取。

## 重要文档

- [Docs/project_handover_introduction.md](Docs/project_handover_introduction.md)：毕业交接项目介绍。
- [Docs/system_overview.md](Docs/system_overview.md)：系统架构与运行流程。
- [Docs/architecture.md](Docs/architecture.md)：当前活跃架构说明。
- [Docs/runtime_guide.md](Docs/runtime_guide.md)：本地运行、调试和 API 验证。
- [Docs/grad_sidecar_runbook.md](Docs/grad_sidecar_runbook.md)：GRAD sidecar 启动、配置和排障。
- [Docs/mmad_import.md](Docs/mmad_import.md)：MMAD 数据导入说明。
- [Docs/thesis_system_design.md](Docs/thesis_system_design.md)：论文系统总体设计材料。
- [Docs/thesis_chapter5_detailed_design.md](Docs/thesis_chapter5_detailed_design.md)：论文详细设计与实现材料。

## 接手建议

如果是老师或同学第一次接手，建议按这个顺序理解：

1. 先读 `Docs/project_handover_introduction.md`，了解项目整体定位。
2. 再读 `Docs/system_overview.md`，理解分层架构和 Agent 流程。
3. 按 `Docs/runtime_guide.md` 启动主后端和前端。
4. 如果要验证老师给的算法，再按 `Docs/grad_sidecar_runbook.md` 启动 GRAD sidecar。
5. 从一次完整图片检测请求入手，看前端结果、后端日志、Agent 时间线和热力图文件。

后续继续开发时，建议优先做三件事：

- 扩展更多工业类别数据和检测权重。
- 标定 GRAD、PatchCore 等后端的阈值和评估指标。
- 优化 RAG 知识库、Agent 解释和报告生成内容。

## 项目更新流程

后续接手人在更新项目时，建议按下面流程操作，避免把本地数据、模型权重或运行缓存误提交。

### 1. 更新代码前先看本地状态

```bash
git status
```

如果看到 `.env`、`data/`、模型权重、ChromaDB sqlite、热力图输出等运行时文件变化，不要直接提交。先确认这些是否只是本地运行产生的文件。

### 2. 拉取远程最新代码

```bash
git fetch origin
git pull
```

如果需要合并指定分支，例如老师或其他同学提交到了 `tjw` 分支，可以使用：

```bash
git fetch origin tjw
git merge origin/tjw
```

合并时如果出现冲突，优先保留当前主流程的接口结构、配置方式和文档说明，解决后再运行测试。

### 3. 更新依赖

如果 `pyproject.toml`、依赖说明或环境配置发生变化，重新安装项目：

```bash
pip install -e .
```

服务器上如果使用独立 Conda 环境，需要先确认当前环境：

```bash
conda info --envs
```

主项目推荐环境名：

```text
MMDL-Agent
```

GRAD sidecar 可以使用独立环境，不要求和主项目完全一致。

### 4. 检查 `.env`

更新后对比 `.env.example` 和本地 `.env`，确认新增配置已经补齐。常见关键项包括：

```env
APP_OPENAI_API_KEY=
APP_CHECKPOINT_BACKEND=memory
APP_VISION_DETECTOR_BACKEND=grad
APP_GRAD_DETECTOR_URL=http://127.0.0.1:9011/detect
APP_GRAD_DETECTOR_TIMEOUT=180
```

`.env` 只保存在本地或服务器，不要提交到 Git。

### 5. 启动验证

主后端验证：

```bash
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
curl http://127.0.0.1:8000/v1/system/health
```

如果使用 GRAD，先启动 sidecar：

```bash
python -m uvicorn services.grad_local.app:app --host 0.0.0.0 --port 9011
curl http://127.0.0.1:9011/health
```

再启动主后端并检查 `grad_sidecar` 是否为 `configured`。

### 6. 修改后测试

如果修改了后端、Agent、工具或接口，至少运行相关测试：

```bash
python -m pytest tests/test_industrial_pilot.py -q
python -m pytest tests/test_image_anomaly_detection_router.py -q
```

如果只改文档，可以不运行代码测试，但要确认 Markdown 能正常读取、路径没有写错。

### 7. 提交更新

提交前再次确认状态：

```bash
git status
```

只提交代码、文档、配置模板和测试，不提交：

```text
.env
data/rag/chroma/
data/heatmaps/
data/runtime/
models/
*.pth
*.pt
*.ckpt
```

提交信息建议使用中文，并遵循：

```text
type(scope): subject
```

示例：

```bash
git add README.md Docs/
git commit -m "docs(readme): 更新项目交接与运行说明"
git push origin feat/rag
```

## 注意事项

- 不要提交 `.env`、API Key、Token、密码、私钥。
- 不要提交模型权重、大数据集、ChromaDB 运行时索引和热力图缓存。
- `data/` 下多数内容是运行时文件，提交前要确认是否应该进入 Git。
- GRAD 训练环境和主系统环境可以不同，优先通过 sidecar 隔离。
- 修改 API 字段时要同步检查前端、Pydantic schema 和测试。
- 修改核心流程后至少运行相关测试或做一次完整接口验证。
