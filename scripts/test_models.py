#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试特定模型的可用性
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv
import logging

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.services.llm_service import LLMService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("model_test.log", encoding="utf-8")
    ]
)

logger = logging.getLogger("model_test")

def load_env_variables():
    """加载环境变量"""
    # 尝试加载.env文件
    load_dotenv()
    return os.getenv("API_KEY", "")

def test_model_direct(model_name, api_key):
    """直接使用原生API测试模型"""
    logger.info(f"开始使用原生API测试模型: {model_name}")
    
    # 映射模型名称到API需要的模型ID
    model_mapping = {
        "baichuan2-7b-chat": "Baichuan2-7B-Chat",
        "baichuan2-13b-chat": "Baichuan2-13B-Chat",
        "llama2-7b-chat": "Llama-2-7b-chat",
        "llama2-13b-chat": "Llama-2-13b-chat"
    }
    
    actual_model_id = model_mapping.get(model_name, model_name)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": actual_model_id,
        "input": {
            "messages": [
                {"role": "system", "content": "你是一个助手。"},
                {"role": "user", "content": "你好，请简短介绍一下自己。"}
            ]
        },
        "parameters": {
            "temperature": 0.1,
            "top_p": 0.7,
            "max_tokens": 1000
        }
    }
    
    try:
        response = requests.post(
            "https://dashscope.aliyuncs.com/api/v1/services/foundation-models/text-generation/generation",
            headers=headers, 
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"模型 {model_name} 测试成功!")
            logger.info(f"响应内容: {json.dumps(result, ensure_ascii=False, indent=2)}")
            return True, result
        else:
            logger.error(f"API返回错误: {response.status_code}, {response.text}")
            return False, response.text
    
    except Exception as e:
        logger.error(f"测试模型时出错: {str(e)}")
        return False, str(e)

def test_model_service(model_name):
    """使用LLMService测试模型"""
    logger.info(f"开始使用LLMService测试模型: {model_name}")
    service = LLMService()
    
    try:
        prompt = "你好，请简单介绍一下自己。"
        result = service.call_model(model_name, prompt)
        
        if result:
            logger.info(f"模型 {model_name} 测试成功!")
            logger.info(f"响应内容: {result}")
            return True, result
        else:
            logger.error(f"模型 {model_name} 调用失败，返回为None")
            return False, "调用失败，返回为None"
    
    except Exception as e:
        logger.error(f"测试模型时出错: {str(e)}")
        return False, str(e)

def main():
    """主函数"""
    api_key = load_env_variables()
    
    if not api_key:
        logger.error("未找到API密钥，请设置环境变量API_KEY或在.env文件中配置")
        return
    
    # 要测试的模型列表
    models_to_test = ["baichuan2-7b-chat", "baichuan2-13b-chat", "llama2-7b-chat", "llama2-13b-chat"]
    
    logger.info("====== 开始测试模型 ======")
    
    # 1. 先使用原生API测试
    for model in models_to_test:
        logger.info(f"\n[原生API] 测试模型: {model}")
        success, result = test_model_direct(model, api_key)
        logger.info(f"测试结果: {'成功' if success else '失败'}")
    
    # 2. 然后使用服务类测试
    for model in models_to_test:
        logger.info(f"\n[LLMService] 测试模型: {model}")
        success, result = test_model_service(model)
        logger.info(f"测试结果: {'成功' if success else '失败'}")
    
    logger.info("====== 模型测试完成 ======")

if __name__ == "__main__":
    main()
