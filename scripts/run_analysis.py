import os
import sys
import time
import logging
import threading
from pathlib import Path
import json
import argparse
import glob
import re

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.response_parser import parse_housing_elements
from src.utils.file_utils import write_model_results_to_json, setup_model_logger
from src.services.llm_service import LLMService, call_models
from src.config.model_config import MODEL_ENDPOINTS, DEFAULT_MODELS
from src.config.prompt_templates import TEMPLATES, DEFAULT_TEMPLATE

# 确保日志目录存在
logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(logs_dir, exist_ok=True)

# 设置主日志记录器
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, 'main.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('main')

# 使用定义的模型端点实例化LLMService
llm_service = LLMService(MODEL_ENDPOINTS)
# 使用配置文件中的默认模型
models = DEFAULT_MODELS
logger.info(f"使用的模型: {models}")

# 添加分句函数
def chunk_text_into_sentences(text):
    """
    将文本分割成句子
    
    Args:
        text: 要分割的文本
    
    Returns:
        句子列表
    """
    # 使用正则表达式匹配句子，保留句末标点
    # 匹配模式为句号、感叹号、问号，并且后面不是引号
    pattern = r'([^。！？]+[。！？]+)'
    sentences = re.findall(pattern, text)
    
    # 处理可能的剩余部分（没有以句号等结尾的最后部分）
    remaining = re.sub(pattern, '', text).strip()
    if remaining:
        sentences.append(remaining)
    
    # 过滤空句子
    return [s.strip() for s in sentences if s.strip()]

def process_sentence(sentence, template, models):
    """处理单个句子"""
    # 应用模板，将句子插入模板中
    prompt = template.format(policy_text=sentence)
    
    # 调用模型
    results = call_models(prompt, models=models)
    
    return {
        "sentence": sentence,
        "results": results
    }

def process_file(file_path, models, output_dir, template_name):
    """处理单个文件"""
    try:
        # 读取政策文本
        with open(file_path, 'r', encoding='utf-8') as f:
            policy_text = f.read().strip()
        
        # 将政策文本分割成句子
        sentences = chunk_text_into_sentences(policy_text)
        logger.info(f"将文本分割为 {len(sentences)} 个句子")
        
        # 获取选定的模板
        template = TEMPLATES[template_name]
        
        # 处理每个句子，获取结果
        sentence_results = []
        for i, sentence in enumerate(sentences):
            logger.info(f"处理第 {i+1}/{len(sentences)} 个句子")
            result = process_sentence(sentence, template, models)
            sentence_results.append(result)
        
        # 获取文件名（不含扩展名）
        filename = os.path.splitext(os.path.basename(file_path))[0]
        
        # 保存结果
        save_results(sentence_results, filename, output_dir, template_name)
        
        return True
    except Exception as e:
        logger.error(f"处理文件 {file_path} 时出错: {str(e)}")
        return False

