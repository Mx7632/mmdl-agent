# 工业异常检测 Agent 架构审查报告

**日期**：2026-04-21
**对象**：MMDL 工业异常检测 Agent 架构

## 1. 当前架构概览
目前项目采用基于 FastAPI + LangGraph 的异步架构，核心流程包括：
- **数据加载** (`load_data`)
- **异常检测工具执行** (`anomaly_detect`)：支持视觉 LLM (Qwen) 和外部 HTTP 服务。
- **循环自省逻辑** (`self_reflect` -> `supplement`)：具备基本的置信度评估和补充分析能力。
- **人机协同** (`wait_user`)：支持在置信度不足时挂起任务等待用户澄清。
- **RAG 系统**：已实现基础的向量检索服务，但尚未深度集成。

## 2. 核心缺陷分析

### 2.1 RAG 孤岛化 (RAG Isolation)
- **缺陷**：虽然实现了 `RagService`，但 LangGraph 的各节点（尤其是 `anomaly_detect` 和 `self_reflect`）并未调用 RAG 获取领域知识。
- **影响**：Agent 缺乏对特定工业场景、设备手册或历史故障案例的理解，检测结果仅依赖 LLM 的泛化能力，准确性和专业性受限。

### 2.2 工具编排僵化 (Static Tool Orchestration)
- **缺陷**：`_anomaly_detect_node` 采用静态的逻辑选择工具（基于硬编码的 `tool_type`）。
- **影响**：无法处理复杂的多源数据场景（如同时分析振动传感器数据和红外热像图）。缺乏一个动态的「规划器」来根据任务目标自动选择和编排工具。

### 2.3 缺乏多模态融合 (Missing Multi-Modal Fusion)
- **缺陷**：系统目前将图像分析与传感器数据分析视为独立任务。
- **影响**：无法实现「跨模态关联分析」（例如：传感器检测到的压力异常是否对应图像中看到的阀门渗漏），这是工业复杂诊断的核心需求。

### 2.4 持久化能力不足 (Persistence Gap)
- **缺陷**：`MemoryCheckpointStore` 和 `memory_manager` 目前完全基于内存。
- **影响**：在生产环境下，系统重启会导致所有正在进行的检测任务状态丢失，无法满足工业级长流程监控的可靠性要求。

### 2.5 解释性与报告深度不足 (Explainability)
- **缺陷**：`report` 节点逻辑相对简单，未充分利用自省过程中的推理链（Reasoning Chain）和 RAG 检索到的参考案例。
- **影响**：生成的报告难以给出一线工程师信服的「检测依据」和「维修建议」。

## 3. 改进建议 (Next Steps)

### 3.1 深度集成 RAG (Deep RAG Integration)
- 在 `anomaly_detect` 之前增加 `knowledge_retrieval` 节点。
- 将检索到的领域知识注入 LLM 的 Prompt 中，辅助其识别非通用的工业组件和特定故障模式。

### 3.2 引入智能规划器 (Planner/Router)
- 仿照 ReAct 模式，将 `anomaly_detect` 重构为基于 Tool-Calling 的动态决策过程。
- 允许 Agent 根据任务描述自主决定是否需要先检索文档，再调用传感器 API，最后调用视觉模型。
 
### 3.3 跨模态联合推理 (Cross-Modal Reasoning)
- 增加一个 `fusion_analysis` 节点，专门负责将多源工具的输出进行逻辑对齐。
- 定义统一的工业特征表示（Feature Representation），使不同模态的数据能在同一上下文中被评估。

### 3.4 状态持久化重构 (Production Checkpointing)
- 将 `CheckpointStore` 实现切换为 PostgreSQL 或 Redis。
- 使用 Pydantic 的序列化能力确保 `DetectionState` 能在分布式环境下安全存取。

### 3.5 强化人机协同反馈循环 (Feedback Loop)
- 允许用户在 `wait_user` 阶段纠正 AI 的误报，并将这些纠正信息通过 RAG 系统「在线学习」到本地知识库中，实现 Agent 的持续进化。

---
*本报告由 AI 自动整理，存放在 [Docs/](file:///e:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/Docs/) 目录下。*
