# MMDL-Agent

一个用于构建多模态/多步骤智能代理（Agent）的框架，集成 LangChain + LangGraph，提供工业级异常处理、记忆管理与工具调用能力。

---

<a id="architecture"></a>

## 🏗️ 项目架构

```
MMDL-Agent/
├── main.py                       # FastAPI 启动入口
├── pyproject.toml                # 项目依赖与构建配置
├── README.md                     # 项目说明文档
├── TESTING.md                    # 测试与 CI 说明
├── tests/                        # 自动化测试用例
│   ├── test_api.py               # API 层测试
│   ├── test_agent.py             # Agent 与工作流测试
│   ├── test_memory.py            # 记忆与检查点测试
│   └── test_exceptions.py        # 异常体系测试
├── web/                          # 前端 Web 界面
│   ├── index.html                # 仪表板主页
│   ├── detection.html            # 检测任务表单页
│   └── assets/                   # 静态资源（CSS/JS）
└── app/                          # 核心后端框架
    ├── api/
    │   └── main.py              # HTTP 路由与中间件
    ├── config/
    │   └── settings.py          # 全局配置（模型、日志、超时等）
    ├── core/
    │   ├── agent.py             # Agent 核心类与执行逻辑
    │   └── graph.py             # LangGraph 工作流定义
    ├── exceptions/
    │   └── base.py              # 统一异常体系（AppError + 子类）
    ├── memory/
    │   ├── state.py             # 执行状态与上下文
    │   └── checkpoint.py        # 检查点与持久化
    ├── prompts/
    │   └── README.md            # 提示词模板说明
    ├── schemas/
    │   └── detection.py         # 数据模型（Pydantic）
    ├── tools/
    │   └── image_anomaly_detection.py # 异常检测工具实现
    └── utils/
        └── logging.py           # 日志与追踪工具
```

---

## 🛠️ 本地开发环境

### 前置要求

- **Python 3.11+**（Anaconda/Conda）
- **Git**
- **pip**（或 conda）

### 快速开始

#### 1. 克隆项目

```bash
git clone https://github.com/Xhr313/MMDL-Agent.git
cd MMDL-Agent
```

#### 2. 创建并激活 Python 虚拟环境

如果使用 **Anaconda**：

```bash
conda create -n MMDL-Agent python=3.12.12 #创建虚拟环境
conda activate MMDL-Agent #激活虚拟环境
```

或使用 **venv**：

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

#### 3. 安装项目依赖

```bash
pip install -e .
```

或者只安装必要的运行依赖：

```bash
pip install fastapi uvicorn pydantic pydantic-settings python-dotenv langchain langgraph httpx orjson
```

#### 4. 启动 FastAPI 应用

```bash
python -m uvicorn main:app --reload
```

