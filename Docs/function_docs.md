# 工业异常检测代理 (Industrial Anomaly Agent) 功能文档 (最终版)
本项目是一个基于 FastAPI 和 LangGraph 构建的智能代理，旨在对工业设备的时序数据进行异常检测，并利用大型语言模型（LLM）对检测结果进行分析和总结。它包含一个完整的 Web 用户界面用于交互。

## 一、项目根目录
文件/目录 作用 main.py 项目主入口文件 。负责启动 Uvicorn 服务器，加载并运行 FastAPI 应用。 app/ 核心应用目录 。包含了项目所有的后端逻辑，是项目的核心。 tests/ 测试目录 。包含对项目各个模块的单元测试和集成测试。 web/ 前端静态资源目录 。存放与用户界面相关的 HTML、CSS 和 JavaScript 文件。 pyproject.toml 项目配置文件 。定义了项目依赖、构建系统和其他元数据。 .gitignore Git 忽略文件 。告诉 Git 哪些文件或目录不需要纳入版本控制。 README.md 项目说明文件 。提供项目的基本介绍、安装和使用指南。

## 二、核心应用 (app/)
### 2.1 API 服务 (app/api/) app/api/main.py
- 作用 : FastAPI 应用的 主文件 ，定义了所有的 API 端点、中间件和异常处理器。
- 核心功能 :
  - CORS 中间件 : 允许跨域资源共享，使得前端页面可以调用后端 API。
  - Trace ID 中间件 : 为每个进入的请求附加一个唯一的 trace_id ，并将其注入日志上下文，便于链路追踪和问题排查。
  - 全局异常处理器 : 捕获应用中抛出的自定义 AppError 异常，并将其转换为统一格式的 JSON 错误响应返回给客户端。
- API 端点 :
  - GET / : 根路径，返回应用的基本信息和文档链接。
  - GET /health : 健康检查端点，用于监控服务是否正常运行。
  - POST /v1/detect : 核心业务接口 。接收一个 DetectionTask 对象，触发 LangGraph 工作流执行异常检测，并最终返回 DetectionResult 。
### 2.2 配置 (app/config/) app/config/settings.py
- 作用 : 定义和管理整个应用的配置。它使用 pydantic-settings 库，可以从环境变量或 .env 文件中加载配置，实现了配置与代码的分离。
- 核心类 :
  - Settings : 一个 Pydantic 模型，集中管理所有配置项。
### 2.3 核心逻辑 (app/core/) app/core/graph.py
- 作用 : 定义了使用 LangGraph 构建的异常检测工作流（Graph）中的所有核心节点。
- 核心函数 (异步节点) :
  - load_data_node : 校验输入数据。
  - anomaly_detect_node : 执行异常检测。
  - summarize_node : 调用 LLM 生成总结。
### 2.4 状态管理 (app/memory/) app/memory/state.py
- 作用 : 定义了 LangGraph 工作流的状态模型 DetectionState ，用于在节点间传递数据。
### 2.5 数据模型 (app/schemas/) app/schemas/detection.py
- 作用 : 使用 Pydantic 定义了项目核心业务的数据结构。
- 核心类 :
  - DetectionTask : 检测任务的输入模型。
  - DetectionResult : 检测任务的输出模型。
  - ToolResponse : 工具执行的统一响应模型。
### 2.6 功能工具 (app/tools/) app/tools/anomaly_detection.py
- 作用 : 提供了异常检测的具体实现工具。
- 核心类 :
  - BaseTool : 工具的抽象基类。
  - MockAnomalyDetectionTool : 用于测试的模拟工具。
  - HttpAnomalyDetectionTool : 通过 HTTP 调用外部服务的工具。
### 2.7 提示模板 (app/prompts/) app/prompts/summarize.py
- 作用 : 存放用于与 LLM 交互的提示模板 SUMMARIZE_PROMPT 。
### 2.8 工具库 (app/utils/) app/utils/logging.py
- 作用 : 提供日志记录和链路追踪相关的工具函数。
### 2.9 异常处理 (app/exceptions/) app/exceptions/base.py
- 作用 : 定义了整个应用统一的、结构化的异常体系，所有自定义异常都继承自 AppError 。
## 三、前端 (web/)
### 3.1 HTML 页面 web/index.html
- 作用 : 仪表盘 (Dashboard) 页面。这是应用的主页，提供了系统状态概览、快速统计、快捷操作和最近检测历史等功能。
- 主要功能 :
  - 显示系统健康状态（在线/离线）。
  - 统计最近任务数、发现的异常总数和成功率。
  - 提供“开始新检测”、“查看历史”和“下载报告”的快捷按钮。
  - 以列表形式展示最近的检测任务记录，并支持查看详情和删除。 web/detection.html
- 作用 : 新建检测任务 页面。提供一个表单，让用户可以配置并提交一个新的异常检测任务。
- 主要功能 :
  - 一个详细的表单，用于输入任务 ID、资产 ID、时间范围、检测数据等。
  - 支持手动输入数据（逗号分隔或 JSON 数组）。
  - 提供一个阈值滑块，用于调整检测灵敏度。
  - 提交表单后，会调用后端 API 执行检测，并以卡片形式在当前页面展示详细的检测结果，包括异常点、LLM 生成的总结和元数据。
### 3.2 JavaScript 脚本 (web/assets/js/) web/assets/js/api-client.js
- 作用 : API 客户端模块 。封装了与后端 FastAPI 服务的所有 HTTP 通信。
- 核心功能 :
  - APIClient 类: 提供了 request , checkHealth , runDetection 等方法，用于发起网络请求。
  - 工具函数 : 包含 parseDataInput (解析用户输入的数据), formatDateTime (格式化日期), generateTaskId (生成唯一任务ID) 等多个前端辅助函数。 web/assets/js/dashboard.js
- 作用 : 仪表盘页面的主逻辑 。负责 index.html 页面的所有动态交互和数据管理。
- 核心功能 :
  - 页面加载时，检查系统健康状态并从 localStorage 加载最近的检测历史。
  - 动态更新统计数据（任务数、异常数等）。
  - 渲染最近检测列表，并处理查看详情、删除记录等交互。
  - 实现“下载报告”功能，将检测历史导出为 CSV 文件。 web/assets/js/detection-form.js
- 作用 : 新建检测页面的主逻辑 。负责 detection.html 页面的表单处理和结果展示。
- 核心功能 :
  - 为表单元素（如提交按钮、阈值滑块）绑定事件监听器。
  - 在提交前对表单数据进行校验。
  - 调用 api-client.js 中的方法，将检测任务发送到后端。
  - 控制加载状态（Loading 动画）的显示和隐藏。
  - 将后端返回的检测结果动态渲染成结果卡片。
  - 将成功完成的检测任务保存到 localStorage ，以便在仪表盘页面显示。