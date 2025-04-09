#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
获取阿里云DashScope平台上可用的模型列表
"""

import os
import json
import requests
from dotenv import load_dotenv
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("available_models.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)

def load_env_variables():
    """加载环境变量"""
    # 尝试加载.env文件
    load_dotenv()
    return os.getenv("API_KEY", "")

def get_available_models(api_key):
    """获取阿里云DashScope平台上可用的模型列表"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 获取文本生成模型列表
    try:
        logger.info("正在获取文本生成基础模型列表...")
        response = requests.get(
            "https://dashscope.aliyuncs.com/api/v1/models?type=text-generation",
            headers=headers
        )
        
        if response.status_code == 200:
            models = response.json()
            logger.info("成功获取文本生成基础模型列表")
            return models
        else:
            logger.error(f"获取模型列表失败: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        logger.error(f"请求模型列表时出错: {str(e)}")
        return None

def get_compatible_mode_models(api_key):
    """获取OpenAI兼容模式下的模型列表"""
    try:
        from openai import OpenAI
        
        logger.info("正在获取OpenAI兼容模式下的模型列表...")
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        models = client.models.list()
        logger.info("成功获取OpenAI兼容模式下的模型列表")
        return models
    except Exception as e:
        logger.error(f"获取OpenAI兼容模式模型列表时出错: {str(e)}")
        return None

def main():
    """主函数"""
    api_key = load_env_variables()
    
    if not api_key:
        logger.error("未找到API密钥，请设置环境变量API_KEY或在.env文件中配置")
        return
    
    # 获取并显示基础模型列表
    foundation_models = get_available_models(api_key)
    if foundation_models:
        logger.info("=== 文本生成基础模型列表 ===")
        if "data" in foundation_models and "models" in foundation_models["data"]:
            models = foundation_models["data"]["models"]
            for model in models:
                logger.info(f"模型名称: {model.get('model')}")
                logger.info(f"  描述: {model.get('description', '无描述')}")
                logger.info(f"  版本: {model.get('version', '无版本信息')}")
                logger.info("---------------------")
            
            # 将结果保存到JSON文件
            with open("foundation_models.json", "w", encoding="utf-8") as f:
                json.dump(foundation_models, f, ensure_ascii=False, indent=2)
                logger.info("文本生成基础模型列表已保存到 foundation_models.json")
    
    # 获取并显示OpenAI兼容模式下的模型列表
    compatible_models = get_compatible_mode_models(api_key)
    if compatible_models:
        logger.info("\n=== OpenAI兼容模式模型列表 ===")
        for model in compatible_models.data:
            logger.info(f"模型ID: {model.id}")
            logger.info(f"  创建时间: {model.created}")
            logger.info("---------------------")
        
        # 将结果保存到JSON文件
        model_list = [{"id": model.id, "created": model.created} for model in compatible_models.data]
        with open("compatible_models.json", "w", encoding="utf-8") as f:
            json.dump(model_list, f, ensure_ascii=False, indent=2)
            logger.info("OpenAI兼容模式模型列表已保存到 compatible_models.json")

if __name__ == "__main__":
    main()
