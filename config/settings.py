"""
全局配置 — 模型参数、MCP 服务器参数、文件路径等
"""
import os

from dotenv import load_dotenv

# ============================================================
# 项目根目录
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 加载 .env 文件（位于项目根目录）
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# ============================================================
# 模型配置
# ============================================================
MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.7"))

# 模型回退链 — 按优先级排列，429 限流时自动切换到下一个
# 每个条目的 api_key 默认复用 MODEL_API_KEY 环境变量
_DEFAULT_API_KEY = os.getenv("MODEL_API_KEY", "")

MODEL_FALLBACK_CHAIN: list[dict] = [
    # 1. Qwen2.5-72B: 阿里最强开源模型 (ModelScope 稳定支持)
    # ZhipuAI/GLM-4.7-Flash
    {
        "model": "ZhipuAI/GLM-4.7-Flash",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api_key": _DEFAULT_API_KEY,
        "family": "glm",
        "function_calling": True,
        "json_output": True,
    },
    {
        "model": "Qwen/Qwen2.5-72B-Instruct",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api_key": _DEFAULT_API_KEY,
        "family": "qwen2.5",
        "function_calling": True,
        "json_output": True,
    },
    # 2. Qwen2.5-Coder-32B: 专精代码生成
    {
        "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api_key": _DEFAULT_API_KEY,
        "family": "qwen2.5",
        "function_calling": True,
        "json_output": True,
    },
    # 3. Qwen2.5-32B: 均衡型中等模型
    {
        "model": "Qwen/Qwen2.5-32B-Instruct",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api_key": _DEFAULT_API_KEY,
        "family": "qwen2.5",
        "function_calling": True,
        "json_output": True,
    },
    # 4. Qwen2.5-14B: 最后的兜底
    {
        "model": "Qwen/Qwen2.5-14B-Instruct",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api_key": _DEFAULT_API_KEY,
        "family": "qwen2.5",
        "function_calling": True,
        "json_output": True,
    },
    # 5. Qwen2.5-7B: 极速/极低成本兜底
    {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api_key": _DEFAULT_API_KEY,
        "family": "qwen2.5",
        "function_calling": True,
        "json_output": True,
    },
]

# 模型 429 限流后的冷却时间（秒）
MODEL_COOLDOWN_SECONDS = 60

# 所有模型均限流时的等待重试时间（秒）
MODEL_RETRY_WAIT_SECONDS = 10

# ============================================================
# Figma 配置
# ============================================================
FIGMA_API_KEY = os.getenv("FIGMA_API_KEY", "")

# ============================================================
# MCP 服务器配置（Windows 环境使用 npx.cmd）
# ============================================================
FIGMA_MCP_COMMAND = os.getenv("FIGMA_MCP_COMMAND", "npx.cmd")
FIGMA_MCP_ARGS = ["-y", "figma-developer-mcp", "--stdio"]

BROWSER_MCP_COMMAND = os.getenv("BROWSER_MCP_COMMAND", "npx.cmd")
BROWSER_MCP_ARGS = ["-y", "@playwright/mcp@latest"]

# ============================================================
# 文件路径
# ============================================================
KNOWLEDGE_BASE_PATH = os.path.join(PROJECT_ROOT, "knowledge", "kb_data.json")
GLOBAL_RULES_PATH = os.path.join(PROJECT_ROOT, "rules", "global_rules.json")
CODING_RULES_PATH = os.path.join(PROJECT_ROOT, "rules", "coding_rules.json")

# ============================================================
# 工作流配置
# ============================================================
MAX_REFLECTION_ROUNDS = 3          # 反思循环最大轮次
SIMILARITY_THRESHOLD = 0.70        # 截图相似度阈值
MAX_TOTAL_MESSAGES = 50            # 群聊最大消息数

# ============================================================
# 输出目录
# ============================================================
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
