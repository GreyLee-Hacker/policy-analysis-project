import os
import sys
import json
import logging
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from openai import OpenAI

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_qwen_model(model_name="qwen-turbo"):
    """测试特定的Qwen模型"""
    
    api_key = os.getenv("API_KEY", "sk-5ccc48320e3341b6b273861358dffdec")
    
    try:
        logger.info(f"正在测试模型: {model_name}...")
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        prompt = "分析以下政策文本: 广州市住房公积金管理委员会关于调整住房公积金缴存比例和缴存基数的通知"
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是一个善于分析政策文本的助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            top_p=0.7,
            max_tokens=1000
        )
        
        result = response.choices[0].message.content
        logger.info(f"模型 {model_name} 测试成功!")
        logger.info(f"输出结果:\n{result[:200]}...")
        
        # 保存结果
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'output')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"test_{model_name}_result.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "model": model_name,
                "prompt": prompt,
                "result": result
            }, f, ensure_ascii=False, indent=4)
            
        logger.info(f"结果已保存到: {output_file}")
        
    except Exception as e:
        logger.error(f"测试模型 {model_name} 时出错: {str(e)}")

if __name__ == "__main__":
    # 测试默认模型
    test_qwen_model()
    
    # 如果要测试其他模型，取消下面的注释
    # test_qwen_model("qwen-plus")
    # test_qwen_model("qwen-max")
