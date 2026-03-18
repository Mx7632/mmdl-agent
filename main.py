from app.api.main import app

__all__ = ["app"]

# 切环境:conda activate pytorch（自己环境的命名）
# 终端运行: uvicorn main:app --reload