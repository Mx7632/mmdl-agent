# GRAD Sidecar 运行与验证手册

本文档说明如何在 AutoDL 服务器上运行已训练好的 GRAD 模型，并通过当前项目调用 `tool_type=grad` 完成图像异常检测。

## 1. 路径约定

下文默认使用以下路径：

```text
GRAD 仓库: /root/autodl-tmp/gradcn
主项目仓库: /root/autodl-tmp/mmad-agent
GRAD 权重: /root/autodl-tmp/gradcn/experiments/exp/GRAD/MVTecAD/checkpoints/ckpt_best.pth.tar
GRAD 数据集: /root/autodl-tmp/gradcn/data/MVTec-AD/mvtec_anomaly_detection
```

如果你的目录不同，替换命令里的路径即可。

## 2. 拉取最新代码

```bash
cd /root/autodl-tmp/mmad-agent
git pull origin feat/rag
```

确认 sidecar 文件存在：

```bash
ls services/grad_local
```

应该能看到：

```text
app.py
requirements.txt
README.md
start_service.sh
```

## 3. 确认 GRAD 权重

```bash
ls -lh /root/autodl-tmp/gradcn/experiments/exp/GRAD/MVTecAD/checkpoints/ckpt_best.pth.tar
```

如果文件不存在，先在 GRAD 仓库里完成训练，或把训练好的 `ckpt_best.pth.tar` 上传到该路径。

## 4. 安装 sidecar 依赖

在能正常运行 GRAD 的 Python 环境中执行：

```bash
cd /root/autodl-tmp/mmad-agent
pip install -r services/grad_local/requirements.txt
```

不要执行：

```bash
pip install .
```

主项目是 Python 3.11 项目，而 GRAD 通常运行在 Python 3.8 环境。sidecar 只需要安装自己的轻量依赖。

## 5. 启动 GRAD sidecar

打开第一个终端：

```bash
cd /root/autodl-tmp/mmad-agent

export PYTHONPATH=/root/autodl-tmp/mmad-agent:/root/autodl-tmp/gradcn:$PYTHONPATH
export GRAD_SERVICE_REPO_DIR=/root/autodl-tmp/gradcn
export GRAD_SERVICE_CONFIG=/root/autodl-tmp/gradcn/experiments/config.yaml
export GRAD_SERVICE_CHECKPOINT=/root/autodl-tmp/gradcn/experiments/exp/GRAD/MVTecAD/checkpoints/ckpt_best.pth.tar
export GRAD_SERVICE_OUTPUT_DIR=/root/autodl-tmp/mmad-agent/data/heatmaps/grad
export GRAD_SERVICE_THRESHOLD=0.5

python -m uvicorn services.grad_local.app:app --host 0.0.0.0 --port 9011
```

保持该终端运行。

## 6. 检查 sidecar 健康状态

打开第二个终端：

```bash
curl http://127.0.0.1:9011/health
```

正常返回应包含：

```json
{
  "status": "ok",
  "checkpoint_exists": true,
  "cuda_available": true
}
```

如果 `checkpoint_exists=false`，检查 `GRAD_SERVICE_CHECKPOINT` 路径。

如果 `cuda_available=false`，切换到 AutoDL 的 GPU PyTorch 环境。

## 7. 直连 sidecar 推理验证

先选一张测试图：

```bash
IMG=/root/autodl-tmp/gradcn/data/MVTec-AD/mvtec_anomaly_detection/bottle/test/broken_large/000.png
```

发送检测请求：

```bash
python - <<'PY'
import base64
import json
import requests

img = "/root/autodl-tmp/gradcn/data/MVTec-AD/mvtec_anomaly_detection/bottle/test/broken_large/000.png"

with open(img, "rb") as f:
    image_base64 = base64.b64encode(f.read()).decode("ascii")

payload = {
    "task_id": "grad-direct-demo",
    "asset_id": "bottle-demo",
    "image_base64": image_base64,
    "image_mime": "image/png",
    "detector_params": {
        "category": "bottle",
        "threshold": 0.5
    }
}

r = requests.post("http://127.0.0.1:9011/detect", json=payload, timeout=120)
print(r.status_code)
print(json.dumps(r.json(), ensure_ascii=False, indent=2))
PY
```

