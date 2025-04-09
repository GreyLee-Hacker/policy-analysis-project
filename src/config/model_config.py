"""
模型配置文件
用于配置可用的模型和API密钥
"""

import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent

# API密钥配置
# 优先使用环境变量中的API密钥，如果没有则使用默认值
API_KEYS = {
    "alicloud": os.getenv("API_KEY", ""),
    "openai": os.getenv("OPENAI_API_KEY", ""),
    "baidu_api_key": os.getenv("BAIDU_API_KEY", ""),
    "baidu_secret_key": os.getenv("BAIDU_SECRET_KEY", ""),
}

# filepath: /home/greylee/Projects/Policy_2024_12/policy-analysis-project/src/config/model_config.py
MODEL_ENDPOINTS = {
    "model_chatglm": os.getenv("CHATGLM_URL", "http://0.0.0.0:8002/chat"),
    "model_alicloud": "https://dashscope.aliyuncs.com/api/v1",  # 修改为标准API端点
    "model_baidu": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
    "model_openai": "https://api.openai.com/v1"
}

# 可用模型配置
AVAILABLE_MODELS = {
    "alicloud": [
        "qwen-turbo",
        "qwen-plus",
        "qwen-max",
        "qwen-72b-chat",
        "qwen2-7b-instruct",
        "qwen2-72b-instruct",
        "deepseek-r1",
        "qwen-long",
        "deepseek-v3"
    ],
    "openai": [
        "gpt-3.5-turbo",
        "gpt-4"
    ],
    "baidu": [
        "ernie-bot-4",
        "ernie-bot",
        "ernie-bot-turbo"
    ],
    "local": [
        "chatglm-local"
    ]
}

# 按优先级排列的默认模型
DEFAULT_MODELS = [
    "qwen-turbo",
    "qwen-plus",
    "qwen-max",
    "qwen-72b-chat",
    "qwen2-7b-instruct",
    "qwen2-72b-instruct",
    "deepseek-r1",
    "qwen-long",
    "deepseek-v3",
    "ernie-bot" if API_KEYS["baidu_api_key"] and API_KEYS["baidu_secret_key"] else None,
    "gpt-3.5-turbo" if API_KEYS["openai"] else None,
    "chatglm-local" if os.path.exists(MODEL_ENDPOINTS["model_chatglm"]) else None
]

# 过滤掉None值
DEFAULT_MODELS = [model for model in DEFAULT_MODELS if model is not None]

# 如果没有可用模型，则至少使用qwen-turbo
if not DEFAULT_MODELS:
    DEFAULT_MODELS = ["qwen-turbo"]
