#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
修复数据文件中的模型错误
"""

import os
import json
import glob
import logging
from tqdm import tqdm

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("model_fix.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)

def process_all_json_files(data_dir):
    """处理所有JSON文件中的模型错误"""
    # 不可用模型名称和替代模型的映射
    model_replacements = {
        "baichuan2-7b-chat": "qwen-turbo",
        "baichuan2-13b-chat": "qwen-turbo",
        "llama2-7b-chat": "qwen-turbo",
        "llama2-13b-chat": "qwen-turbo"
    }
    
    # 查找all目录下的所有JSON文件
    all_files = glob.glob(os.path.join(data_dir, "output", "all", "*.json"))
    logger.info(f"找到 {len(all_files)} 个汇总JSON文件")
    
    modified_count = 0
    
    # 处理每个文件
    for file_path in tqdm(all_files, desc="处理文件"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            file_modified = False
            
            # 检查models_used列表
            if "models_used" in data:
                updated_models = []
                for model in data["models_used"]:
                    if model in model_replacements:
                        if model_replacements[model] not in updated_models:
                            updated_models.append(model_replacements[model])
                    else:
                        updated_models.append(model)
                
                if updated_models != data["models_used"]:
                    data["models_used"] = updated_models
                    file_modified = True
            
            # 检查results字段中的错误模型
            if "results" in data:
                new_results = {}
                for model, result in data["results"].items():
                    if model in model_replacements:
                        # 不复制错误的模型结果
                        pass
                    else:
                        new_results[model] = result
                
                if new_results != data["results"]:
                    data["results"] = new_results
                    file_modified = True
            
            # 如果文件被修改，则保存更新
            if file_modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                modified_count += 1
                logger.info(f"已更新文件: {os.path.basename(file_path)}")
        
        except Exception as e:
            logger.error(f"处理文件 {file_path} 时出错: {str(e)}")
    
    logger.info(f"共更新了 {modified_count} 个文件")
    return modified_count

def main():
    """主函数"""
    # 数据目录
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    
    logger.info(f"开始处理数据目录: {data_dir}")
    count = process_all_json_files(data_dir)
    logger.info(f"处理完成，共更新了 {count} 个文件")

if __name__ == "__main__":
    main()
