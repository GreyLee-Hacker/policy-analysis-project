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

def process_file_with_threads(file_path, models, output_dir, template_name, max_workers=5, batch_size=3):
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
        
        # 创建进度记录文件
        progress_dir = os.path.join(output_dir, template_name, "progress")
        os.makedirs(progress_dir, exist_ok=True)
        progress_file = os.path.join(progress_dir, f"{filename}_progress.json")
        
        # 初始化进度记录
        progress_data = {
            "filename": filename,
            "total_sentences": len(sentences),
            "processed_sentences": 0,
            "last_update": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "processing",
            "thread_count": max_workers,
            "batch_size": batch_size
        }
        
        # 保存初始进度
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
        
        # 创建结果输出目录
        result_dir = os.path.join(output_dir, template_name, "incremental")
        os.makedirs(result_dir, exist_ok=True)
        
        # 为当前文件创建专门的增量结果文件
        incremental_file = os.path.join(result_dir, f"{filename}_incremental.json")
        
        # 如果文件不存在，创建一个空的结果列表文件
        if not os.path.exists(incremental_file):
            with open(incremental_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False)
        
        # 创建线程锁，用于同步文件访问
        file_lock = threading.Lock()
        current_processed = [0]  # 使用列表作为可变对象，用于跨线程更新
        
        # 将句子列表分成多个批次
        batches = []
        for i in range(0, len(sentences), batch_size):
            batches.append(sentences[i:i+batch_size])
        
        logger.info(f"将 {len(sentences)} 个句子分为 {len(batches)} 个批次进行处理，每批次 {batch_size} 个句子")
        
        # 使用ThreadPoolExecutor并行处理所有批次
        all_results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有批次的处理任务
            future_to_batch = {
                executor.submit(
                    process_batch, 
                    batch, 
                    template, 
                    models, 
                    file_lock,
                    progress_data,
                    progress_file,
                    incremental_file,
                    current_processed
                ): i for i, batch in enumerate(batches)
            }
            
            logger.info(f"已提交 {len(batches)} 个批次任务到线程池，使用 {max_workers} 个工作线程")
            
            # 收集所有结果
            for future in as_completed(future_to_batch):
                batch_index = future_to_batch[future]
                try:
                    batch_results = future.result()
                    all_results.extend(batch_results)
                    logger.info(f"批次 {batch_index} 处理完成，获取了 {len(batch_results)} 个结果")
                except Exception as e:
                    logger.error(f"批次 {batch_index} 处理失败: {str(e)}")
        
        logger.info(f"所有批次处理完成，共处理 {current_processed[0]}/{len(sentences)} 个句子")
        
        # 完成所有处理后，更新进度记录
        progress_data["status"] = "completed"
        progress_data["processed_sentences"] = len(sentences)
        progress_data["completion_percentage"] = 100
        progress_data["completion_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"处理完成: {len(sentences)}/{len(sentences)} (100%)")
        
        # 创建输出目录
        all_output_dir = os.path.join(output_dir, template_name, "all")
        os.makedirs(all_output_dir, exist_ok=True)
        
        # 保存最终结果
        final_output_file = os.path.join(all_output_dir, f"{filename}_sentences.json")
        
        # 直接使用增量文件的结果作为最终结果
        try:
            with open(incremental_file, 'r', encoding='utf-8') as f:
                final_results = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # 如果增量文件有问题，使用all_results重新构建
            logger.warning(f"无法读取增量结果文件，使用内存中结果构建最终输出")
            final_results = all_results
        
        with open(final_output_file, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"所有句子分析结果已保存到 {final_output_file}")
        
        return True
    except Exception as e:
        logger.error(f"处理文件 {file_path} 时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
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
    parser.add_argument('--threads', '-j', type=int, default=5,
                       help='指定工作线程数量 (默认: 5)')
    parser.add_argument('--batch-size', '-b', type=int, default=3,
                       help='每个批次的句子数量 (默认: 3)')
    args = parser.parse_args()
    
    # 设置输入和输出目录
    input_directory = os.path.join(os.path.dirname(__file__), '..', 'data', 'input')
    output_directory = os.path.join(os.path.dirname(__file__), '..', 'data', 'output')
    
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
                    process_file_with_threads(file_path, models, output_directory, template_name, max_workers, batch_size)
        else:
            # 如果是单个文件或目录
            if os.path.isfile(args.input):
                process_file_with_threads(args.input, models, output_directory, template_name, max_workers, batch_size)
            elif os.path.isdir(args.input):
                # 如果是目录，处理目录中的所有文件
                for f in os.listdir(args.input):
                    file_path = os.path.join(args.input, f)
                    if os.path.isfile(file_path) and f.endswith((".txt", ".json", ".md")):
                        logger.info(f"处理文件: {file_path}")
                        process_file_with_threads(file_path, models, output_directory, template_name, max_workers, batch_size)
        logger.info("所有文件处理完成!")
        return
    else:
        # 使用默认输入目录
        input_files = [f for f in os.listdir(input_directory) 
                      if f.endswith((".txt", ".json", ".md"))]
    
    if not input_files:
        logger.warning(f"没有找到输入文件。请在 {input_directory} 目录中添加文件后重新运行。")
        return
    
    logger.info(f"找到 {len(input_files)} 个输入文件")
    
    processed_files_count = 0 # 计数器
    total_files = len(input_files) # 总文件数

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        # 依次处理每个输入文件，使用process_file_with_threads函数
        future_to_file = {executor.submit(process_file_with_threads, os.path.join(input_directory, input_file), models, output_directory, template_name, max_workers, batch_size): input_file for input_file in input_files}
        for future in as_completed(future_to_file):
            input_file = future_to_file[future]
            try:
                if future.exception() is None:
                    processed_files_count += 1 # 成功处理则计数
            except Exception as exc:
                logger.error(f'处理文件 {input_file} 时产生异常: {exc}')

    logger.info("所有文件处理完成。")

    # 在所有文件处理完成后发送邮件
    send_completion_email(processed_files_count, total_files, start_time)

if __name__ == "__main__":
    main()