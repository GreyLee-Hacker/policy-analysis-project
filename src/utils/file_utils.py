import os
import json
import logging
from pathlib import Path

def write_results_to_json(results, output_path, ensure_dir=True):
    """
    将结果写入JSON文件
    
    Args:
        results: 要写入的结果数据
        output_path: 输出文件路径
        ensure_dir: 是否确保目录存在
    
    Returns:
        写入文件的路径
    """
    if ensure_dir:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    # 检查输出路径是否是目录
    if os.path.isdir(output_path):
        output_path = os.path.join(output_path, "results.json")
        print(f"提供的路径是目录，将使用默认文件名: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(results, json_file, ensure_ascii=False, indent=4)
    
    logging.info(f"结果已保存到: {output_path}")
    return output_path

def write_model_results_to_json(model_name, results, output_dir, file_prefix=None):
    """
    将特定模型的结果写入JSON文件
    
    Args:
        model_name: 模型名称
        results: 要写入的结果数据
        output_dir: 输出目录
        file_prefix: 文件名前缀，默认为空
    
    Returns:
        写入文件的路径
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    prefix = f"{file_prefix}_" if file_prefix else ""
    output_path = os.path.join(output_dir, f"{prefix}{model_name}_results.json")
    
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(results, json_file, ensure_ascii=False, indent=4)
    
    logging.info(f"{model_name}模型结果已保存到: {output_path}")
    return output_path

def read_json_file(file_path):
    """
    读取JSON文件
    
    Args:
        file_path: 文件路径
    
    Returns:
        JSON数据
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def ensure_directory_exists(directory_path):
    """
    确保目录存在，如果不存在则创建
    
    Args:
        directory_path: 目录路径
    """
    Path(directory_path).mkdir(parents=True, exist_ok=True)
    return directory_path

def setup_model_logger(model_name, log_dir="logs"):
    """
    为特定模型设置日志记录器
    
    Args:
        model_name: 模型名称
        log_dir: 日志目录
        
    Returns:
        配置好的日志记录器
    """
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logger = logging.getLogger(f"model.{model_name}")
    
    if not logger.handlers:  # 避免重复添加处理器
        # 设置文件处理器
        log_file = os.path.join(log_dir, f"{model_name}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        
        # 设置格式
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # 添加到记录器
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        
    return logger