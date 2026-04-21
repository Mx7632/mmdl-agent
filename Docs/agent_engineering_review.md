# 标准 Agent 工程架构评估与优化建议

## 背景

本文从“标准 Agent 工程”的角度，对当前项目架构进行评估，并结合 Claude Code 一类通用 Agent 产品的使用体验，分析当前系统还缺少哪些关键能力，以及哪些点最值得优先优化。

这里的“标准 Agent 工程”不只是指：

- 能调用模型
- 能调用工具
- 能跑通一条 ReAct 链路

而是指一个可持续演进、可调试、可观测、可评测、可恢复、可扩展上线的 Agent 系统工程。

## 当前项目的已有基础

当前项目已经具备一个 Agent 工程的核心雏形，主要包括：

- 基于 LangGraph 的流程图编排
- `planner -> executor -> consolidate -> self_reflect -> answer` 的主链路
- 多轮对话状态管理
- 工具抽象与工具调用
- RAG 检索能力
- 工作记忆 / 中短期 / 长期记忆设计
- 流式输出与非流式输出双通道

这些能力说明项目已经不是“单次调用 LLM 的应用”，而是一个初步具备 Agent 形态的系统。

但从标准工程化视角看，当前仍更接近：

“能工作的业务型 Agent 应用”

而不是：

“可扩展、可运营、可维护的标准 Agent 工程平台”

## 从 Claude Code 使用者视角的判断标准

如果以 Claude Code 这类 Agent 产品的重度使用者视角来判断，一个标准 Agent 工程通常需要同时具备以下能力：

- 每轮任务都能独立规划、执行、反思、产出结果
- 工具调用有统一协议、上下文和错误语义
- 每次运行都可回放、可审计、可定位问题
- 会话状态、运行状态和工具结果能够持久化
- 有评测体系，可以验证修改是否带来退化
- 有权限控制和安全边界，不会因为工具扩展导致系统失控
- 有清晰的工程分层，方便后续继续增加新 Agent、新工具和新场景

按这个标准看，当前项目主干方向是对的，但平台层和工程层还不够完整。

## 当前架构还缺少的关键能力

### 1. 缺少统一的 Agent Runtime 层

当前项目已经有 LangGraph 流程，但它更像“业务流程图”，还不是完整的“Agent Runtime”。

目前缺少的 Runtime 能力包括：

- 对一次 Agent run 的统一抽象
- run 生命周期管理
- step 级事件模型
- 可中断 / 可取消 / 可重试机制
- 统一 artifact 输出规范
- 回放与审计入口

也就是说，现在系统的核心是“图能跑起来”，但不是“运行时标准已经建立起来”。

在标准 Agent 工程里，通常会有一个明显的 Runtime 层，负责承接：

- 当前任务是什么
- 当前处于哪一轮
- 已经调用了哪些工具
- 工具输出是什么
- 当前是否需要用户澄清
- 最终产出了哪些结果和工件

而这些能力当前大多还散落在 graph、state 和接口逻辑中。

### 2. 缺少持久化运行状态与 durable checkpoint

当前多轮对话依赖内存型 checkpoint：

- `app/memory/checkpoint.py`

这会带来几个明显限制：

- 服务重启后会话丢失
- 无法恢复历史任务
- 无法回放一次失败的 Agent run
- 无法审计“为什么 planner 选择了这个工具”
- 无法对线上问题进行可重复分析

这类设计适合开发验证，不适合标准 Agent 工程。

标准做法应该是把以下信息落库：

- run
- run_event
- checkpoint
- conversation_turn
- tool_call
- tool_result
- artifact

至少应该先具备“服务重启后状态不丢失”。

### 3. 工具层协议还不够平台化

当前工具已经做了抽象，这一步是对的。但目前仍然偏“可用”，还不够“平台级”。

当前还缺少的工具层能力包括：

- 统一超时控制
- 工具级重试策略
- 幂等语义
- 风险等级标注
- side effects 标注
- 工具权限边界
- 工具版本管理
- 工具输出标准化 schema

未来一旦工具变多，或者接入文件系统、外部服务、执行环境，缺少这些能力会很快成为系统瓶颈。

### 4. 缺少系统化评测机制

当前项目有单测，但标准 Agent 工程最重要的并不是普通单测，而是行为评测。

目前明显缺少这类评测：

