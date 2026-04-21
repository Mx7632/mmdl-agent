# MMDL-Agent API 接口文档

本文档详细说明了 MMDL-Agent 项目的所有可用接口及其功能，为后续开发和集成提供参考。

---

## 1. 系统基础接口

### 1.1 根路由 (Root)
- **路径**: `GET /`
- **功能**: 检查服务器运行状态，返回应用名称、版本及文档链接。
- **响应示例**:
  ```json
  {
    "app": "industrial-anomaly-agent",
    "version": "0.1.0",
    "message": "后端服务器已经启动成功",
    "docs": "/docs",
    "openapi_schema": "/openapi.json"
  }
  ```

### 1.2 API 文档 (Swagger UI)
- **路径**: `GET /docs`
- **功能**: 提供交互式的 API 测试和说明文档。

---

## 2. RAG（检索增强生成）管理接口
用于管理工业异常知识库，支持向量数据库的构建、查询和在线反馈。

### 2.1 构建 RAG 知识库 (同步)
- **路径**: `POST /v1/rag/build`
- **功能**: 从指定数据集根目录构建向量索引。
- **请求参数 (`RagBuildRequest`)**: 
  - `dataset_root`: 数据集路径 (可选)
  - `include_normal`: 是否包含正常样本 (布尔值)
- **响应**: 包含索引行数、向量数量及统计信息。

### 2.2 启动 RAG 构建任务 (异步)
- **路径**: `POST /v1/rag/build/start`
- **功能**: 异步启动建库任务，立即返回任务 ID。
- **响应**: `task_id`。

### 2.3 查询建库进度
- **路径**: `GET /v1/rag/build/status/{task_id}`
- **功能**: 根据任务 ID 查询异步建库的百分比和当前阶段。

### 2.4 文本检索知识库
- **路径**: `POST /v1/rag/query`
- **功能**: 输入描述性文本，检索最相关的异常案例。
- **请求参数 (`RagQueryRequest`)**: 
  - `query_text`: 查询文本
  - `category`: 类别过滤 (可选)
  - `top_k`: 返回结果数量 (默认 3)

### 2.5 图片检索知识库
- **路径**: `POST /v1/rag/query-image`
- **功能**: 提供图片路径，检索相似的工业异常视觉样本。

### 2.6 异常描述生成 (LLM)
- **路径**: `POST /v1/rag/generate-descriptions`
- **功能**: 调用 LLM 为数据集中的异常样本自动生成文本描述。

### 2.7 在线反馈入库
- **路径**: `POST /v1/rag/ingest-feedback`
- **功能**: 将用户确认的异常样本或修正后的描述实时存入向量库，实现 Agent 的持续学习。

---

## 3. 异常检测核心接口

### 3.1 执行异常检测任务 (同步)
- **路径**: `POST /v1/detect`
- **功能**: 项目核心入口。接收多模态数据，通过 LangGraph 工作流进行检测与诊断。
- **请求方式**: `multipart/form-data`
- **主要参数**:
  - `image`: 上传的图片文件 (可选)
  - `task_id`: 任务标识
  - `asset_id`: 资产标识
  - `start_time`, `end_time`: 监测时间段
  - `question`: 用户针对该检测提出的具体问题 (可选)
  - `parameters`: JSON 字符串，包含额外参数 (如 `tool_type`)
- **执行流程**: 
  1. 解析图片并转换为 Base64。
  2. 构建 `DetectionState`。
  3. 进入 **Planner -> Executor -> Consolidate** 循环工作流。
  4. Planner 根据问题动态决定调用哪些工具（视觉、时序、RAG）。
- **响应 (`DetectionResult`)**: 
  - `status`: success/failed/pending (pending 表示需要用户澄清)
  - `answer`: 诊断结论
  - `anomalies`: 检测到的异常列表

### 3.2 任务续传接口
- **路径**: `POST /v1/continue`
- **功能**: 当 `status=pending` 时，用户提交澄清信息后调用，继续执行工作流。
- **请求参数**: `task_id`, `user_reply`

### 3.3 流式对话接口 (SSE)
- **路径**: `POST /v1/stream`
- **功能**: 实时输出 Agent 的规划过程、工具调用情况和最终回答。
- **请求方式**: `multipart/form-data` (参数同 `/v1/detect`)
- **响应类型**: `text/event-stream`
- **事件类型**:
  - `node_start`: 节点开始（planner, executor 等）
  - `tool_start/end`: 工具执行状态
  - `stream`: 内容流 (subtype: `thought` 或 `answer`)
  - `final_result`: 任务完成标识

### 3.4 报告生成接口
- **路径**: `POST /v1/generate_report`
- **功能**: 基于已有检测结果生成深度技术报告。

---

## 4. 异常处理与追踪
- **Trace ID**: 每个请求都会在 Header 中携带 `X-Trace-Id`。
- **异常响应**: 统一返回结构化 JSON，包含 `code`, `message`, `trace_id`。
