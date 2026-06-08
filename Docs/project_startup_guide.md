# MMDL-Agent 项目启动指南

这份文档只说明项目如何启动。更完整的架构、交接和算法说明可以看 `README.md`、`Docs/system_overview.md` 和 `Docs/grad_sidecar_runbook.md`。

## 1. 启动前准备

进入项目目录：

```bash
cd /root/autodl-tmp/mmad-agent
```

如果是在本地 Windows：

```powershell
cd E:\Computer\Projects\20_products\anomaly-detection\mmdl-agent
```

确认 Conda 环境：

```bash
conda info --envs
```

主项目推荐环境名：

```text
MMDL-Agent
```

如果当前 shell 不能直接使用 `conda activate`，可以先执行：

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate MMDL-Agent
```

AutoDL 上如果环境名是实际创建时的其他名字，例如 `mmol-agent`，就激活实际存在的环境。

## 2. 检查 `.env`

项目启动前必须确认 `.env` 存在：

```bash
ls -la .env .env.example
```

如果没有 `.env`，从示例复制：

```bash
cp .env.example .env
```

本地快速联调最小配置：

```env
APP_OPENAI_API_KEY=your_key
APP_CHECKPOINT_BACKEND=memory
APP_VISION_DETECTOR_BACKEND=qwen
```

服务器 GRAD 路线推荐配置：

```env
APP_OPENAI_API_KEY=your_key
APP_CHECKPOINT_BACKEND=memory
APP_VISION_DETECTOR_BACKEND=grad
APP_GRAD_DETECTOR_URL=http://127.0.0.1:9011/detect
APP_GRAD_DETECTOR_TIMEOUT=180
```

检查关键配置：

```bash
grep -E '^(APP_OPENAI_API_KEY|APP_CHECKPOINT_BACKEND|APP_VISION_DETECTOR_BACKEND|APP_GRAD_DETECTOR_URL|APP_GRAD_DETECTOR_TIMEOUT)=' .env
```

注意：`.env` 不能提交到 Git。

## 3. 安装或刷新依赖

第一次启动或代码更新后执行：

```bash
pip install -e .
```

如果只是文档更新，通常不需要重新安装依赖。

## 4. 启动方式 A：只启动主后端

适合先验证前端、API、Agent 和 RAG 主流程，不依赖 GRAD。

```bash
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

本地开发也可以使用：

```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/v1/system/health
```

前端访问：

```text
http://127.0.0.1:8000/web/index.html
```

## 5. 启动方式 B：GRAD sidecar + 主后端

适合验证老师给的 GRAD 算法和蕾丝/MVTec 实验路线。

需要开两个终端。

### 终端 1：启动 GRAD sidecar

进入主项目目录：

```bash
cd /root/autodl-tmp/mmad-agent
```

如果使用默认 MVTec 配置：

```bash
python -m uvicorn services.grad_local.app:app --host 0.0.0.0 --port 9011
```

如果使用蕾丝 LaceAD 配置，可以在启动前设置环境变量：

```bash
export GRAD_SERVICE_REPO_DIR=/root/autodl-tmp/gradcn
export GRAD_SERVICE_CONFIG=/root/autodl-tmp/gradcn/experiments/config_lace_eval.yaml
export GRAD_SERVICE_CHECKPOINT=/root/autodl-tmp/gradcn/experiments/exp/GRAD/LaceAD/checkpoints/ckpt_best.pth.tar
export GRAD_SERVICE_OUTPUT_DIR=/root/autodl-tmp/mmad-agent/data/heatmaps/grad
export GRAD_SERVICE_THRESHOLD=0.5

python -m uvicorn services.grad_local.app:app --host 0.0.0.0 --port 9011
```

检查 GRAD sidecar：

```bash
curl http://127.0.0.1:9011/health
```

正常情况下会看到：

```json
{
  "status": "ok",
  "checkpoint_exists": true,
  "cuda_available": true
}
```

### 终端 2：启动主后端

确保 `.env` 中配置：