- 某个问题 planner 是否选对工具
- 工具调用顺序是否合理
- 新 Prompt 是否让规划退化
- 新模型是否导致工具误调
- 相同问题在改造前后是否变差
- 多轮上下文注入后回答是否更稳

如果没有 eval harness，后续每次改 planner、executor、prompt、tool schema，都会进入“改完只能靠体感验证”的状态。

这对 Agent 工程是非常危险的。

### 5. 缺少完整的可观测性与回放能力

当前项目已有 trace id 和 logs，但从 Agent 工程视角还远远不够。

建议具备的可观测性包括：

- 每轮 run 的 step timeline
- planner 原始输出
- tool call 参数快照
- tool result 摘要
- token 用量
- latency
- 模型版本
- prompt 版本
- 错误类型与恢复策略
- replay 入口

Claude Code 一类产品之所以可维护，一个很重要的原因是它们不是只输出“答案”，而是能观察完整运行轨迹。

当前项目还缺这部分。

### 6. 缺少权限模型与安全边界

当前系统的工具都是低风险工具，所以问题还不明显。

但如果未来扩展到：

- 文件系统读写
- 外部 API 调用
- 远程执行
- shell / Python 执行
- 数据写入

那必须引入：

- 工具风险等级
- 用户确认节点
- 审批机制
- 只读 / 可写权限边界
- 高危工具隔离策略

标准 Agent 工程必须尽早建立这条边界，否则后面很难补。

### 7. 缺少多 Agent / 专用 Agent 的演进空间

当前系统的主干是一个单 Agent 图。

这对当前场景足够，但如果目标是标准 Agent 工程，后面通常会演进出：

- 对话 Agent
- 检索 Agent
- 报告 Agent
- 批处理 Agent
- 诊断 Agent

也就是说，未来更合理的形态可能不是“所有事情都塞到一个 graph 里”，而是：

- Runtime 负责编排
- 多个专用 Agent 负责不同子能力

当前项目还没有为这种扩展形态留出明显结构空间。

## 当前最值得优先优化的点

### 1. 先做 durable state 与持久化 checkpoint

这是优先级最高的优化项。

建议第一步先把以下信息持久化：

- 任务基本信息
- 当前 state
- conversation history
- tool calls
- tool outputs
- run logs

哪怕先使用 SQLite / PostgreSQL，也会比纯内存方案更接近标准工程。

这是所有后续能力的基础：

- 回放
- 恢复
- 调试
- 审计
- 评测

都依赖它。

### 2. 抽出独立的 Runtime 层

建议把当前“业务图逻辑”和“运行时管理逻辑”分离开。

理想方向是拆成两层：

- Runtime 层  
  负责 run、event、checkpoint、tool execution、retry、trace、artifact

- Domain 层  
  负责工业异常检测场景中的 planner policy、tool policy、memory policy

这样后续新增别的 Agent 时，不需要复制整套架构。

### 3. 把工具系统做成注册中心

当前工具通过 `get_industrial_tools()` 返回，是可以工作的。

但更适合长期扩展的做法是建立 tool registry，管理：

- tool name
- description
- input schema
- output schema
- risk level
- timeout
- retry policy
- required context
- supported mode

这样 planner 不只是“看到几个工具名”，而是能获得完整的工具元数据。

### 4. 提升 executor 的执行控制能力

当前 executor 能工作，但还比较基础。

后续建议增强：

- 并行执行工具
- 单工具 timeout
- retry policy
- cancellation
- circuit breaker
- 工具结果归一化

这会明显提升工程稳定性和执行效率。

### 5. Prompt 与模型配置需要版本化

当前 planner prompt、reflect prompt 主要是代码内常量。

这在早期阶段可以接受，但不利于长期迭代。

建议引入：

- prompt registry
- prompt version
- model version
- run 时记录使用的 prompt/model 版本

否则后续无法回答这些问题：

- 为什么这个版本规划退化了
- 是模型变了还是 prompt 变了
- 哪个版本的回答质量最好

### 6. 配置与密钥管理需要立刻收紧

当前 `app/config/settings.py` 里存在默认 API key，这在标准工程里风险很高。

建议立即改为：

- 代码内不出现真实 key
- 缺失 key 时启动报错
- 区分 dev / test / prod 环境
- 引入更明确的配置校验机制

