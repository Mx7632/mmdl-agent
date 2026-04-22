# Frontend Documentation

前端已经收敛为单一入口页，围绕最核心的检测流程组织：

1. 上传图片并发起检测
2. 查看初始回答和异常摘要
3. 继续追问或补充人工澄清
4. 基于当前状态生成完整报告

## 当前结构

```text
web/
├── index.html                 # 核心工作台（唯一主入口）
├── detection.html             # 兼容跳转页 -> index.html
├── chat.html                  # 兼容跳转页 -> index.html
├── expert_inspection.html     # 兼容跳转页 -> index.html
├── frontend_chat.html         # 兼容跳转页 -> index.html
├── rag.html                   # 兼容跳转页 -> index.html
└── README.md
```

## 核心页面

### `index.html`

`index.html` 现在是唯一需要用户直接访问的页面，页面包含三块核心动作：

- 发起检测：填写 `asset_id`、问题描述并上传图片，请求 `POST /v1/detect`
- 继续交互：
  - 普通追问走 `POST /v1/chat`
  - 待澄清任务走 `POST /v1/continue`
- 生成报告：请求 `POST /v1/generate_report`

页面右侧统一展示：

- 当前任务状态
- 检测回答
- 异常标签
- 待澄清信息
- 完整报告
- 任务时间线

## 兼容策略

为了避免旧链接失效，以下页面没有直接删除，而是改成 0 秒跳转回 `index.html`：

- `detection.html`
- `chat.html`
- `expert_inspection.html`
- `frontend_chat.html`
- `rag.html`

这意味着：

- 旧书签还能打开
- 旧静态路由不会 404
- 但新的交互只维护 `index.html`

## API 对接

当前前端主流程依赖的后端接口如下：

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/health` | 检查后端是否在线 |
| `POST` | `/v1/detect` | 发起第一轮图片检测 |
| `POST` | `/v1/chat` | 基于已有任务继续追问 |
| `POST` | `/v1/continue` | 为 pending 任务提交人工澄清 |
| `POST` | `/v1/generate_report` | 基于当前任务状态生成完整报告 |

## 本地运行

```bash
# 1. 启动后端
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 2. 打开前端
# 方式一：直接打开 web/index.html
# 方式二：后端启动后访问 http://127.0.0.1:8000/web/index.html
```

## 设计取舍

这次前端收敛有几个明确目标：

- 去掉仪表板、RAG 控制台、专家检测等分散入口
- 避免用户在多个页面之间切换
- 保留最短任务路径，降低使用门槛
- 用跳转页替代删除页，减少兼容性风险

## 后续建议

如果后面还要继续完善，可以考虑：

- 把兼容跳转页策略写进版本更新日志
- 为 `index.html` 增加一次真实浏览器联调验收
- 根据真实使用情况再决定是否保留所有兼容跳转页
