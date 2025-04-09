import logging
import os
from pathlib import Path

def setup_logger(name):
    """
    为每个模型设置独立的日志记录器
    
    Args:
        name: 日志记录器名称，通常是模型名
        
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 文件处理器
    file_handler = logging.FileHandler(log_dir / f"{name}_log.txt", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 保持原有函数不变
def log_info(model_name, message):
    logger = setup_logger(model_name)
    logger.info(message)

def log_error(model_name, message):
    logger = setup_logger(model_name)
    logger.error(message)

def log_warning(model_name, message):
    logger = setup_logger(model_name)
    logger.warning(message)