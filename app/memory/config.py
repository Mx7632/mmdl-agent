# 基础路径配置，适配LangGraph项目根目录
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 记忆数据本地存储路径
MEMORY_STORE_PATH = os.path.join(BASE_DIR, "data/memory")
# 自动创建目录，避免运行报错
os.makedirs(MEMORY_STORE_PATH, exist_ok=True)

# 记忆过期时间配置（分钟）
WORKING_MEMORY_EXPIRE = 30    # 短期工作记忆
TOOL_CONTEXT_EXPIRE = 5       # 工具上下文记忆
LONG_TERM_MEMORY_EXPIRE = -1  # 长期记忆，永不过期

# 缓存大小限制
MAX_WORKING_MEMORY = 500

# LangGraph智能体配置
AGENT_TASK_PREFIX = "agent_task_"  # 任务ID前缀
DEFAULT_USER_ID = "student_user"   # 默认用户ID