成功返回应包含：

```json
{
  "status": "success",
  "metadata": {
    "selected_backend": "grad",
    "heatmap_path": "...",
    "overlay_path": "...",
    "mask_path": "..."
  }
}
```

查看生成的热力图文件：

```bash
ls -lh /root/autodl-tmp/mmad-agent/data/heatmaps/grad/bottle
```

## 8. 配置主项目调用 GRAD

编辑主项目 `.env`：

```env
APP_GRAD_DETECTOR_URL=http://127.0.0.1:9011/detect
APP_GRAD_DETECTOR_TIMEOUT=120
APP_GRAD_DETECTOR_ALIASES=grad,bi_grid,bi-grid
```

如果希望默认视觉检测后端就是 GRAD：

```env
APP_VISION_DETECTOR_BACKEND=grad
```

如果只想单次请求使用 GRAD，则可以保留原默认后端，在请求参数中传：

```json
{"tool_type":"grad"}
```

## 9. 启动主项目 API

打开第三个终端：

```bash
cd /root/autodl-tmp/mmad-agent
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

检查主项目是否识别 GRAD：

```bash
curl http://127.0.0.1:8000/v1/system/health
```

返回中应包含：

```json
"grad_sidecar": {
  "status": "configured",
  "url": "http://127.0.0.1:9011/detect"
}
```

## 10. 通过主项目完整调用

```bash
curl -X POST http://127.0.0.1:8000/v1/detect \
  -F "task_id=grad-main-demo" \
  -F "asset_id=bottle-demo" \
  -F "start_time=2026-05-21T00:00:00" \
  -F "end_time=2026-05-21T00:00:00" \
  -F "question=请判断图片是否存在异常，并给出异常位置" \
  -F 'parameters={"tool_type":"grad","require_localization":true,"detector_params":{"category":"bottle","threshold":0.5}}' \
  -F "image=@/root/autodl-tmp/gradcn/data/MVTec-AD/mvtec_anomaly_detection/bottle/test/broken_large/000.png"
```

重点检查返回：

```json
{
  "status": "success",
  "metadata": {
    "selected_backend": "grad",
    "detector_type": "grad"
  },
  "anomalies": [
    {
      "type": "surface_anomaly",
      "bbox": [0, 0, 10, 10],
      "has_localization": true
    }
  ]
}
```

## 11. 常见问题

### 缺少 `services/grad_local/requirements.txt`

说明服务器代码不是最新的：

```bash
cd /root/autodl-tmp/mmad-agent
git pull origin feat/rag
```

### `TypeError: Unable to evaluate type annotation 'str | None'`

说明服务器没有拉到 Python 3.8 兼容修复：

```bash
cd /root/autodl-tmp/mmad-agent
git pull origin feat/rag
```

确认当前提交不早于：

```text
876261b fix(grad): support python 3.8 sidecar typing
```

### `GRAD detector url not configured`

主项目 `.env` 缺少：

```env
APP_GRAD_DETECTOR_URL=http://127.0.0.1:9011/detect
```

修改 `.env` 后需要重启主项目 API。

### `GRAD checkpoint not found`

检查：

```bash
echo $GRAD_SERVICE_CHECKPOINT
ls -lh $GRAD_SERVICE_CHECKPOINT
```

### `GRAD service requires CUDA`

当前 Python 环境无法使用 GPU。检查：

```bash
python - <<'PY'
import torch
print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
PY
```

`torch.cuda.is_available()` 必须为 `True`。

### 主项目能启动，但调用超时

第一次请求会加载 GRAD 模型，可能较慢。建议：

```env
APP_GRAD_DETECTOR_TIMEOUT=120
```

并先用 `/health` 与 sidecar 直连 `/detect` 验证模型加载正常。