def save_results(sentence_results, filename, output_dir, template_name=None):
    """保存模型分析结果"""
    # 如果提供了模板名称，则创建以模板命名的子文件夹
    if template_name:
        # 创建模板专用的输出目录
        template_output_dir = os.path.join(output_dir, template_name)
    else:
        # 使用默认输出目录结构
        template_output_dir = output_dir
    
    # 创建汇总结果的目录，现在始终位于模板目录下
    all_output_dir = os.path.join(template_output_dir, "all")
        
    # 确保目录存在
    os.makedirs(all_output_dir, exist_ok=True)

    # 构建结果汇总
    combined_results = {
        "filename": filename,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_sentences": len(sentence_results),
        "sentences": []
    }
    
    # 为每个模型创建子目录
    model_dirs = {}
    for sentence_result in sentence_results:
        for model_name in sentence_result["results"].keys():
            if model_name not in model_dirs:
                model_output_dir = os.path.join(template_output_dir, model_name)
                os.makedirs(model_output_dir, exist_ok=True)
                model_dirs[model_name] = model_output_dir
    
    # 处理每个句子的结果，并添加到汇总
    for sentence_result in sentence_results:
        sentence = sentence_result["sentence"]
        
        # 添加句子信息到汇总结果
        sentence_entry = {
            "text": sentence,
            "models": {}
        }
        
        # 处理每个模型的结果
        for model_name, result in sentence_result["results"].items():
            # 解析结果并添加到句子条目中
            if "content" in result and result["status"] == "success":
                content = result["content"]
                # 检测是否是housing模板的输出格式
                if isinstance(content, str) and "policy_object:" in content and "policy_stage:" in content:
                    parsed_content = parse_housing_elements(content)
                    sentence_entry["models"][model_name] = parsed_content
                else:
                    sentence_entry["models"][model_name] = content
            else:
                sentence_entry["models"][model_name] = {"error": result.get("error", "未知错误")}
        
        # 添加句子条目到汇总结果
        combined_results["sentences"].append(sentence_entry)
    
    # 保存汇总结果到all目录
    all_output_file = os.path.join(all_output_dir, f"{filename}_sentences.json")
    
    with open(all_output_file, 'w', encoding='utf-8') as f:
        json.dump(combined_results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"所有句子分析结果已保存到 {all_output_file}")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='政策文档分析工具')
    parser.add_argument('--template', '-t', 
                       choices=list(TEMPLATES.keys()), 
                       default=DEFAULT_TEMPLATE,
                       help='选择分析模板')
    # 添加input参数的定义
    parser.add_argument('--input', '-i',
                       help='指定输入文件或目录路径，支持通配符')
    parser.add_argument('--models', '-m',
                       help='指定要使用的模型，用逗号分隔')
    args = parser.parse_args()
    
    # 设置输入和输出目录
    input_directory = os.path.join(os.path.dirname(__file__), '..', 'data', 'input')
    output_directory = os.path.join(os.path.dirname(__file__), '..', 'data', 'output')
    
    # 使用命令行指定的模板 - 移到这里，确保所有分支都能访问
    template_name = args.template
    
    # 确保输入目录存在
    if not os.path.exists(input_directory):
        os.makedirs(input_directory)
        logger.warning(f"创建了输入目录: {input_directory}")
        logger.warning("请在输入目录中添加文本文件后重新运行")
        return
    
    # 获取输入文件列表
    if args.input:
        # 如果提供了input参数，直接使用该路径
        if '*' in args.input:
            input_files = glob.glob(args.input)
            # 处理每个匹配的文件
            for file_path in input_files:
                if os.path.isfile(file_path):
                    logger.info(f"处理文件: {file_path}")
                    process_file(file_path, models, output_directory, template_name)
        else:
            # 如果是单个文件或目录
            if os.path.isfile(args.input):
                process_file(args.input, models, output_directory, template_name)
            elif os.path.isdir(args.input):
                # 如果是目录，处理目录中的所有文件
                for f in os.listdir(args.input):
                    file_path = os.path.join(args.input, f)
                    if os.path.isfile(file_path) and f.endswith((".txt", ".json", ".md")):
                        logger.info(f"处理文件: {file_path}")
                        process_file(file_path, models, output_directory, template_name)
        logger.info("所有文件处理完成!")
        return
    else:
        # 使用默认输入目录
        input_files = [f for f in os.listdir(input_directory) 
                      if f.endswith((".txt", ".json", ".md"))]
        # 原有处理逻辑...
    
    if not input_files:
        logger.warning(f"没有找到输入文件。请在 {input_directory} 目录中添加文件后重新运行。")
        return
    
    logger.info(f"找到 {len(input_files)} 个输入文件")
    
    # 使用命令行指定的模板
    template_name = args.template
    
    # 依次处理每个输入文件，使用process_file函数
    for input_file in input_files:
        file_path = os.path.join(input_directory, input_file)
        logger.info(f"处理文件: {input_file}")
        
        # 使用process_file替代原来的逻辑
        process_file(file_path, models, output_directory, template_name)
    
    logger.info("所有文件处理完成!")

if __name__ == "__main__":
    main()