```env
APP_VISION_DETECTOR_BACKEND=grad
APP_GRAD_DETECTOR_URL=http://127.0.0.1:9011/detect
```

启动主后端：

```bash
cd /root/autodl-tmp/mmad-agent
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

检查主系统：

```bash
curl http://127.0.0.1:8000/v1/system/health
```

如果返回里有：

```json
"grad_sidecar": {
  "status": "configured",
  "url": "http://127.0.0.1:9011/detect"
}
```

说明主后端已经连上 GRAD sidecar。

## 6. 发送一次检测请求

MVTec bottle 示例：

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

蕾丝示例需要把图片路径换成 Lace-AD 测试集图片，并把 category 改成实际使用的类别，例如：

```bash
curl -X POST http://127.0.0.1:8000/v1/detect \
  -F "task_id=grad-lace-demo" \
  -F "asset_id=lace-demo" \
  -F "start_time=2026-06-02T00:00:00" \
  -F "end_time=2026-06-02T00:00:00" \
  -F "question=请判断这张蕾丝样本是否存在异常，并给出异常位置" \
  -F 'parameters={"tool_type":"grad","require_localization":true,"detector_params":{"category":"lace","threshold":0.5}}' \
  -F "image=@/root/autodl-tmp/gradcn/data/Lace-AD/mvtec_anomaly_detection/lace/test/你的测试图片.png"
```

成功响应重点看：

```text
status
answer
anomalies
metadata.selected_backend
metadata.anomaly_score
metadata.heatmap_path
metadata.overlay_path
metadata.mask_path
```

## 7. 前端演示流程

浏览器打开：

```text
http://服务器IP:8000/web/index.html
```

或本机：

```text
http://127.0.0.1:8000/web/index.html
```

前端操作顺序：

1. 上传工业图片。
2. 填写问题，例如“请判断图片是否存在异常，并给出异常位置”。
3. 选择或填写检测参数。
4. 点击检测。
5. 查看异常结果、热力图、overlay、mask 和 Agent 时间线。
6. 如有需要，继续追问或生成报告。

## 8. 常见问题

### 8.1 `No module named 'torch'`

说明当前环境没有安装 PyTorch，或者没有激活正确 Conda 环境。先确认：

```bash
which python
python -c "import torch; print(torch.__version__)"
```

主后端如果只通过 HTTP 调用 GRAD，理论上不需要在主环境强制加载 GRAD 的 torch；但某些健康检查或本地检测工具可能仍会触发相关依赖。

### 8.2 `openai_api_key is not configured`

说明 `.env` 中没有配置：

```env
APP_OPENAI_API_KEY=your_key
```

如果只是验证 GRAD 直接检测，也尽量先配置这个 key，避免 Agent 或回答生成阶段失败。

### 8.3 `grad_sidecar` 不是 `configured`

检查 `.env`：

```bash
grep -E '^(APP_VISION_DETECTOR_BACKEND|APP_GRAD_DETECTOR_URL)=' .env
```

确认：

```env
APP_VISION_DETECTOR_BACKEND=grad
APP_GRAD_DETECTOR_URL=http://127.0.0.1:9011/detect
```

同时确认 sidecar 已启动：

```bash
curl http://127.0.0.1:9011/health
```

### 8.4 GRAD checkpoint 不存在

检查：

```bash
ls -lh /root/autodl-tmp/gradcn/experiments/exp/GRAD/LaceAD/checkpoints/ckpt_best.pth.tar
```

如果文件不存在，需要先完成训练或把权重放到对应路径。

### 8.5 端口被占用

查看端口：

```bash
lsof -i:8000
lsof -i:9011
```

可以换端口启动，但 `.env` 中的 `APP_GRAD_DETECTOR_URL` 要同步改。

## 9. 停止服务

在对应终端按：

```text
Ctrl+C
```

如果是后台运行，需要根据实际进程管理方式停止，例如 `ps`、`kill`、`tmux` 或 AutoDL 控制台。
