import os
import sys
import json
import logging
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.llm_service import LLMService, call_models
from src.config.model_config import AVAILABLE_MODELS, DEFAULT_MODELS

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_models(models=None, prompt=None):
    """测试指定的模型或默认模型"""
    
    if models is None:
        models = DEFAULT_MODELS
        logger.info(f"使用默认模型: {models}")
    
    if prompt is None:
        prompt = "分析以下政策文本: 广州市住房公积金管理委员会关于调整住房公积金缴存比例和缴存基数的通知"
    
    # 调用模型
    logger.info(f"开始测试以下模型: {models}")
    results = call_models(prompt, models)
    
    # 显示和保存结果
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'test_output')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "multiple_models_test_result.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "prompt": prompt,
            "models": models,
            "results": results
        }, f, ensure_ascii=False, indent=4)
    
    logger.info(f"测试结果已保存到: {output_file}")
    
    # 输出每个模型的状态
    for model_name, result in results.items():
        status = result.get("status", "未知")
        if status == "success":
            logger.info(f"模型 {model_name} 测试成功! 响应时间: {result.get('time', '未知')}秒")
            # 显示结果前100个字符作为预览
            content = result.get("content", "")
            preview = content[:100] + "..." if len(content) > 100 else content
            logger.info(f"回复预览: {preview}")
        else:
            error = result.get("error", "未知错误")
            logger.error(f"模型 {model_name} 测试失败! 错误: {error}")

def list_available_models():
    """列出所有可用的模型"""
    logger.info("可用的模型列表:")
    
    for platform, models in AVAILABLE_MODELS.items():
        logger.info(f"- {platform.upper()}平台模型:")
        for model in models:
            logger.info(f"  - {model}")
    
    logger.info(f"\n当前配置的默认模型: {DEFAULT_MODELS}")
    logger.info("\n使用方法示例:")
    logger.info("python scripts/test_multiple_models.py --models qwen-turbo,ernie-bot,gpt-3.5-turbo")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='测试多个模型')
    parser.add_argument('--models', type=str, help='要测试的模型，用逗号分隔')
    parser.add_argument('--prompt', type=str, help='测试提示词')
    parser.add_argument('--list', action='store_true', help='列出所有可用的模型')
    
    args = parser.parse_args()
    
    if args.list:
        list_available_models()
    else:
        models = args.models.split(',') if args.models else None
        test_models(models, args.prompt)