这是工程化和安全性上的必修项。

### 7. 返回结构需要统一为 run result 模型

当前不同接口返回结构略有差异：

- detect
- chat
- continue
- stream
- generate_report

从业务角度没问题，但从标准 Agent 工程角度，建议统一为：

- run metadata
- messages
- tool traces
- artifacts
- final answer
- report summary

统一返回结构后，前端、日志、回放、评测会容易很多。

### 8. 建立失败恢复策略

当前异常处理更多还是“日志 + fallback”。

建议把失败类型分层：

- planner failed
- tool failed
- parser failed
- reflect failed
- model unavailable
- permission denied
- timeout

然后对每类失败定义策略：

- 是否重试
- 是否降级
- 是否中断
- 是否需要用户确认

这是标准 Agent 工程的重要组成部分。

## 当前代码中可以直接优化的具体点

### 1. `RagService` 的使用方式可以统一

当前工具层里知识检索工具直接实例化 `RagService()`，而不是统一通过单例入口管理。

建议统一通过服务获取函数管理实例，避免：

- 重复初始化
- 向量库状态不一致
- 资源浪费

### 2. planner / executor 与 domain policy 耦合较重

当前 planner prompt、工具优先级策略、图像优先判断等逻辑都写在同一处。

可以进一步拆开：

- 通用 planner runner
- 工业领域 policy
- 工具选择策略

这样后续如果切到别的业务场景，不需要重写 planner 核心逻辑。

### 3. event / log 的粒度需要提升

当前 logs 足够看流程，但不够做生产级问题定位。

建议事件化记录：

- planner_started
- planner_finished
- tool_selected
- tool_started
- tool_finished
- tool_failed
- reflection_finished
- answer_generated

这会比纯文本 logs 更适合做查询、分析和 UI 展示。

### 4. 缺少 artifact 概念

当前系统输出主要是：

- answer
- anomalies
- summary

标准 Agent 工程通常还会有 artifact 概念，比如：

- 检索上下文片段
- 结构化诊断报告
- 工具执行结果快照
- 可下载报告
- 中间分析结果

这对后续产品化很重要。

## 一个更标准的目标架构方向

如果目标是把当前项目进一步做成标准 Agent 工程，建议朝这个分层演进：

```text
app/
  api/                # HTTP / SSE 接口层
  runtime/            # Agent Runtime：run、checkpoint、event、trace、retry
  agents/             # 各类 Agent 定义：chat、diagnosis、report
  graphs/             # LangGraph 编排定义
  tools/              # 具体工具实现
  tool_registry/      # 工具注册与元数据
  prompts/            # Prompt 模板与版本管理
  memory/             # Working/Short/Long memory
  storage/            # DB、checkpoint、artifact 存储
  evals/              # Agent 行为评测
  observability/      # tracing、metrics、replay
  policies/           # 领域策略、权限策略、安全策略
```

这不是要求一次性重构完成，而是建议作为中长期目标目录结构。

## 推荐的实施优先级

建议按下面顺序推进：

### 第一阶段：先补工程底座

1. 持久化 checkpoint 和 run state
2. 去掉代码中的默认敏感配置
3. 统一 run 返回结构
4. 增强 step 级事件日志

### 第二阶段：补运行时能力

1. 抽出 runtime 层
2. 工具注册中心
3. 工具执行策略统一化
4. Prompt / model 版本记录

### 第三阶段：补质量体系

1. 建 eval harness
2. 建回放能力
3. 建 regression case 集
4. 接入 metrics 与 trace

### 第四阶段：补平台扩展性

1. 风险工具权限模型
2. 子 Agent / 专用 Agent 架构
3. artifact 管理
4. 更完整的任务调度与异步 worker

## 总结

当前项目已经具备一个 Agent 工程的核心雏形：

- 有图编排
- 有工具调用
- 有多轮状态
- 有反思节点
- 有记忆层

这是非常好的基础。

但如果目标是“标准 Agent 工程”，当前最缺的不是 Agent 思路，而是以下三类能力：

- 平台层：runtime、storage、tool registry、permissions
- 工程层：observability、evals、replay、versioning
- 运营层：durable state、审计、恢复、配置安全

一句话概括：

当前系统已经是一个“能工作的 Agent 应用”，  
下一步要补的是“把它做成一个真正可持续演进的 Agent 工程平台”。

