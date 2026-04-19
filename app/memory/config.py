# 基础路径配置，适配LangGraph项目根目录
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 记忆数据本地存储路径
MEMORY_STORE_PATH = os.path.join(BASE_DIR, "data/memory")
# 自动创建目录，避免运行报错
os.makedirs(MEMORY_STORE_PATH, exist_ok=True)

# 记忆过期时间配置
WORKING_MEMORY_EXPIRE = 30       # 短期工作记忆（分钟）
TOOL_CONTEXT_EXPIRE = 5         # 工具上下文记忆（分钟）
SHORT_TERM_MEMORY_EXPIRE = 7    # 中期记忆（天数）【优化新增】
LONG_TERM_MEMORY_EXPIRE = -1    # 长期记忆，永不过期

# 缓存大小限制
MAX_WORKING_MEMORY = 500
MAX_SHORT_TERM = 200            # 中期记忆最大条数【优化新增】
LONG_TERM_COMPRESS_THRESHOLD = 5  # 超过此条同 asset_id 记录时触发压缩【优化新增】

# 长期记忆压缩后存档路径
MEMORY_ARCHIVE_PATH = os.path.join(MEMORY_STORE_PATH, "archive")
os.makedirs(MEMORY_ARCHIVE_PATH, exist_ok=True)

# LangGraph智能体配置
AGENT_TASK_PREFIX = "agent_task_"  # 任务ID前缀
DEFAULT_USER_ID = "student_user"   # 默认用户ID
