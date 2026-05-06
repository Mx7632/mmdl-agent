# 系统架构与运行流程

本文档说明当前 MMDL-Agent 的系统架构、主运行链路、多 Agent 分工、RAG 知识库、PatchCore 热力图和 MMAD 七任务分析如何协同工作。

## 1. 系统定位

当前系统是一个面向工业视觉异常诊断的多 Agent 应用框架。它不是由单个模型直接给出结论，而是通过 LangGraph 编排多个专家 Agent：

```text
API / 前端
  -> LangGraph 工作流
  -> Supervisor 规划
  -> 专家 Agent 执行
  -> 共享上下文合并
  -> 自反 / 澄清 / 回答 / 报告
```

核心能力包括：

- 图像异常检测
- PatchCore 热力图定位
- RAG 相似案例检索
- MMAD 七任务结构化分析
- 多轮追问
- 人工澄清
- 诊断报告生成
- 多 Agent 执行时间线观测

## 2. 分层架构

当前主要代码分层如下：

```text
app/api
  FastAPI 接口层，负责 /v1/detect、/v1/stream、/v1/chat、/v1/rag/* 等入口。

app/services
  任务运行层，负责 detect/chat/continue/report 的状态恢复、流式输出、最终响应组装。

app/core
  LangGraph 图定义和节点逻辑，包括 graph、answer、self_reflect、wait_user。

app/orchestration
  多 Agent 编排层，包括执行计划、step 状态、事件时间线、merge adapters、共享上下文。

app/agents
  专家 Agent 层，包括 SupervisorAgent、VisionAgent、KnowledgeAgent、ClarificationAgent、ReportAgent。

app/tools
  工具层，包括 Qwen、AnomalyGPT、PatchCore 图像异常检测。

app/rag
  知识库层，包括数据集扫描、文本生成、向量库、检索、知识分析。

app/analysis
  分析协议层，目前包含 MMAD 七任务分析和 MMAD 官方数据导入。

app/memory
  记忆与状态层，包括 DetectionState、短期/长期记忆、checkpoint。

web
  单页前端工作台，负责上传图片、发起检测、展示热力图、多 Agent 时间线和分析结果。
```

## 3. 主运行流程

一次检测的主流程如下：

```text
1. 用户在前端上传图片 / 输入问题
2. 前端调用 /v1/stream 或 /v1/detect
3. API 构造 DetectionTask
4. services 启动 LangGraph
5. load_data 加载任务数据
6. supervisor_plan 决定要调用哪些专家 Agent
7. supervisor_execute 执行专家 Agent
8. supervisor_merge 合并专家输出
9. self_reflect 判断结果是否足够可靠
10. 如果信息不足，进入 wait_user 等待人工澄清
11. 如果信息足够，进入 answer 生成最终中文诊断
12. 用户可以继续追问或生成报告
```

对应的运行链路是：

```text
web/index.html 或 HTTP client
  -> app/api/main.py
  -> app/services/task_runner.py 或 app/services/streaming.py
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

## 4. 多 Agent 分工

### SupervisorAgent

主控 Agent。它根据任务状态、用户问题、图像输入和已有结果决定下一步调用哪些专家。

常见决策：

- 有新图像时，优先调用 `VisionAgent`
- 需要成因、风险、相似案例时，调用 `KnowledgeAgent`
- 置信度不足或异常类型不清楚时，调用 `ClarificationAgent`
- 用户要求报告时，调用 `ReportAgent`

### VisionAgent

视觉异常检测 Agent。它调用图像检测工具，输出异常候选、定位信息和后端元数据。

可选视觉后端：

- `qwen`
- `anomalygpt`
- `patchcore`

### KnowledgeAgent

知识检索和结构化分析 Agent。它基于 RAG 检索相似案例，并生成：

- `defect_analysis`
- `object_analysis`

这些内容会进入最终回答、报告和 MMAD 七任务分析。

### ClarificationAgent

澄清 Agent。当系统无法可靠判断时，它生成待人工确认的问题，例如：

```text
请确认异常是否位于图像右下角？
```

任务会进入 pending 状态，等待用户通过 `/v1/continue` 补充信息。

### ReportAgent

报告 Agent。它复用当前检测结果、RAG 知识、MMAD 七任务分析和对话历史，生成完整诊断报告。

## 5. 状态模型

系统核心状态是 `DetectionState`。它保存：

```text
task
result
shared_context
agent_outputs
agent_trace
execution_plan
step_status
step_attempts
execution_events
conversation_history
conversation_summary
```

当前推荐通过三个运行视图访问状态：

```text
task_runtime()
  任务输入、对话历史、报告请求、阶段状态。

orchestration_runtime()
  执行计划、重试次数、step 状态、挂起/恢复控制。

domain_runtime()
  检测结果、共享上下文、工具输出、Agent 输出。
