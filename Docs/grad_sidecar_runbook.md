# GRAD Sidecar 与主后端运行手册

本文档说明如何在 AutoDL 服务器上启动 GRAD 推理服务和主项目后端，并完成端到端验证。

## 1. 服务结构

GRAD 与主项目必须使用两个独立 Python 环境，并在两个终端中分别运行：

```text
终端 1: GRAD sidecar
  Python 3.8 + GPU PyTorch
  端口: 9011

终端 2: 主项目 API
  Python 3.11
  端口: 8000
```

默认路径：

```text
GRAD 仓库: /root/autodl-tmp/gradcn
主项目仓库: /root/autodl-tmp/mmad-agent
GRAD 权重: /root/autodl-tmp/gradcn/experiments/exp/GRAD/MVTecAD/checkpoints/ckpt_best.pth.tar
测试图片: /root/autodl-tmp/gradcn/data/MVTec-AD/mvtec_anomaly_detection/bottle/test/broken_large/000.png
```

## 2. 拉取最新代码

```bash
cd /root/autodl-tmp/mmad-agent
git pull origin feat/rag
```

确认 GRAD sidecar 文件存在：

```bash
ls services/grad_local
```

## 3. 初始化主项目 `.env`

首次配置时，复制完整模板：

```bash
cd /root/autodl-tmp/mmad-agent
cp .env.example .env
```

安全地填写 DashScope API Key：

```bash
read -s -p "请输入 DashScope API Key: " API_KEY
echo
sed -i "s|^APP_OPENAI_API_KEY=.*|APP_OPENAI_API_KEY=${API_KEY}|" .env
unset API_KEY
```

检查关键配置，不直接输出 API Key：

```bash
grep -E '^(APP_CHECKPOINT_BACKEND|APP_VISION_DETECTOR_BACKEND|APP_GRAD_DETECTOR_URL|APP_GRAD_DETECTOR_TIMEOUT)=' .env

python - <<'PY'
from pathlib import Path

rows = dict(
    line.split("=", 1)
    for line in Path(".env").read_text().splitlines()
    if "=" in line and not line.startswith("#")
)
key = rows.get("APP_OPENAI_API_KEY", "")
print("APP_OPENAI_API_KEY configured:", bool(key))
print("APP_OPENAI_API_KEY preview:", f"{key[:4]}...{key[-4:]}" if len(key) >= 8 else "missing")
PY
```

关键配置应为：

```env
APP_CHECKPOINT_BACKEND=memory
APP_VISION_DETECTOR_BACKEND=grad
APP_GRAD_DETECTOR_URL=http://127.0.0.1:9011/detect
APP_GRAD_DETECTOR_TIMEOUT=180
```

## 4. 启动 GRAD sidecar

打开终端 1。使用能够训练 GRAD 的 Python 3.8 GPU 环境。

如果当前 shell 无法执行 `conda activate`，先加载 Conda：

```bash
source /root/miniconda3/etc/profile.d/conda.sh
```

如果你为 GRAD 创建过独立环境，例如环境名为 `GRAD`：

```bash
conda activate GRAD
```

如果训练时直接使用 AutoDL 默认环境，则无需切换环境。

确认 GPU 可用：

```bash
python - <<'PY'
import torch
print("torch:", torch.__version__)
print("cuda runtime:", torch.version.cuda)
print("cuda available:", torch.cuda.is_available())
PY
```

启动 GRAD sidecar：

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

保持终端 1 运行。

## 5. 验证 GRAD sidecar

打开一个新的终端执行：

```bash
curl http://127.0.0.1:9011/health
```

预期结果：

```json
{
  "status": "ok",
  "checkpoint_exists": true,
  "cuda_available": true
}
```

进行一次 GRAD 直连推理：

```bash
cd /root/autodl-tmp/mmad-agent

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

r = requests.post("http://127.0.0.1:9011/detect", json=payload, timeout=180)
print("HTTP:", r.status_code)
print(json.dumps(r.json(), ensure_ascii=False, indent=2))
PY
```

成功结果应包含：

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

## 6. 首次创建主项目 Python 3.11 环境

仅首次部署需要执行：

```bash
source /root/miniconda3/etc/profile.d/conda.sh

conda create -n mmol-agent python=3.11 -y
conda activate mmol-agent

cd /root/autodl-tmp/mmad-agent
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
```

主项目会导入 PatchCore 模块，因此即使当前默认使用 GRAD，也需要安装 CPU 版 PyTorch：

```bash
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

## 7. 启动主项目后端

打开终端 2：

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate mmol-agent

cd /root/autodl-tmp/mmad-agent
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

保持终端 2 运行。

检查主项目健康状态：

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

## 8. 端到端调用 GRAD

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

重点检查：

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
      "bbox": [305, 233, 797, 829],
      "has_localization": true
    }
  ]
}
```

查看生成文件：

```bash
ls -lh /root/autodl-tmp/mmad-agent/data/heatmaps/grad/bottle
```

## 9. 日常重启速查

服务器重启后，通常只需开两个终端。

终端 1：GRAD sidecar

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

终端 2：主项目 API

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate mmol-agent

cd /root/autodl-tmp/mmad-agent
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

## 10. 常见问题

### `conda activate` 无法执行

```bash
source /root/miniconda3/etc/profile.d/conda.sh
```

### 主项目报错 `No module named 'torch'`

在主项目 Python 3.11 环境中安装 CPU 版 PyTorch：

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate mmol-agent
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### 主项目报错 `openai_api_key is not configured`

检查 `.env`：

```bash
cd /root/autodl-tmp/mmad-agent
grep '^APP_OPENAI_API_KEY=' .env
```

如果为空，执行本文第 3 节中的 API Key 写入命令，并重启主项目 API。

### 主项目报错 `GRAD detector url not configured`

确认 `.env` 中存在：

```env
APP_GRAD_DETECTOR_URL=http://127.0.0.1:9011/detect
```

### GRAD 报错 `GRAD checkpoint not found`

```bash
echo $GRAD_SERVICE_CHECKPOINT
ls -lh $GRAD_SERVICE_CHECKPOINT
```

### GRAD 报错 `GRAD service requires CUDA`

确认终端 1 使用的是 GRAD GPU 环境：

```bash
python - <<'PY'
import torch
print(torch.cuda.is_available())
PY
```

结果必须为：

```text
True
```
