import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv # <--- 添加导入

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 加载 .env 文件中的环境变量 <--- 添加这行
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

from openai import OpenAI

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_qwen_model(model_name="qwen-turbo"):
    """测试特定的Qwen模型"""
    
    # 现在 os.getenv 应该能正确读取 .env 文件中的 API_KEY
    # 如果仍然想保留一个默认值以防万一（但不推荐硬编码真实密钥）
    # api_key = os.getenv("API_KEY", "YOUR_DEFAULT_PLACEHOLDER_IF_NEEDED") 
    api_key = os.getenv("API_KEY") # 直接获取，如果 .env 或环境变量没有设置，则为 None

    if not api_key:
         logger.error("错误：未能从 .env 文件或环境变量中加载 API_KEY。请检查 .env 文件是否存在且包含有效的 API_KEY。")
         return # 如果没有 key 则直接退出

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
    # test_qwen_model()
    
    # 如果要测试其他模型，取消下面的注释
    # test_qwen_model("qwen-plus")
    # test_qwen_model("qwen-max")
    # test_qwen_model("qwen-72b-chat") 
    
    # 允许从命令行指定模型名称
    if len(sys.argv) > 1:
        model_to_test = sys.argv[1]
        test_qwen_model(model_to_test)
    else:
        # 如果没有命令行参数，可以提示用户输入或测试默认模型
        # test_qwen_model() # 测试默认 qwen-turbo
        try:
            model_input = input("请输入要测试的模型名称 [默认 qwen-turbo, 输入0取消]: ")
            if model_input == "0":
                print("测试取消。")
            elif not model_input.strip():
                 test_qwen_model() # 用户直接回车，测试默认
            else:
                test_qwen_model(model_input.strip())
        except EOFError:
             print("\n输入结束，测试默认模型 qwen-turbo。")
             test_qwen_model() # 处理管道输入或Ctrl+D的情况
