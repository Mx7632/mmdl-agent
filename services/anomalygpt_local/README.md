# AnomalyGPT 本地服务

这个目录提供的是一个“本机侧车服务”包装层，用来把官方 `AnomalyGPT` 模型包装成当前项目可调用的本地服务。

## 目录作用

- `app.py`: FastAPI 服务入口，暴露 `/health` 和 `/detect`
- `requirements.txt`: 服务壳本身依赖
- `start_service.ps1`: Windows 启动脚本

## 推荐部署方式

不要把 `AnomalyGPT` 直接塞进当前主项目环境。更稳妥的方式是：

1. 单独创建一个 `conda`/`venv` 环境跑 `AnomalyGPT`
2. 在那个环境里安装官方仓库依赖
3. 再额外安装这里的服务壳依赖
4. 启动本地服务，主项目只访问 `127.0.0.1`

## 依据的官方部署信息

官方仓库说明了基础运行流程：

- 克隆仓库并安装 `requirements.txt`
- 准备 `ImageBind`、`Vicuna`、`PandaGPT delta`、`AnomalyGPT` 权重
- 进入 `code/` 目录运行 `python web_demo.py`

我这里做的是在这个基础上，把 `web_demo.py` 里直接加载模型并调用 `model.generate(...)` 的逻辑改造成可复用的本地 API 服务。

官方仓库：

- [AnomalyGPT GitHub](https://github.com/CASIA-LMC-Lab/AnomalyGPT)

## 建议目录

```text
D:\models\AnomalyGPT\
├─ code\
├─ pretrained_ckpt\
└─ requirements.txt
```

## 第一步：准备官方 AnomalyGPT 环境

在单独环境中执行：

```powershell
git clone https://github.com/CASIA-LMC-Lab/AnomalyGPT D:\models\AnomalyGPT
cd D:\models\AnomalyGPT
pip install -r requirements.txt
```

然后按官方 README 放好这些权重：

- `pretrained_ckpt/imagebind_ckpt/imagebind_huge.pth`
- `pretrained_ckpt/vicuna_ckpt/7b_v0/...`
- `pretrained_ckpt/pandagpt_ckpt/7b/pytorch_model.pt`
- `code/ckpt/train_supervised/pytorch_model.pt`

## 第二步：安装本地服务壳

在同一个环境里继续安装：

```powershell
cd E:\Computer\Projects\20_products\anomaly-detection\mmdl-agent
pip install -r services\anomalygpt_local\requirements.txt
```

## 第三步：启动服务

### 方式 A：直接启动

```powershell
$env:ANOMALYGPT_SERVICE_REPO_DIR="D:\models\AnomalyGPT"
python -m uvicorn services.anomalygpt_local.app:app --host 127.0.0.1 --port 9001
```

### 方式 B：使用脚本

```powershell
.\services\anomalygpt_local\start_service.ps1 -RepoDir "D:\models\AnomalyGPT" -Port 9001
```

### 方式 C：使用 Docker

前提：

- 机器上已经安装 Docker Desktop 或 Docker Engine
- GPU 容器可用，`docker run --gpus all ...` 能正常工作
- 本地已经准备好官方 `AnomalyGPT` 仓库和权重

先复制一份 Docker 环境文件：

```powershell
Copy-Item services\anomalygpt_local\.env.docker.example services\anomalygpt_local\.env.docker
```

然后把 `services\anomalygpt_local\.env.docker` 里的 `ANOMALYGPT_REPO_DIR` 改成你的本地仓库目录，比如：

```env
ANOMALYGPT_REPO_DIR=D:/models/AnomalyGPT
```

启动容器：

```powershell
cd services\anomalygpt_local
docker compose --env-file .env.docker up --build -d
```

查看健康状态：

```powershell
docker compose --env-file .env.docker ps
curl http://127.0.0.1:9001/health
```

停止容器：

```powershell
docker compose --env-file .env.docker down
```

## 第四步：配置主项目接入

主项目 `.env` 建议这样配置：

```env
APP_VISION_DETECTOR_BACKEND=anomalygpt
APP_PROFESSIONAL_VISION_DETECTOR_TYPE=anomalygpt
APP_PROFESSIONAL_VISION_DETECTOR_URL=http://127.0.0.1:9001/detect
```

如果你想保留 Qwen 为默认，只在部分请求里切换，则保留：

```env
APP_VISION_DETECTOR_BACKEND=qwen
APP_PROFESSIONAL_VISION_DETECTOR_URL=http://127.0.0.1:9001/detect
```

然后请求里传：

```json
{"tool_type":"anomalygpt"}
```

## 服务接口

### 健康检查

```http
GET /health
```

### 检测接口

```http
POST /detect
Content-Type: application/json
```

请求体示例：

```json
{
  "task_id": "task-001",
  "asset_id": "motor-01",
  "question": "请判断是否有裂纹或破损",
  "image_base64": "<base64>",
  "image_mime": "image/jpeg",
  "detector_type": "anomalygpt",
  "detector_params": {
    "mask_threshold": 0.5,
    "top_p": 0.01,
    "temperature": 1.0,
    "max_tgt_len": 128
  }
}
```

返回体里会包含：

- `answer`
- `summary`
- `anomalies`
- `metadata.localization_mask_base64`

## 已知注意点

- 这个服务默认按官方 `web_demo.py` 的加载方式走 GPU 推理，没做多卡调度。
- 第一次请求会加载大模型，启动会慢。
- `Vicuna`、`PandaGPT delta`、`AnomalyGPT` 权重路径必须和官方目录一致，或者通过环境变量改掉。
- 如果显存紧张，可以先保留当前项目默认走 Qwen，只把 `AnomalyGPT` 作为按需后端。
- Docker 版本默认使用 `nvidia/cuda:11.7.1-cudnn8-runtime-ubuntu22.04`，并在容器内安装官方推理依赖。
- 我这里没有实际替你构建镜像和下载权重，所以如果官方仓库后续依赖变动，可能需要微调 [requirements-official.txt](/E:/Computer/Projects/20_products/anomaly-detection/mmdl-agent/services/anomalygpt_local/requirements-official.txt)。
