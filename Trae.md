# AI 交互工作约束指南

本文档旨在明确 AI 在参与本项目（工业异常检测 Agent）开发时的行为准则、技术规范及工作流约束。在进行开发时，严格遵守以下规则：

## 1. 核心上下文约束
- **项目目标**：专注于工业异常检测，开发并维护用于检测工业过程异常的智能化 Agent。
- **环境管理**：强制使用 **Conda** 进行环境管理，环境名称约定为 `MMDL-Agent`。
- **Python 版本**：强制使用 **Python 3.12.12**。
- **编码**：所有代码文件必须使用 **utf-8** 编码。

## 2. 技术栈选型规范
- **后端框架**：统一使用 **FastAPI**。
- **Agent 框架**：核心逻辑必须基于 **LangChain** 和 **LangGraph** 构建。
- **数据校验**：使用 **Pydantic V2** 定义所有 Data Schemas。
- **配置管理**：使用 `pydantic-settings`。环境变量需以 `APP_` 为前缀（如 `APP_LOG_LEVEL`）。
- **向量数据库**：选用 **ChromaDB**，主要用于 RAG 功能。

## 3. 目录结构约束
AI 在创建或修改文件时，必须严格遵守以下目录划分：
- [app/](file:///e:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/app/): 核心后端逻辑（API、Agent 编排、RAG 服务、Prompts 等）。
- [web/](file:///e:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/web/): 前端静态资源（HTML/JS/CSS）。
- [data/](file:///e:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/data/): 向量索引（Chroma）及运行时上传的数据（Images/Logs）。
- [tests/](file:///e:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/tests/): 单元测试与集成测试。
- [Docs/](file:///e:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/Docs/): 项目文档、技术指南及 AI 自动生成的总结。

## 4. 编码与质量约束
- **代码风格**：
  - 使用 **Ruff** 进行 Lint 和格式化。
  - 单行代码长度限制为 **100** 字符。
- **类型安全**：所有 Python 代码必须包含类型标注，并确保通过 **Mypy** 检查。
- **日志与追踪**：
  - 必须集成 `trace_id` 链路追踪。
  - 异步函数中需正确传递上下文，确保日志在并发请求下可追溯。

## 5. 文档自动化工作流
- **自动整理**：在每次重要的 AI 问答、复杂功能实现或架构调整结束后，AI 应主动或在请求下将关键结论、接口变更或技术方案整理成 Markdown 文档。
- **存放路径**：所有自动生成的文档应存放于 [Docs/](file:///e:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/Docs/) 目录下。
- **文档命名**：采用 `YYYY-MM-DD-Topic.md` 或具描述性的名称（如 `api_docs.md`）。

## 6. 交互原则
- **优先复用**：在实现新功能前，优先搜索现有的 `utils` 或 `core` 模块，避免重复造轮子。
- **参数解耦**：在编写工具（Tools）时，利用 `executor_node` 的参数自动注入机制（如 `task_id`, `image_base64` 等），保持工具调用的简洁性。
- **主动验证**：完成代码修改后，应主动运行 [tests/](file:///e:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/tests/) 中的相关测试或创建临时脚本验证逻辑。
- **渐进式改进**：保持代码的向后兼容性，对核心逻辑的重大改动需在文档中说明理由。

## 7. 提交规范
- **及时提交**：每次完成一个模块的开发或修复后，应及时提交到当前分支，以中文语言提交。
- **标准格式**：采用 **Git Commit Message 标准**，即 `type(scope): subject`。
  - `type`：提交类型，如 `feat`（新功能）、`fix`（修复）、`docs`（文档）等。
  - `scope`：影响范围，如 `app`、`core`、`web`、`api` 等。
  - `subject`：简洁明了的提交描述。
- **PR 描述**：在发起 Pull Request 时，简要描述变更内容、实现逻辑以及对最终用户的影响。