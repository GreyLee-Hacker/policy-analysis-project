import os
import sys
import logging
import requests
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from openai import OpenAI

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_available_models():
    """检查可用的模型列表"""
    
    api_key = os.getenv("API_KEY", "sk-5ccc48320e3341b6b273861358dffdec")
    
    # 检查阿里云模型
    try:
        logger.info("正在检查阿里云可用模型...")
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        models = client.models.list()
        
        logger.info("阿里云可用模型:")
        for model in models.data:
            logger.info(f"- {model.id}")
        
        logger.info("推荐在代码中使用以下模型:")
        logger.info('models = ["qwen-turbo", "qwen-plus", "qwen-max"]')
        
    except Exception as e:
        logger.error(f"检查阿里云模型时出错: {str(e)}")
    
    # 检查百度模型（如果有API密钥）
    baidu_api_key = os.getenv("BAIDU_API_KEY")
    baidu_secret_key = os.getenv("BAIDU_SECRET_KEY")
    
    if baidu_api_key and baidu_secret_key:
        try:
            logger.info("正在检查百度文心可用模型...")
            # 获取百度访问令牌
            token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={baidu_api_key}&client_secret={baidu_secret_key}"
            response = requests.post(token_url)
            access_token = response.json().get("access_token")
            
            if access_token:
                logger.info("百度文心模型可用:")
                logger.info("- ERNIE-Bot-4")
                logger.info("- ERNIE-Bot")
                logger.info("- ERNIE-Bot-turbo")
                
                logger.info("推荐在代码中使用以下百度模型:")
                logger.info('models = ["ernie-bot-4", "ernie-bot", "ernie-bot-turbo"]')
            else:
                logger.error("无法获取百度访问令牌")
        except Exception as e:
            logger.error(f"检查百度模型时出错: {str(e)}")
    
    # 检查ChatGLM本地模型
    chatglm_url = os.getenv("CHATGLM_URL", "http://0.0.0.0:8002/chat")
    try:
        logger.info(f"正在检查本地ChatGLM模型 ({chatglm_url})...")
        response = requests.post(
            chatglm_url, 
            json={"prompt": "hello", "history": []}, 
            timeout=5
        )
        if response.status_code == 200:
            logger.info("本地ChatGLM模型可用")
            logger.info("推荐在代码中使用:")
            logger.info('models = ["chatglm-local"]')
        else:
            logger.warning(f"本地ChatGLM模型不可用: {response.status_code}")
    except Exception as e:
        logger.warning(f"本地ChatGLM模型不可用: {str(e)}")
    
    # 如果有OpenAI API密钥，也检查OpenAI模型
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        try:
            logger.info("正在检查OpenAI模型...")
            client = OpenAI(
                api_key=openai_api_key
            )
            
            models = client.models.list()
            
            logger.info("OpenAI可用模型:")
            for model in models.data:
                logger.info(f"- {model.id}")
            
            logger.info("推荐在代码中使用以下OpenAI模型:")
            logger.info('models = ["gpt-3.5-turbo", "gpt-4"]')
        except Exception as e:
            logger.error(f"检查OpenAI模型时出错: {str(e)}")

if __name__ == "__main__":
    check_available_models()
