#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
与本地大模型服务交互的客户端脚本
提供命令行交互界面，支持多种功能
"""

import os
import sys
import json
import time
import requests
import argparse
import logging
from pathlib import Path
from colorama import init, Fore, Style

# 初始化colorama
init()

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 从配置模块导入设置
try:
    from src.config.model_config import MODEL_ENDPOINTS
    DEFAULT_API_URL = MODEL_ENDPOINTS.get("model_chatglm", "http://0.0.0.0:8001/chat")
except ImportError:
    DEFAULT_API_URL = os.getenv("LOCAL_MODEL_URL", "http://0.0.0.0:8001/chat")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(project_root, "logs", "model_interaction.log"), 
                           encoding="utf-8", mode="a")
    ]
)

logger = logging.getLogger(__name__)

def print_colored(text, color=Fore.WHITE, style=Style.NORMAL, end='\n'):
    """打印彩色文本"""
    print(f"{style}{color}{text}{Style.RESET_ALL}", end=end)

def call_local_model(prompt, api_url, conversation_id="general", history=None, temperature=0.7, max_new_tokens=512):
    """调用本地模型的API"""
    # 准备请求参数
    payload = {
        "conversation_id": conversation_id,
        "prompt": prompt,
        "history": history or [],
        "temperature": temperature,
        "max_new_tokens": max_new_tokens
    }

    try:
        # 发起API请求
        start_time = time.time()
        response = requests.post(api_url, json=payload, timeout=60)
        elapsed_time = time.time() - start_time
        
        # 处理响应
        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "")
            history = result.get("history", [])
            
            logger.info(f"请求成功处理，耗时: {elapsed_time:.2f}秒")
            return response_text, history, True
        else:
            error_msg = f"API请求失败，状态码: {response.status_code}"
            try:
                error_detail = response.json().get("detail", "未提供错误详情")
                error_msg += f", 错误: {error_detail}"
            except:
                error_msg += f", 响应: {response.text[:100]}"
            
            logger.error(error_msg)
            return error_msg, history, False
            
    except requests.exceptions.Timeout:
        logger.error(f"请求超时，API地址: {api_url}")
        return "请求超时，模型可能处理较慢，请稍后再试", history, False
    except requests.exceptions.ConnectionError:
        logger.error(f"连接错误，请确保服务已启动: {api_url}")
        return "无法连接到模型服务，请确保服务已启动且地址正确", history, False
    except Exception as e:
        logger.error(f"调用模型时发生错误: {str(e)}")
        return f"调用模型时发生错误: {str(e)}", history, False

def call_chatglm_compatible_api(prompt, api_url, history=None):
    """调用兼容ChatGLM格式的API"""
    # 准备请求参数
    payload = {
        "prompt": prompt,
        "history": history or []
    }
    
    api_url = api_url.rstrip('/') + '/api/chat'  # 转换为ChatGLM兼容的API端点
    
    try:
        # 发起API请求
        start_time = time.time()
        response = requests.post(api_url, json=payload, timeout=60)
        elapsed_time = time.time() - start_time
        
        # 处理响应
        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "")
            history = result.get("history", [])
            
            logger.info(f"请求成功处理，耗时: {elapsed_time:.2f}秒")
            return response_text, history, True
        else:
            error_msg = f"API请求失败，状态码: {response.status_code}"
            logger.error(error_msg)
            return error_msg, history, False
            
    except Exception as e:
        logger.error(f"调用模型时发生错误: {str(e)}")
        return f"调用模型时发生错误: {str(e)}", history, False

def process_policy(policy_text, model_url, use_chatglm_format=False):
    """处理政策文本"""
    # 构建提示词
    prompt = f"""请分析以下政策文本，按以下结构输出：
1. 政策基本信息和背景
2. 政策核心内容
3. 政策受益群体
4. 政策实施主体
5. 政策创新点
6. 政策影响评估

