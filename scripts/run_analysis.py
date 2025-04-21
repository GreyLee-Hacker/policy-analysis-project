import os
import sys
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json
import argparse
import glob
import re
from dotenv import load_dotenv # <--- 添加导入
import smtplib
import socket
from email.mime.text import MIMEText

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 加载 .env 文件中的环境变量 <--- 添加这行
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

from src.utils.response_parser import parse_housing_elements
from src.utils.file_utils import write_model_results_to_json
from src.utils.logging_utils import setup_logger  # 使用统一的日志设置函数
from src.services.llm_service import LLMService, call_models
from src.config.model_config import MODEL_ENDPOINTS, DEFAULT_MODELS
from src.config.prompt_templates import TEMPLATES, DEFAULT_TEMPLATE

# 确保日志目录存在
logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(logs_dir, exist_ok=True)

# 设置主日志记录器 - 作为根记录器
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, 'main.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 获取主日志记录器
logger = logging.getLogger(__name__)
logger.info("开始政策分析任务")

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

def process_batch(batch_sentences, template, models, lock, progress_data, progress_file, incremental_file, current_processed):
    """处理一批句子的worker函数"""
    batch_results = []
    
    try:
        for sentence_data in batch_sentences:
            # 处理单个句子
            thread_logger = logging.getLogger(f"thread-{threading.current_thread().name}")
            thread_logger.info(f"处理句子: [{sentence_data['doc_id']}]-[{sentence_data['sent_id']}]")
            
            result = process_sentence(sentence_data['content'], template, models)
            
            # 添加句子标识信息
            result['doc_id'] = sentence_data['doc_id']
            result['sent_id'] = sentence_data['sent_id']
            if 'item_id' in sentence_data:
                result['item_id'] = sentence_data['item_id']
            
            # 处理结果，提取七步要素
            processed_result = {
                'doc_id': result['doc_id'],
                'sent_id': result['sent_id'],
                'sentence': result['sentence']
            }
            
            # 处理模型结果，提取七步要素
            for model_name, model_result in result['results'].items():
                if model_result['status'] == 'success' and 'content' in model_result:
                    parsed_elements = parse_housing_elements(model_result['content'])
                    processed_result[model_name] = parsed_elements
                else:
                    processed_result[model_name] = [{"error": model_result.get("error", "处理失败")}]
            
            batch_results.append(processed_result)
            
            # 更新进度（需要加锁）
            with lock:
                current_processed[0] += 1
                progress_data["processed_sentences"] = current_processed[0]
                progress_data["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")
                progress_data["completion_percentage"] = round(current_processed[0] / progress_data["total_sentences"] * 100, 2)
                
                # 每处理一个句子都更新进度文件
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress_data, f, ensure_ascii=False, indent=2)
        
        # 批次处理完成后，将结果追加到增量文件（需要加锁）
        with lock:
            try:
                # 先尝试读取现有结果
                existing_results = []
                try:
                    with open(incremental_file, 'r', encoding='utf-8') as f:
                        file_content = f.read().strip()
                        if file_content:  # 确保文件不为空
                            existing_results = json.loads(file_content)
                        else:
                            existing_results = []
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    thread_logger.warning(f"读取增量文件失败，将创建新文件: {str(e)}")
                    existing_results = []
                
                # 检查existing_results是否为列表
                if not isinstance(existing_results, list):
                    thread_logger.warning(f"增量文件内容不是列表格式，将重置为空列表")
                    existing_results = []
                
                # 追加新结果
                existing_results.extend(batch_results)
                
                # 强制先清空文件内容再写入，避免追加到损坏的内容
                with open(incremental_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_results, f, ensure_ascii=False, indent=2)
                
                thread_logger.info(f"批次处理结果已追加到文件: {incremental_file}，当前共 {len(existing_results)} 条结果")
            except Exception as e:
                thread_logger.error(f"保存增量结果时出错: {str(e)}")
                import traceback
                thread_logger.error(traceback.format_exc())
        
        return batch_results
    except Exception as e:
        logger.error(f"处理批次时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def process_file_with_threads(file_path, models, output_dir, template_name, max_workers=2, batch_size=3, resume=False, start_from=None, resume_file=None, resume_doc_id=None):
    """使用多线程处理单个文件，大幅提高处理速度"""
    try:
        # 读取政策文本
        if file_path.endswith('.json'):
            # JSON文件处理
            logger.info(f"开始处理JSON文件: {file_path}")
            
            # 存储句子列表
            sentences = []
            
            # 直接加载整个JSON文件
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 处理数组格式的JSON
                if isinstance(data, list):
                    logger.info(f"检测到JSON数组格式，包含 {len(data)} 个项目")
                    
                    for idx, item in enumerate(data):
                        if isinstance(item, dict):
                            # 检查并处理"分割"字段
                            if '分割' in item and isinstance(item['分割'], list):
                                split_items = item['分割']
                                valid_split_items = [s for s in split_items if s and isinstance(s, str) and s.strip()]
                                logger.info(f"项目 {idx} 中找到'分割'字段，包含 {len(valid_split_items)} 个有效元素")
                                
                                for split_item in valid_split_items:
                                    # 提取格式为"[文章id]-[句子id]具体句子内容"的文本
                                    match = re.match(r'\[(.*?)\]-\[(.*?)\](.*)', split_item)
                                    if match:
                                        doc_id = match.group(1)
                                        sent_id = match.group(2)
                                        content = match.group(3)
                                        
                                        if content and content.strip():  # 只处理非空内容
                                            sentences.append({
                                                'doc_id': doc_id,
                                                'sent_id': sent_id,
                                                'content': content.strip(),
                                                'item_id': idx
                                            })
                            else:
                                logger.debug(f"项目 {idx} 中没有找到有效的'分割'字段列表")
                else:
                    logger.warning(f"JSON文件不是数组格式: {file_path}")
            
            except json.JSONDecodeError as e:
                logger.error(f"解析JSON文件时出错: {str(e)}")
                return False
        else:
            # 普通文本文件不处理
            logger.warning(f"目前仅处理JSON格式文件，{file_path} 将被跳过")
            return False
        
        logger.info(f"从文件中提取了 {len(sentences)} 个有效句子")
        
        if not sentences:
            logger.warning(f"文件 {file_path} 中没有找到有效句子")
            return False
        
        logger.info(f"成功提取了 {len(sentences)} 个有效句子，准备进行模型处理")
        
        # 获取选定的模板
        template = TEMPLATES[template_name]
        
        # 获取文件名（不含扩展名）
        filename = os.path.splitext(os.path.basename(file_path))[0]
        file_basename = os.path.basename(file_path) # <-- 获取完整文件名用于比较
        
        # 创建进度记录文件
        progress_dir = os.path.join(output_dir, template_name, "progress")
        os.makedirs(progress_dir, exist_ok=True)
        progress_file = os.path.join(progress_dir, f"{filename}_progress.json")
        
        # 检查是否已有进度文件和断点续处理参数
        start_position = 0
        existing_processed = []
        
        # 优先处理特定文件和 doc_id 的续跑逻辑
        if resume_file and resume_doc_id is not None and file_basename == resume_file:
            logger.info(f"检测到特定文件续跑请求: 文件='{resume_file}', doc_id='{resume_doc_id}'")
            found_start_index = -1
            for i, sentence_data in enumerate(sentences):
                # 确保比较的是字符串类型
                if str(sentence_data.get('doc_id')) == str(resume_doc_id):
                    found_start_index = i
                    break
            if found_start_index != -1:
                start_position = found_start_index
                logger.info(f"在文件 '{resume_file}' 中找到 doc_id '{resume_doc_id}' 对应的句子索引: {start_position}，将从该位置开始处理。")
                # 特定文件续跑时，也尝试加载增量文件以避免重复写入
                incremental_file_path_for_resume = os.path.join(output_dir, template_name, "incremental", f"{filename}_incremental.json")
                if os.path.exists(incremental_file_path_for_resume):
                     try:
                         with open(incremental_file_path_for_resume, 'r', encoding='utf-8') as f:
                             existing_processed = json.load(f)
                             if not isinstance(existing_processed, list): existing_processed = []
                             logger.info(f"从增量文件 '{incremental_file_path_for_resume}' 加载了 {len(existing_processed)} 条已处理结果。")
                     except (json.JSONDecodeError, FileNotFoundError) as e:
                         logger.warning(f"读取增量文件 '{incremental_file_path_for_resume}' 失败: {str(e)}，将创建新的增量文件")
                         existing_processed = []
            else:
                logger.warning(f"在文件 '{resume_file}' 中未找到指定的 doc_id '{resume_doc_id}'，将从头处理该文件。")
                start_position = 0 # 未找到则从头开始
        elif resume_file and file_basename != resume_file:
             logger.info(f"当前文件 '{file_basename}' 不是指定的续跑文件 '{resume_file}'，将从头处理。")
             start_position = 0 # 其他文件从头开始
             existing_processed = [] # 其他文件不加载历史结果
        elif resume and os.path.exists(progress_file): # 处理通用的 resume 逻辑 (如果没有指定特定文件)
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    existing_progress = json.load(f)
                    # 只有在没有指定特定文件续跑时，才使用进度文件中的位置
                    if not (resume_file and file_basename == resume_file):
                        start_position = existing_progress.get("processed_sentences", 0)
                        logger.info(f"发现进度文件，从第 {start_position} 个句子继续处理")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning(f"读取进度文件失败: {str(e)}，将从头开始处理")
                start_position = 0
        elif start_from is not None and start_from >= 0: # 处理 start_from 参数 (优先级低于特定文件续跑)
             if not (resume_file and file_basename == resume_file):
                 start_position = start_from
                 logger.info(f"根据参数指定，从第 {start_position} 个句子开始处理")
        
        
        # 创建增量结果目录
        result_dir = os.path.join(output_dir, template_name, "incremental")
        os.makedirs(result_dir, exist_ok=True)
        
        # 为当前文件创建专门的增量结果文件
        incremental_file = os.path.join(result_dir, f"{filename}_incremental.json")
        
        # 检查是否存在已处理的结果，避免重复处理 (仅在续跑时加载)
        # 注意：上面特定文件续跑逻辑已经处理了 existing_processed 的加载
        if start_position > 0 and not (resume_file and file_basename == resume_file): # 只有在通用续跑时才加载
            if os.path.exists(incremental_file):
                try:
                    with open(incremental_file, 'r', encoding='utf-8') as f:
                        loaded_data = json.load(f)
                        if isinstance(loaded_data, list):
                             existing_processed = loaded_data
                             logger.info(f"读取到 {len(existing_processed)} 个已处理结果")
                        else:
                             logger.warning(f"增量文件 '{incremental_file}' 内容格式不正确，将忽略。")
                             existing_processed = []
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    logger.warning(f"读取增量文件失败: {str(e)}，将创建新的增量文件")
                    existing_processed = []
            else:
                 existing_processed = [] # 文件不存在则为空
        
        # 如果增量文件不存在或不续跑，创建一个空的结果列表文件
        if not os.path.exists(incremental_file) or start_position == 0:
             # 如果是特定文件续跑，即使 start_position > 0，也可能需要清空旧的增量文件
             # 但上面的逻辑已经加载了 existing_processed，所以这里只在文件不存在时创建
             if not os.path.exists(incremental_file):
                 with open(incremental_file, 'w', encoding='utf-8') as f:
                     json.dump([], f, ensure_ascii=False)
                 existing_processed = []
             # 如果 start_position 为 0 (从头开始)，确保 existing_processed 为空
             if start_position == 0:
                 existing_processed = []
                 # 如果文件存在但要从头跑，清空它
                 if os.path.exists(incremental_file):
                      logger.info(f"从头处理文件 '{file_basename}'，清空现有增量文件 '{incremental_file}'。")
                      with open(incremental_file, 'w', encoding='utf-8') as f:
                          json.dump([], f, ensure_ascii=False)
        
        
        # 初始化进度记录
        # 注意：这里的 processed_sentences 应该反映实际从增量文件加载的数量
        # 但为了简化，我们让 process_batch 去累加，这里只记录总数和初始状态
        progress_data = {
            "filename": filename,
            "total_sentences": len(sentences),
            "processed_sentences": start_position, # 记录开始处理的位置
            "last_update": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "processing",
            "thread_count": max_workers,
            "batch_size": batch_size,
            "completion_percentage": round(start_position / len(sentences) * 100, 2) if sentences else 0
        }
        
        # 保存初始进度
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
        
        # 创建线程锁，用于同步文件访问
        file_lock = threading.Lock()
        # current_processed 应该从 start_position 开始计数
        current_processed = [start_position] # 使用列表作为可变对象，用于跨线程更新
        
        # 根据断点位置处理句子
        sentences_to_process = []
        if start_position >= len(sentences):
            logger.warning(f"指定的起始位置 {start_position} 大于或等于句子总数 {len(sentences)}，无需处理文件 '{file_basename}'")
            # 更新进度为完成
            progress_data["status"] = "completed"
            progress_data["processed_sentences"] = len(sentences) # 标记为全部处理完
            progress_data["completion_percentage"] = 100
            progress_data["completion_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(progress_file, 'w', encoding='utf-8') as f:
                 json.dump(progress_data, f, ensure_ascii=False, indent=2)
            return True # 直接返回成功
        else:
            sentences_to_process = sentences[start_position:]
            logger.info(f"准备处理文件 '{file_basename}' 从第 {start_position} 个句子开始，共 {len(sentences_to_process)} 个句子需处理")
        
        
        # 将待处理的句子列表分成多个批次
        batches = []
        for i in range(0, len(sentences_to_process), batch_size):
            batches.append(sentences_to_process[i:i+batch_size])
        
        logger.info(f"将 {len(sentences_to_process)} 个待处理句子分为 {len(batches)} 个批次进行处理，每批次 {batch_size} 个句子")
        
        # 使用ThreadPoolExecutor并行处理所有批次
        processed_count_in_run = 0 # 本次运行实际处理的数量
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有批次的处理任务
            future_to_batch = {
                executor.submit(
                    process_batch,
                    batch,
                    template,
                    models,
                    file_lock,
                    progress_data, # 传递 progress_data 字典本身
                    progress_file,
                    incremental_file,
                    current_processed # 传递包含当前计数的列表
                ): i for i, batch in enumerate(batches)
            }
            
            logger.info(f"已提交 {len(batches)} 个批次任务到线程池，使用 {max_workers} 个工作线程")
            
            # 收集所有结果
            for future in as_completed(future_to_batch):
                batch_index = future_to_batch[future]
                try:
                    batch_results = future.result()
                    # all_results.extend(batch_results) # 不再需要收集所有结果到内存
                    processed_count_in_run += len(batch_results)
                    logger.info(f"批次 {batch_index} 处理完成，获取了 {len(batch_results)} 个结果")
                except Exception as e:
                    logger.error(f"批次 {batch_index} 处理失败: {str(e)}")
        
        logger.info(f"文件 '{file_basename}' 本次运行处理完成，共处理 {processed_count_in_run} 个句子")
        
        # 完成所有处理后，更新进度记录
        final_processed_count = current_processed[0] # 获取最终处理到的句子总数
        progress_data["status"] = "completed"
        progress_data["processed_sentences"] = final_processed_count
        progress_data["completion_percentage"] = round(final_processed_count / len(sentences) * 100, 2) if sentences else 100
        progress_data["completion_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"文件 '{file_basename}' 处理完成: {final_processed_count}/{len(sentences)} ({progress_data['completion_percentage']}%)")
        
        # 创建输出目录
        all_output_dir = os.path.join(output_dir, template_name, "all")
        os.makedirs(all_output_dir, exist_ok=True)
        
        # 保存最终结果 (从增量文件读取)
        final_output_file = os.path.join(all_output_dir, f"{filename}_sentences.json")
        
        try:
            with open(incremental_file, 'r', encoding='utf-8') as f:
                final_results = json.load(f)
                if not isinstance(final_results, list):
                     logger.error(f"最终增量文件 '{incremental_file}' 内容格式错误，无法生成汇总文件。")
                     final_results = [] # 置为空列表避免写入错误
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"无法读取最终增量结果文件 '{incremental_file}' ({e})，无法生成汇总文件。")
            final_results = [] # 置为空列表避免写入错误
        
        # 只有在 final_results 不为空时才写入
        if final_results:
             with open(final_output_file, 'w', encoding='utf-8') as f:
                 json.dump(final_results, f, ensure_ascii=False, indent=2)
             logger.info(f"所有句子分析结果已保存到 {final_output_file}")
        else:
             logger.warning(f"由于增量文件为空或读取失败，未生成最终汇总文件 '{final_output_file}'")
        
        
        return True
    except Exception as e:
        logger.error(f"处理文件 {file_path} 时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # 标记进度为失败
        try:
            progress_data["status"] = "failed"
            progress_data["error_message"] = str(e)
            progress_data["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
        except NameError: # 如果 progress_data 还未定义
             logger.error("在记录失败状态之前发生错误")
        except Exception as pe: # 记录进度文件写入错误
             logger.error(f"写入失败状态到进度文件时出错: {pe}")
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
    
    # 为每个模型创建子目录和模型特定结果集合
    model_dirs = {}
    model_results = {}  # 用于存储每个模型的结果
    
    for sentence_result in sentence_results:
        for model_name in sentence_result["results"].keys():
            if model_name not in model_dirs:
                model_output_dir = os.path.join(template_output_dir, model_name)
                os.makedirs(model_output_dir, exist_ok=True)
                model_dirs[model_name] = model_output_dir
                # 为每个模型初始化结果集合
                model_results[model_name] = {
                    "filename": filename,
                    "model": model_name,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "total_sentences": len(sentence_results),
                    "sentences": []
                }
    
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
                    
                    # 同时将解析后的内容添加到模型特定结果中
                    model_sentence_entry = {
                        "text": sentence,
                        "parsed_content": parsed_content
                    }
                    model_results[model_name]["sentences"].append(model_sentence_entry)
                else:
                    sentence_entry["models"][model_name] = content
                    
                    # 将原始内容添加到模型特定结果中
                    model_sentence_entry = {
                        "text": sentence,
                        "content": content
                    }
                    model_results[model_name]["sentences"].append(model_sentence_entry)
            else:
                error_msg = result.get("error", "未知错误")
                sentence_entry["models"][model_name] = {"error": error_msg}
                
                # 将错误信息添加到模型特定结果中
                model_sentence_entry = {
                    "text": sentence,
                    "error": error_msg
                }
                model_results[model_name]["sentences"].append(model_sentence_entry)
        
        # 添加句子条目到汇总结果
        combined_results["sentences"].append(sentence_entry)
    
    # 保存汇总结果到all目录
    all_output_file = os.path.join(all_output_dir, f"{filename}_sentences.json")
    
    with open(all_output_file, 'w', encoding='utf-8') as f:
        json.dump(combined_results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"所有句子分析结果已保存到 {all_output_file}")
    
    # 为每个模型保存单独的结果文件
    for model_name, result in model_results.items():
        model_output_file = os.path.join(model_dirs[model_name], f"{filename}_sentences.json")
        
        with open(model_output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"{model_name} 模型的句子分析结果已保存到 {model_output_file}")

def send_completion_email(processed_files_count, total_files, start_time):
    """发送分析完成的邮件通知"""
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    recipient_email = os.getenv("EMAIL_RECIPIENT")

    if not all([smtp_server, smtp_port, smtp_username, smtp_password, recipient_email]):
        logger.warning("邮件配置不完整，跳过发送完成通知邮件。请检查 .env 文件中的 SMTP_* 和 EMAIL_RECIPIENT 配置。")
        return

    try:
        smtp_port = int(smtp_port) # 端口号需要是整数
        end_time = time.time()
        duration = round(end_time - start_time, 2)

        subject = "政策分析任务完成通知"
        body = f"""
        政策分析任务已完成。

        开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}
        结束时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}
        总耗时: {duration} 秒

        共处理文件数: {processed_files_count} / {total_files}

        请检查 'data/output/' 目录获取结果。
        """

        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = smtp_username
        msg['To'] = recipient_email

        logger.info(f"准备发送邮件通知至 {recipient_email}...")

        # 根据端口号选择连接方式
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30) as server:
                server.login(smtp_username, smtp_password)
                server.sendmail(smtp_username, [recipient_email], msg.as_string())
        elif smtp_port == 587:
             with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.starttls() # 启用TLS
                server.login(smtp_username, smtp_password)
                server.sendmail(smtp_username, [recipient_email], msg.as_string())
        else: # 其他端口尝试普通SMTP连接
             with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                # 如果需要，尝试 server.starttls()
                try: # 尝试登录，如果需要的话
                    server.login(smtp_username, smtp_password)
                except smtplib.SMTPNotSupportedError:
                    logger.info("SMTP 服务器不支持登录，尝试匿名发送...")
                except smtplib.SMTPAuthenticationError:
                     logger.error("SMTP 登录失败，请检查用户名和密码。")
                     return # 登录失败则不发送
                except Exception as login_err:
                     logger.error(f"SMTP 登录时发生未知错误: {login_err}")
                     return
                server.sendmail(smtp_username, [recipient_email], msg.as_string())


        logger.info("邮件通知发送成功！")

    except smtplib.SMTPAuthenticationError:
        logger.error(f"邮件发送失败：SMTP认证错误，请检查邮箱地址 ({smtp_username}) 和密码/授权码。")
    except smtplib.SMTPServerDisconnected:
         logger.error("邮件发送失败：SMTP服务器意外断开连接。")
    except smtplib.SMTPConnectError:
         logger.error(f"邮件发送失败：无法连接到SMTP服务器 {smtp_server}:{smtp_port}。请检查服务器地址和端口。")
    except socket.gaierror:
         logger.error(f"邮件发送失败：无法解析SMTP服务器地址 {smtp_server}。")
    except socket.timeout:
         logger.error("邮件发送失败：连接SMTP服务器超时。")
    except Exception as e:
        logger.error(f"发送邮件通知时发生未知错误: {str(e)}")


def main():
    start_time = time.time() # 记录开始时间
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
    # 添加多线程相关参数
    parser.add_argument('--threads', '-j', type=int, default=2, # <-- 修改默认值为 2
                       help='指定工作线程数量 (默认: 2)')
    parser.add_argument('--batch-size', '-b', type=int, default=3,
                       help='每个批次的句子数量 (默认: 3)')
    # 添加断点续处理相关参数
    parser.add_argument('--resume', '-r', action='store_true',
                       help='启用断点续处理功能，从上次处理的位置继续 (通用，基于进度文件)')
    parser.add_argument('--start-from', '-s', type=int,
                       help='指定从哪个句子序号开始处理 (从0开始计数，通用，优先级低于特定文件续跑)')
    parser.add_argument('--resume-file', type=str,
                       help='指定要续跑的文件名 (例如: 地方法规2_cleaned1_extract.json)')
    parser.add_argument('--resume-doc-id', type=str, # <-- doc_id 通常是字符串
                       help='指定在 resume-file 中从哪个 doc_id 开始处理')

    args = parser.parse_args()

    # 验证 resume-file 和 resume-doc-id 是否成对出现
    if (args.resume_file and not args.resume_doc_id) or (not args.resume_file and args.resume_doc_id):
        parser.error("--resume-file 和 --resume-doc-id 必须同时提供。")
        return # 或者 sys.exit(1)

    # 设置输入和输出目录
    input_directory = os.path.join(os.path.dirname(__file__), '..', 'data', 'input')
    # 修正 output_directory 路径，确保它指向 data/output
    output_directory = os.path.join(os.path.dirname(__file__), '..', 'data', 'output', args.template) # 直接指向模板子目录
    # os.makedirs(output_directory, exist_ok=True) # 确保基础输出目录存在，process_file_with_threads 会创建子目录

    # 使用命令行指定的模板
    template_name = args.template

    # 如果命令行指定了模型，则使用指定模型，否则使用默认模型
    global models
    if args.models:
        models = args.models.split(',')
        logger.info(f"使用命令行指定的模型: {models}")

    # 获取线程数和批次大小
    max_workers = args.threads
    batch_size = args.batch_size
    logger.info(f"使用 {max_workers} 个工作线程，每批处理 {batch_size} 个句子")

    # 获取断点续处理参数
    resume = args.resume
    start_from = args.start_from
    resume_file = args.resume_file
    resume_doc_id = args.resume_doc_id

    if resume_file and resume_doc_id:
         logger.info(f"启用特定文件续跑: 文件='{resume_file}', doc_id='{resume_doc_id}'")
         # 当指定特定文件续跑时，禁用通用的 resume 和 start_from，避免冲突
         resume = False
         start_from = None
         logger.info("通用 resume 和 start-from 参数已被忽略。")
    elif resume:
        logger.info("启用通用断点续处理功能，将从上次处理的位置继续")
    elif start_from is not None:
        logger.info(f"将从第 {start_from} 个句子开始处理 (通用)")


    # 确保输入目录存在 (检查原始 input 目录)
    base_input_directory = os.path.join(os.path.dirname(__file__), '..', 'data', 'input')
    if not os.path.exists(base_input_directory):
        os.makedirs(base_input_directory)
        logger.warning(f"创建了输入目录: {base_input_directory}")
        logger.warning("请在输入目录中添加文本文件后重新运行")
        return

    # 获取输入文件列表
    input_files_to_process = []
    if args.input:
        # 如果提供了input参数
        input_path = args.input
        # 检查是否是绝对路径，如果不是，则相对于项目根目录
        if not os.path.isabs(input_path):
             project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
             input_path = os.path.join(project_root, input_path)

        if '*' in input_path or '?' in input_path: # 检查是否包含通配符
            input_files_to_process = glob.glob(input_path)
        elif os.path.isfile(input_path):
            input_files_to_process = [input_path]
        elif os.path.isdir(input_path):
             # 处理目录中的所有 JSON 文件 (根据你的文件结构)
             input_files_to_process = glob.glob(os.path.join(input_path, '*.json'))
        else:
             logger.error(f"指定的输入路径无效: {args.input}")
             return
    else:
        # 使用默认输入目录 (data/input/policy/2024) - 根据你的结构调整
        default_input_path = os.path.join(base_input_directory, 'policy', '2024')
        if os.path.isdir(default_input_path):
             input_files_to_process = glob.glob(os.path.join(default_input_path, '*.json'))
        else:
             logger.warning(f"默认输入路径 {default_input_path} 不存在或不是目录。")


    if not input_files_to_process:
        logger.warning(f"没有找到有效的输入文件。请检查输入路径或 {base_input_directory} 目录。")
        return

    logger.info(f"找到 {len(input_files_to_process)} 个输入文件准备处理: {', '.join([os.path.basename(f) for f in input_files_to_process])}")

    processed_files_count = 0 # 计数器
    total_files = len(input_files_to_process) # 总文件数

    # 顺序处理文件，不再使用线程池处理文件本身
    # 线程池用于处理单个文件内的句子批次
    for file_path in input_files_to_process:
         logger.info(f"开始处理文件: {file_path}")
         # 确定当前文件是否是指定的续跑文件
         current_file_basename = os.path.basename(file_path)
         is_target_resume_file = resume_file == current_file_basename

         # 准备传递给 process_file_with_threads 的参数
         process_args = {
             "file_path": file_path,
             "models": models,
             "output_dir": os.path.join(os.path.dirname(__file__), '..', 'data', 'output'), # 传递基础输出目录
             "template_name": template_name,
             "max_workers": max_workers,
             "batch_size": batch_size,
             "resume": resume, # 通用 resume 标志
             "start_from": start_from, # 通用 start_from
             "resume_file": resume_file, # 特定续跑文件名
             "resume_doc_id": resume_doc_id # 特定续跑 doc_id
         }

         success = process_file_with_threads(**process_args)

         if success:
             processed_files_count += 1
             logger.info(f"文件处理成功: {file_path}")
         else:
             logger.error(f"文件处理失败: {file_path}")
         logger.info(f"已处理 {processed_files_count}/{total_files} 个文件")


    logger.info("所有文件处理完成。")

    # 在所有文件处理完成后发送邮件
    send_completion_email(processed_files_count, total_files, start_time)

if __name__ == "__main__":
    main()