**预期输出：**

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started server process [12345]
INFO:     Application startup complete
```

#### 5. 验证服务运行

打开浏览器或使用 curl 验证：

```bash
# 根路由（欢迎页面）
curl http://127.0.0.1:8000/
```

**返回示例：**
```json
{
  "app": "industrial-anomaly-agent",
  "version": "0.1.0",
  "message": "后端服务器已经启动成功",
  "docs": "/docs",
  "openapi_schema": "/openapi.json"
}
```
---

## 📋 核心模块说明

| 模块 | 职责 | 关键文件 |
|-----|------|--------|
| **API 层** | HTTP 路由、中间件、异常转换 | `app/api/main.py` |
| **Agent 核心** | 执行流程、状态管理、工具调用 | `app/core/agent.py` |
| **LangGraph** | 工作流定义与执行 | `app/core/graph.py` |
| **异常体系** | 统一异常处理与上下文追踪 | `app/exceptions/base.py` |
| **记忆管理** | 执行状态与检查点持久化 | `app/memory/state.py`, `app/memory/checkpoint.py` |
| **数据模型** | 请求/响应 Pydantic Schema | `app/schemas/detection.py` |
| **日志工具** | 追踪 ID、结构化日志 | `app/utils/logging.py` |
| **测试套件** | 单元测试与集成测试 | `tests/`, `TESTING.md` |
| **Web 前端** | 可视化仪表板与表单 | `web/index.html`, `web/detection.html`, `web/assets/*` |

### 异常体系

项目提供**结构化异常**便于错误处理与追踪：

- `AppError`: 基础异常类（包含 `details`、`original_error`、HTTP 状态码）
- `ModelError`: 模型调用失败
- `ToolError` / `ToolNotFoundError` / `ToolExecutionError`: 工具相关错误
- `ContextError` / `TokenLimitError`: 上下文与 Token 限制
- `MaxTurnsError`: 执行轮次超限
- `ResponseParseError`: 响应解析失败
- `ConfigurationError`: 配置错误
- `StreamError`: 流式处理错误

<a id="detection-algorithm"></a>

### 异常检测算法流（概览）

- 客户端或 Web 前端向 `POST /v1/detect` 提交检测任务，请求体会被解析为 `DetectionTask`（见 `app/schemas/detection.py`）。
- Agent 调用在 `app/tools/image_anomaly_detection.py` 中注册的检测工具。
- 工具返回 `DetectionResult`，其中包含任务状态、异常列表、摘要与元数据，最终被封装为标准 API 响应返回给调用方。

---

## 🚀 开发工作流

### 新增 API 端点

1. 在 `app/schemas/detection.py` 定义请求/响应数据模型
2. 在 `app/api/main.py` 添加路由处理函数
3. 在 `app/core/agent.py` 实现业务逻辑

### 新增工具或模型

1. 在 `app/tools/` 新建工具模块
2. 在 `app/core/agent.py` 注册工具到 Agent
3. 补充单元测试

### 日志与调试

使用 `app/utils/logging.py` 的统一日志接口：

```python
from app.utils.logging import setup_logger

logger = setup_logger(trace_id="custom-trace-id")
logger.info("Processing task")
logger.error("Task failed", extra={"task_id": "123"})
```

### Web 前端

- `web/` 目录提供纯静态 Web 前端，用于与后端 API（如 `/health`、`/v1/detect`）进行交互。
- 推荐使用任意静态文件服务器或 IDE 插件（如 VS Code Live Server）打开 `web/index.html` 进行调试。
- 更详细的前端结构与使用说明见 `web/README.md`。

---

## 🧪 测试与代码检查

```bash
# 安装开发依赖
pip install pytest ruff mypy

# 运行测试
pytest

# 代码风格检查与修复
ruff check --fix

# 类型检查
mypy app/
```

> 更完整的测试说明（覆盖率、并行运行、CI 集成等）请参考docs下的 `TESTING.md`。

---

## 📖 API 示例

### 1. 异常检测

```bash
POST http://127.0.0.1:8000/v1/detect
Content-Type: application/json

{
  "task_id": "task-001",
  "data": [...],
  "threshold": 0.5
}
```

---

## 🐛 常见问题

| 问题 | 解决方案 |
|------|--------|
| `ModuleNotFoundError: No module named 'uvicorn'` | 运行 `pip install uvicorn fastapi` |
| 端口被占用 | 更换端口 `python -m uvicorn main:app --port 8001` |
| Conda 环境激活失败 | 使用 `conda init` 初始化 shell |

---

## 📝 文件说明

- `main.py`: 应用入口（引入 FastAPI 实例）
- `pyproject.toml`: 项目元信息、依赖声明、工具配置
- `app/config/settings.py`: 应用全局配置（模型、超时、日志等）
- `app/api/main.py`: FastAPI 实例创建、路由注册、中间件配置

---

## 🚀 v2 新增内容（2026-04）

### 架构升级：链式流程 → 两阶段图

原始链式流程（`load_data → anomaly_detect → summarize`）已重构为两阶段：

| 阶段 | 状态 | 说明 |
|------|------|------|
| 循环自检图 | 已实现，未启用 | MAX_LOOP=3，置信度<0.7 或 unknown 触发循环，长期记忆参与决策 |
| 对话图 | **当前使用** | 先回答，可多轮 chat，点击按钮触发报告生成 |

### 新增后端文件

| 文件 | 作用 |
|------|------|
| `app/core/answer_node.py` | 对话回答节点（只回答，不生成报告） |
| `app/core/self_reflect.py` | 自检节点（循环图用） |
| `app/core/wait_user.py` | 人工澄清节点 |
| `app/core/supplement.py` | 补充分析节点 |
| `app/core/__init__.py` | 节点模块导出 |
| `app/core/agent.py` | 新增 `run_chat()`、`generate_report()` 方法 |
| `app/memory/state.py` | 新增 `report_requested`、`loop_count`、`reflection_decision` 等字段 |
| `app/memory/memory_manager.py` | 记忆管理器（新增） |
| `app/memory/models.py` | 记忆数据模型（新增） |
| `app/memory/config.py` | 记忆配置（新增） |
| `app/memory/LRU_cache.py` | LRU 缓存（新增） |
| `app/memory/utils.py` | 记忆工具函数（新增） |
| `app/memory/__init__.py` | 记忆模块导出 |

### 新增 API 端点

| 端点 | 方法 | 作用 |
|------|------|------|
| `/v1/detect` | POST | 上传图片+问题，返回简洁回答（无报告） |
| `/v1/chat` | POST | 多轮对话，基于已有检测状态 |
| `/v1/generate_report` | POST | 基于已有状态生成完整报告 |
| `/v1/detect_with_report` | POST | 检测+报告一次性返回（可选） |

### 前端聊天界面（`frontend_chat.html`）

新增独立前端，完整交互流程：

```
上传图片 → 开始检测（/v1/detect）
    → AI 返回答案 + 内嵌异常标签
    → 用户可多轮提问（/v1/chat）
    → 点击「📄 生成报告」（/v1/generate_report）
        → loading 动画
        → 报告卡片插入聊天记录 ✅（可反复点击查看）
        → 侧边栏滑出查看完整报告
    → 关闭侧边栏可继续聊天
```

**侧边栏特性：** backdrop 遮罩、右侧滑入动画、Esc 键关闭、Markdown 渲染、异常置信度标签。

### 已知待改进项

- `settings.py` 中 API Key 为硬编码，存在泄露风险，建议迁移至环境变量或密钥管理服务
- 目前仅支持 `qwen3.5-plus` 模型
- 记忆模块可进一步优化：语义搜索、记忆分层压缩、工具效果追踪、向量数据库集成

### 本地运行

```bash
# 1. 进入项目目录
cd D:\Graduation_project\MMDL

# 2. 激活虚拟环境
conda activate mmdl-agent

# 3. 启动后端
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 4. 打开前端（任选一种）
# 方式一：直接在浏览器打开 frontend_chat.html
# 方式二：后端启动后访问 http://127.0.0.1:8000/frontend_chat.html

# 5. API 测试
# 检测（无报告）
curl -X POST http://127.0.0.1:8000/v1/detect \
  -F "task_id=test-001" \
  -F "asset_id=asset-001" \
  -F "start_time=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -F "end_time=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -F "question=这张图片有什么异常？" \
  -F "image=@C:/Users/simmer/Pictures/Camera Roll/anomaly.jpg"

# 生成报告
curl -X POST http://127.0.0.1:8000/v1/generate_report \
  -H "Content-Type: application/json" \
  -d '{"task_id": "test-001"}'
```

### Git 操作说明

```bash
# 查看当前变更
git status

# 添加所有变更（含新文件）
git add .

# 提交（填写自己的信息）
git commit -m "feat: 重构为对话图架构，新增聊天前端和报告侧边栏"

# 推送到远程
git push origin main
```

---