以下是政策文本：
{policy_text}
"""

    print_colored("\n正在分析政策内容...", Fore.YELLOW, Style.BRIGHT)
    
    # 调用模型API
    if use_chatglm_format:
        response, _, success = call_chatglm_compatible_api(prompt, model_url)
    else:
        response, _, success = call_local_model(prompt, model_url)
    
    # 处理响应
    if success:
        print_colored("\n===== 政策分析结果 =====", Fore.GREEN, Style.BRIGHT)
        print_colored(response, Fore.WHITE)
    else:
        print_colored("\n分析政策时出错！", Fore.RED, Style.BRIGHT)
        print_colored(response, Fore.RED)

def interactive_chat(model_url, use_chatglm_format=False):
    """交互式聊天"""
    history = []
    conversation_id = f"chat_{int(time.time())}"
    
    print_colored("\n===== 交互式聊天模式 =====", Fore.CYAN, Style.BRIGHT)
    print_colored("输入 'quit'、'exit' 或 'q' 退出聊天", Fore.YELLOW)
    print_colored("输入 'clear' 清除聊天历史", Fore.YELLOW)
    print_colored("输入 'save' 保存聊天历史到文件", Fore.YELLOW)
    
    while True:
        # 获取用户输入
        user_input = input(f"\n{Fore.GREEN}您: {Style.RESET_ALL}")
        
        # 处理特殊命令
        if user_input.lower() in ["quit", "exit", "q"]:
            print_colored("\n感谢使用，再见！", Fore.CYAN, Style.BRIGHT)
            break
        elif user_input.lower() == "clear":
            history = []
            print_colored("已清除聊天历史", Fore.YELLOW)
            continue
        elif user_input.lower() == "save":
            save_path = f"chat_history_{int(time.time())}.json"
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            print_colored(f"聊天历史已保存到: {save_path}", Fore.YELLOW)
            continue
        elif not user_input.strip():
            continue
        
        # 调用模型API
        if use_chatglm_format:
            response, history, success = call_chatglm_compatible_api(user_input, model_url, history)
        else:
            response, history, success = call_local_model(user_input, model_url, conversation_id, history)
        
        # 显示回复
        print(f"\n{Fore.BLUE}AI: {Fore.WHITE}{response}{Style.RESET_ALL}")

def analyze_file(file_path, model_url, use_chatglm_format=False):
    """分析文件内容"""
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print_colored(f"错误：文件 {file_path} 不存在", Fore.RED, Style.BRIGHT)
            return
        
        # 读取文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 处理内容
        process_policy(content, model_url, use_chatglm_format)
        
    except Exception as e:
        print_colored(f"处理文件时发生错误: {str(e)}", Fore.RED, Style.BRIGHT)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='与本地大模型交互的客户端')
    parser.add_argument('--url', type=str, default=DEFAULT_API_URL,
                        help=f'模型API的URL地址，默认: {DEFAULT_API_URL}')
    parser.add_argument('--chatglm', action='store_true',
                        help='使用ChatGLM兼容格式的API')
    parser.add_argument('--file', '-f', type=str,
                        help='要分析的政策文件路径')
    parser.add_argument('--policy', '-p', type=str,
                        help='直接输入的政策文本')
    
    return parser.parse_args()

def main():
    """主函数"""
    # 解析命令行参数
    args = parse_args()
    
    # 显示当前连接信息
    print_colored(f"正在连接到模型API: {args.url}", Fore.CYAN)
    print_colored(f"API格式: {'ChatGLM兼容格式' if args.chatglm else '标准格式'}", Fore.CYAN)
    
    # 根据参数选择操作模式
    if args.file:
        print_colored(f"分析文件: {args.file}", Fore.CYAN)
        analyze_file(args.file, args.url, args.chatglm)
    elif args.policy:
        print_colored("分析政策文本", Fore.CYAN)
        process_policy(args.policy, args.url, args.chatglm)
    else:
        # 默认进入交互式聊天模式
        interactive_chat(args.url, args.chatglm)

if __name__ == "__main__":
    main()