```

这样可以把任务输入、编排状态和领域结果分开，避免所有逻辑都直接读写顶层状态字段。

## 6. 共享上下文

专家 Agent 的结果会进入 `shared_context`：

```text
shared_context.vision
  anomalies
  metadata
  answer

shared_context.knowledge
  defect_analysis
  object_analysis
  prompt_context

shared_context.mmad_analysis
  anomaly_discrimination
  defect_classification
  defect_localization
  defect_description
  defect_analysis
  object_classification
  object_analysis

shared_context.clarification
  pending_question
  requires_human

shared_context.report
  summary
  metadata
```

`shared_context.mmad_analysis` 是当前对齐 MMAD 论文七大任务的统一结构化输出。

## 7. RAG 知识库链路

RAG 不是每次强制执行，而是由 Supervisor 根据任务意图和上下文规划。

知识库构建链路：

```text
MVTec 数据集
  -> DatasetAnalyzer 扫描样本
  -> AnomalyTextGenerator 生成文本描述
  -> VectorStore 写入 Chroma
  -> KnowledgeAgent 检索相似案例
  -> FewShotSelector 筛选正常/异常案例
  -> FewShotPromptBuilder 构造少样本上下文
  -> knowledge_pipeline 生成缺陷分析和产品分析
```

运行时如果调用 `KnowledgeAgent`，它会检索相似案例，并生成：

- 可能成因
- 风险提示
- 建议动作
- 相似案例
- 产品结构
- 功能影响

这些输出会进入：

- `metadata.analysis_contracts`
- `shared_context.knowledge`
- `shared_context.mmad_analysis`
- 最终回答
- 报告生成

当前 KnowledgeAgent 的 RAG 内部链路是：

```text
KnowledgeAgent
  -> RAG 检索相似异常案例
  -> RAG 检索少样本候选，包括正常和异常案例
  -> FewShotSelector 平衡选择正常/异常案例
  -> FewShotPromptBuilder 生成 few_shot_context
  -> knowledge_pipeline 合成 prompt_context
  -> 输出 defect_analysis / object_analysis
```

`few_shot_context` 会被追加到 `shared_context.knowledge.prompt_context` 中，最终进入 answer/report prompt。这样最终诊断既能参考相似异常，也能参考正常样本边界，减少把正常结构误判成缺陷的风险。

## 8. PatchCore 热力图链路

PatchCore 是当前本地热力图后端。它分为训练和推理两步。

训练阶段：

```text
MVTec train/good
  -> patchcore_train.py
  -> memory_bank.pt
  -> metadata.json
```

推理阶段：

```text
待检测图片
  -> 提取 patch embedding
  -> 与 memory bank 计算距离
  -> 得到 anomaly score map
  -> 生成 heatmap / overlay / mask
  -> 提取 bbox / location / appearance
  -> 返回 VisionAgent
```

输出文件：

```text
data/heatmaps/{category}/{task_id}_heatmap.png
data/heatmaps/{category}/{task_id}_overlay.png
data/heatmaps/{category}/{task_id}_mask.png
```

API 静态挂载：

```text
/data/heatmaps
```

前端可以展示：

- 原图
- BBox
- Heatmap
- Overlay

热力图不仅用于显示，也会进入：

```text
metadata.heatmap_path
metadata.overlay_path
metadata.mask_path
mmad_analysis.defect_localization
```

## 9. MMAD 七任务分析

当前系统已经新增 MMAD 七任务统一协议：

```text
anomaly_discrimination
defect_classification
defect_localization
defect_description
defect_analysis
object_classification
object_analysis
```

生成位置：

```text
supervisor_merge
  -> build_mmad_analysis_context
  -> shared_context.mmad_analysis
  -> result.metadata.mmad_analysis
```

作用：

- 将 VisionAgent 和 KnowledgeAgent 的输出归一化
- 让前端有稳定展示结构
- 让后续评测模块可以直接读取
- 避免视觉失败时被错误解释为正常
- 对齐 MMAD 论文中的工业异常理解任务定义

## 10. 流式时间线

如果走 `/v1/stream`，前端会实时收到：

```text
execution_plan
step_status
step_attempts
execution_events
agent_trace
```

因此前端可以展示：

- Supervisor 规划了哪些 Agent
- 哪个 Agent 开始执行
- 哪个 Agent 成功或失败
- 是否发生重试
- 是否进入 pending
- 最终结果是什么

这条时间线主要用于长任务排障和多 Agent 执行过程观测。

## 11. 一句话总结

当前主线是：

```text
检测图片
  -> 多 Agent 判断
  -> 视觉定位
  -> RAG 解释
  -> MMAD 七任务归一化
  -> 中文诊断 / 报告
```

系统已经从单次异常检测接口升级为：

```text
多 Agent 编排
+ 视觉检测
+ PatchCore 热力图
+ RAG 知识分析
+ MMAD 七任务结构化输出
+ 多轮追问
+ 报告生成
+ 前端时间线可观测
```
