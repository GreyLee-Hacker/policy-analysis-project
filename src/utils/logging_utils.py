import logging
import os
from pathlib import Path

def setup_logger(name, log_dir="logs"):
    """
    为每个模型设置独立的日志记录器，同时确保日志也会记录到主日志文件中
    
    Args:
        name: 日志记录器名称，通常是模型名
        log_dir: 日志目录
        
    Returns:
        配置好的日志记录器
    """
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    # 获取或创建记录器
    logger = logging.getLogger(name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    # 设置日志级别
    logger.setLevel(logging.INFO)
    
    # 文件处理器 - 模型特定的日志文件
    model_log_file = os.path.join(log_dir, f"{name}.log")
    file_handler = logging.FileHandler(model_log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    
    # 重要：设置propagate=True确保日志会传递到根记录器(main.log)
    logger.propagate = True
    
    return logger

def log_info(model_name, message):
    """记录信息级别的日志"""
    logger = logging.getLogger(model_name)
    logger.info(message)

def log_error(model_name, message):
    """记录错误级别的日志"""
    logger = logging.getLogger(model_name)
    logger.error(message)

def log_warning(model_name, message):
    """记录警告级别的日志"""
    logger = logging.getLogger(model_name)
    logger.warning(message)