#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
模型管理脚本 - 提供便捷接口来管理和测试项目使用的AI模型
"""

import os
import sys
import json
import time
import importlib
import importlib.util
import requests
import re  # 添加缺失的re模块导入
from dotenv import load_dotenv
import logging
from colorama import init, Fore, Style

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# 初始化colorama
init()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(project_root, "model_management.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

def print_colored(text, color=Fore.WHITE, style=Style.NORMAL, end='\n'):
    """打印彩色文本"""
    print(f"{style}{color}{text}{Style.RESET_ALL}", end=end)

def load_env_variables():
    """加载环境变量"""
    # 尝试加载.env文件
    env_path = os.path.join(project_root, '.env')
    load_dotenv(env_path)
    return {
        "API_KEY": os.getenv("API_KEY", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "BAIDU_API_KEY": os.getenv("BAIDU_API_KEY", ""),
        "BAIDU_SECRET_KEY": os.getenv("BAIDU_SECRET_KEY", "")
    }

def load_model_config():
    """动态加载模型配置"""
    try:
        # 动态导入配置模块
        config_path = os.path.join(project_root, "src", "config", "model_config.py")
        spec = importlib.util.spec_from_file_location("model_config", config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        
        # 返回模型配置
        return {
            "AVAILABLE_MODELS": getattr(config_module, "AVAILABLE_MODELS", {}),
            "DEFAULT_MODELS": getattr(config_module, "DEFAULT_MODELS", []),
            "MODEL_ENDPOINTS": getattr(config_module, "MODEL_ENDPOINTS", {})
        }
    except Exception as e:
        logger.error(f"加载模型配置失败: {str(e)}")
        print_colored(f"加载模型配置失败: {str(e)}", Fore.RED)
        return {
            "AVAILABLE_MODELS": {},
            "DEFAULT_MODELS": [],
            "MODEL_ENDPOINTS": {}
        }

def update_model_config(config_data):
    """更新模型配置文件"""
    try:
        config_path = os.path.join(project_root, "src", "config", "model_config.py")
        
        # 读取原始文件内容
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 1. 更新AVAILABLE_MODELS部分
        categories_str = []
        for category, models in config_data["AVAILABLE_MODELS"].items():
            models_str = []
            for model in models:
                models_str.append(f'        "{model}"')
            
            # 使用普通字符串拼接，避免f-string中的反斜杠问题
            category_str = '    "' + category + '": [\n' + ",\n".join(models_str) + '\n    ]'
            categories_str.append(category_str)
        
        available_models_str = "AVAILABLE_MODELS = {\n" + ",\n".join(categories_str) + "\n}"
        
        # 2. 更新DEFAULT_MODELS部分 - 简化处理方式，不再处理条件表达式
        default_models_list = []
        for model in config_data["DEFAULT_MODELS"]:
            if isinstance(model, str):
                default_models_list.append(f'    "{model}"')
        
        # 添加条件模型
        conditional_models = [
            '    "ernie-bot" if API_KEYS["baidu_api_key"] and API_KEYS["baidu_secret_key"] else None',
            '    "gpt-3.5-turbo" if API_KEYS["openai"] else None',
            '    "chatglm-local" if os.path.exists(MODEL_ENDPOINTS["model_chatglm"]) else None'
        ]
        
        # 生成DEFAULT_MODELS的完整字符串
        default_models_content = "DEFAULT_MODELS = [\n" + ",\n".join(default_models_list + conditional_models) + "\n]\n\n"
        default_models_content += "# 过滤掉None值\nDEFAULT_MODELS = [model for model in DEFAULT_MODELS if model is not None]\n\n"
        default_models_content += "# 如果没有可用模型，则至少使用qwen-turbo\nif not DEFAULT_MODELS:\n    DEFAULT_MODELS = [\"qwen-turbo\"]"
        
        # 3. 用正则表达式替换文件内容
        import re
        # 替换AVAILABLE_MODELS部分
        content = re.sub(r'AVAILABLE_MODELS = \{[^}]*\}', available_models_str, content, flags=re.DOTALL)
        
        # 替换DEFAULT_MODELS及其后续处理逻辑的整个部分
        content = re.sub(r'# 按优先级排列的默认模型.*?if not DEFAULT_MODELS:.*?\]', 
                        "# 按优先级排列的默认模型\n" + default_models_content, 
                        content, flags=re.DOTALL)
        
        # 保存更新后的文件
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info("成功更新模型配置文件")
        return True
    except Exception as e:
        logger.error(f"更新模型配置失败: {str(e)}")
        print_colored(f"更新模型配置失败: {str(e)}", Fore.RED)
        return False

def test_model(model_name, api_key=None):
    """测试模型连接性"""
    if (model_name == "0"):
        print_colored("已取消测试模型操作", Fore.YELLOW)
        return False

    print_colored(f"正在测试模型: {model_name}...", Fore.YELLOW)
    
    # 导入LLMService
    try:
        from src.services.llm_service import LLMService
        service = LLMService()
        
        # 设置简单的测试提示
        test_prompt = "你好，请简单介绍一下自己。回答限制在50字以内。"
        
        # 测试开始时间
        start_time = time.time()
        
        # 调用模型
        result = service.call_model(model_name, test_prompt)
        
        # 测试耗时
        elapsed_time = time.time() - start_time
        
        if result:
            print_colored(f"✓ 模型 {model_name} 测试成功! (耗时: {elapsed_time:.2f}秒)", Fore.GREEN)
            print_colored("模型响应:", Fore.CYAN)
            print_colored(f"  {result[:150]}{'...' if len(result) > 150 else ''}", Fore.WHITE)
            logger.info(f"模型 {model_name} 测试成功，耗时: {elapsed_time:.2f}秒")
            return True
        else:
            print_colored(f"✗ 模型 {model_name} 测试失败，无响应", Fore.RED)
            logger.error(f"模型 {model_name} 测试失败，无响应")
            return False
    except Exception as e:
        print_colored(f"✗ 测试模型时出错: {str(e)}", Fore.RED)
        logger.error(f"测试模型 {model_name} 时出错: {str(e)}")
        return False

def display_model_list(config_data):
    """显示当前配置的模型列表"""
    available_models = config_data["AVAILABLE_MODELS"]
    default_models = config_data["DEFAULT_MODELS"]
    
    print_colored("\n当前配置的模型类别:", Fore.CYAN, Style.BRIGHT)
    for category, models in available_models.items():
        print_colored(f"\n{category.upper()}:", Fore.YELLOW, Style.BRIGHT)
        for i, model in enumerate(models, 1):
            # 检查该模型是否在默认模型列表中
            is_default = model in default_models
            status = " (默认使用)" if is_default else ""
            print_colored(f"  {i}. {model}{status}", Fore.GREEN if is_default else Fore.WHITE)
    
    print()

def update_llm_service_for_model(model_name, category):
    """
    更新LLMService类以支持新增的模型
    
    Args:
        model_name: 模型名称
        category: 模型类别
        
    注意:
        - 该函数会自动修改 llm_service.py 文件以支持新模型
        - 目前主要支持阿里云API模型的自动更新
        - 对于非阿里云类别的模型，可能需要手动修改 llm_service.py
    """
    try:
        llm_service_path = os.path.join(project_root, "src", "services", "llm_service.py")
        
        # 读取原始文件内容
        with open(llm_service_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 判断是否需要更新
        if f'"{model_name}": "{model_name}"' in content:
            logger.info(f"模型 {model_name} 已在LLMService中配置，无需更新")
            return True
        
        # 更新步骤1: 添加模型到model_mapping字典
        import re
        
        # 查找model_mapping字典
        mapping_pattern = r'model_mapping = \{[^}]*\}'
        mapping_match = re.search(mapping_pattern, content, re.DOTALL)
        
        if mapping_match:
            # 在字典末尾添加新模型
            old_mapping = mapping_match.group(0)
            if old_mapping.strip().endswith("}"):
                # 如果字典以}结尾，在前面添加新条目
                new_mapping = old_mapping.replace("}", f',\n        # {category}模型映射\n        "{model_name}": "{model_name}"\n    }}')
            else:
                # 如果字典中已有内容，添加新行
                new_mapping = old_mapping + f',\n        # {category}模型映射\n        "{model_name}": "{model_name}"\n    }}'
            
            content = content.replace(old_mapping, new_mapping)
        
        # # 更新步骤2: 更新call_model方法
        # if category == "alicloud":
        #     # 查找处理阿里云模型的if语句
        #     alicloud_pattern = r'if model_name\.startswith\("qwen"\)(.*?):'
        #     alicloud_match = re.search(alicloud_pattern, content)
            
        #     if alicloud_match:
        #         # 添加对新模型的支持
        #         old_condition = alicloud_match.group(0)
        #         if "deepseek" in old_condition and model_name != "deepseek-r1":
        #             # 已经有deepseek模型的处理逻辑
        #             new_condition = old_condition.replace('startswith("qwen")', f'startswith("qwen") or model_name == "{model_name}"')
        #         elif model_name == "deepseek-r1" and "deepseek" not in old_condition:
        #             # 添加deepseek-r1
        #             new_condition = old_condition.replace('startswith("qwen")', 'startswith("qwen") or model_name == "deepseek-r1"')
        #         else:
        #             # 添加新模型
        #             new_condition = old_condition.replace('startswith("qwen")', f'startswith("qwen") or model_name == "{model_name}"')
                
        #         content = content.replace(old_condition, new_condition)
            
        #     # 更新OpenAI兼容模式的选择
        #     openai_pattern = r'if model\.startswith\("qwen"\)(.*?):'
        #     openai_match = re.search(openai_pattern, content)
            
        #     if openai_match:
        #         old_condition = openai_match.group(0)
        #         if model_name not in old_condition:
        #             new_condition = old_condition.replace('startswith("qwen")', f'startswith("qwen") or model == "{model_name}"')
        #             content = content.replace(old_condition, new_condition)
        
        # 保存更新后的文件
        with open(llm_service_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"成功更新LLMService以支持模型 {model_name}")
        return True
    except Exception as e:
        logger.error(f"更新LLMService失败: {str(e)}")
        print_colored(f"更新LLMService失败: {str(e)}", Fore.RED)
        return False

# 修改add_new_model函数，添加对LLMService的更新
def add_new_model():
    """添加新模型"""
    config_data = load_model_config()
    env_vars = load_env_variables()
    
    # 显示当前模型列表
    display_model_list(config_data)
    
    # 获取模型类别
    print_colored("\n选择要添加模型的类别:", Fore.CYAN, Style.BRIGHT)
    categories = list(config_data["AVAILABLE_MODELS"].keys())
    
    for i, category in enumerate(categories, 1):
        print_colored(f"  {i}. {category}", Fore.WHITE)
    
    print_colored("  0. 取消操作", Fore.YELLOW)
    
    choice = -1
    while choice < 0 or choice > len(categories):
        try:
            choice = int(input("\n请选择类别 [0-" + str(len(categories)) + "]: "))
            if choice == 0:
                print_colored("已取消添加模型操作", Fore.YELLOW)
                return
        except ValueError:
            print_colored("请输入有效的数字", Fore.RED)
    
    if choice == 0:
        # 创建新类别
        new_category = input("请输入新类别名称: ").strip()
        if not new_category:
            print_colored("类别名称不能为空", Fore.RED)
            return
        
        config_data["AVAILABLE_MODELS"][new_category] = []
        selected_category = new_category
    else:
        selected_category = categories[choice-1]
    
    # 获取新模型信息
    model_name = input("\n请输入模型名称 (例如: gpt-4-turbo) [输入0取消]: ").strip()
    if not model_name or model_name == "0":
        print_colored("已取消添加模型操作", Fore.YELLOW)
        return
    
    # 检查模型是否已存在
    for category, models in config_data["AVAILABLE_MODELS"].items():
        if model_name in models:
            print_colored(f"模型 {model_name} 已在 {category} 类别中存在", Fore.YELLOW)
            if input("是否继续添加? (y/n): ").lower() != 'y':
                return
    
    # 添加模型到选定类别
    config_data["AVAILABLE_MODELS"][selected_category].append(model_name)
    
    # 询问是否添加到默认模型列表
    if input("是否将此模型添加到默认使用的模型列表? (y/n): ").lower() == 'y':
        if model_name not in config_data["DEFAULT_MODELS"]:
            config_data["DEFAULT_MODELS"].append(model_name)
    
    # 更新配置文件
    if update_model_config(config_data):
        print_colored(f"\n✓ 成功添加模型 {model_name} 到 {selected_category} 类别", Fore.GREEN)
        
        # 更新LLMService以支持新模型
        if selected_category == "alicloud":
            print_colored("正在更新LLMService以支持新模型...", Fore.YELLOW)
            if update_llm_service_for_model(model_name, selected_category):
                print_colored("✓ 成功更新LLMService", Fore.GREEN)
            else:
                print_colored("✗ 更新LLMService失败，新模型可能无法正常工作", Fore.RED)
        
        # 询问是否测试新模型
        if input("\n是否测试新添加的模型? (y/n): ").lower() == 'y':
            test_model(model_name)
    else:
        print_colored("\n✗ 添加模型失败", Fore.RED)

def remove_model_references(model_name):
    """在相关文件中删除对特定模型的引用"""
    try:
        # 1. 更新 llm_service.py 文件，删除模型映射及相关行
        llm_service_path = os.path.join(project_root, "src", "services", "llm_service.py")
        if os.path.exists(llm_service_path):
            with open(llm_service_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找可能的模式包括注释行、逗号行和键值对行
            pattern = rf',\s*#.*模型映射\s*"{re.escape(model_name)}": ".*?"'
            match = re.search(pattern, content)
            
            if match:
                # 找到完整的模式（逗号+注释+键值对）
                full_pattern = match.group(0)
                # 直接替换为空
                new_content = content.replace(full_pattern, '')
                
                if new_content != content:
                    with open(llm_service_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    logger.info(f"已从 llm_service.py 的model_mapping中移除模型 {model_name} 及其相关行")
                    return True
            else:
                # 如果找不到完整模式，尝试只找键值对
                simple_pattern = rf'[,\s]*"{re.escape(model_name)}": ".*?"[,\s]*'
                match = re.search(simple_pattern, content)
                if match:
                    # 找到了键值对
                    full_pattern = match.group(0)
                    # 如果这是最后一项，保留前面的逗号；如果不是，则替换为逗号
                    replacement = "" if full_pattern.strip().startswith(",") else ""
                    new_content = content.replace(full_pattern, replacement)
                    
                    if new_content != content:
                        with open(llm_service_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        logger.info(f"已从 llm_service.py 的model_mapping中移除模型 {model_name}")
                        return True
                
                logger.info(f"在llm_service.py的model_mapping字典中未找到模型 {model_name} 的条目")
        
        return True
    except Exception as e:
        logger.error(f"删除模型引用时出错: {str(e)}")
        print_colored(f"删除模型引用时出错: {str(e)}", Fore.RED)
        return False

def remove_model():
    """移除模型"""
    config_data = load_model_config()
    
    # 显示当前模型列表
    display_model_list(config_data)
    
    # 获取要删除的模型
    model_name = input("\n请输入要移除的模型名称 [输入0取消]: ").strip()
    if not model_name or model_name == "0":
        print_colored("已取消移除模型操作", Fore.YELLOW)
        return
    
    # 查找模型并删除
    model_found = False
    for category, models in config_data["AVAILABLE_MODELS"].items():
        if (model_name in models):
            model_found = True
            # 从类别中删除
            config_data["AVAILABLE_MODELS"][category].remove(model_name)
            print_colored(f"已从 {category} 类别中移除模型 {model_name}", Fore.YELLOW)
    
    # 从默认模型列表中删除
    if model_name in config_data["DEFAULT_MODELS"]:
        config_data["DEFAULT_MODELS"].remove(model_name)
        print_colored(f"已从默认模型列表中移除模型 {model_name}", Fore.YELLOW)
    
    if not model_found:
        print_colored(f"未找到模型 {model_name}", Fore.RED)
        return
    
    # 更新配置文件
    config_updated = update_model_config(config_data)
    
    # 尝试从llm_service中移除模型专属代码
    # 这里只会处理特定模型的专用条件分支
    references_check = remove_model_references(model_name)
    
    if config_updated:
        print_colored(f"\n✓ 成功从配置中移除模型 {model_name}", Fore.GREEN)
        if references_check:
            print_colored("√ 检查并清理了相关代码引用", Fore.GREEN)
        
        # 添加提示而不是自动修改其他文件
        print_colored("\n提示: 您可能需要手动检查以下文件中的模型引用:", Fore.YELLOW)
        print_colored(f"  - src/config/prompt_templates.py", Fore.WHITE)
        print_colored(f"  - scripts/run_analysis.py", Fore.WHITE)
        print_colored(f"  - 其他可能包含模型名称'{model_name}'的文件", Fore.WHITE)
    else:
        print_colored("\n✗ 移除模型失败", Fore.RED)

def toggle_default_model():
    """设置或取消某个模型作为默认模型"""
    config_data = load_model_config()
    
    # 显示当前模型列表
    display_model_list(config_data)
    
    # 获取要设置的模型
    model_name = input("\n请输入要设置或取消默认状态的模型名称 [输入0取消]: ").strip()
    if not model_name or model_name == "0":
        print_colored("已取消设置默认模型操作", Fore.YELLOW)
        return
    
    # 查找模型
    model_found = False
    for category, models in config_data["AVAILABLE_MODELS"].items():
        if model_name in models:
            model_found = True
            break
    
    if not model_found:
        print_colored(f"未找到模型 {model_name}", Fore.RED)
        return
    
    # 检查模型是否已经在默认列表中
    is_default = model_name in config_data["DEFAULT_MODELS"]
    
    if is_default:
        # 从默认列表中移除
        config_data["DEFAULT_MODELS"].remove(model_name)
        print_colored(f"已将 {model_name} 从默认模型列表中移除", Fore.YELLOW)
    else:
        # 添加到默认列表
        config_data["DEFAULT_MODELS"].append(model_name)
        print_colored(f"已将 {model_name} 添加到默认模型列表中", Fore.GREEN)
    
    # 更新配置文件
    if update_model_config(config_data):
        print_colored(f"\n✓ 成功{'' if not is_default else '取消'}{model_name}作为默认模型", Fore.GREEN)
        return True
    else:
        print_colored("\n✗ 更新默认模型设置失败", Fore.RED)
        return False

def test_api_connection():
    """测试API连接"""
    print_colored("\n=== API连接测试 ===", Fore.CYAN, Style.BRIGHT)
    print_colored("1. 测试阿里云API", Fore.WHITE)
    print_colored("2. 测试百度API", Fore.WHITE)
    print_colored("3. 测试OpenAI API", Fore.WHITE)
    print_colored("0. 返回上一级", Fore.YELLOW)
    
    choice = input("\n请选择要测试的API [0-3]: ").strip()
    
    if choice == "0":
        print_colored("已返回主菜单", Fore.YELLOW)
        return

    env_vars = load_env_variables()
    
    print_colored("\n正在测试API连接...", Fore.CYAN, Style.BRIGHT)
    
    # 测试阿里云API
    if env_vars["API_KEY"]:
        print_colored("\n测试阿里云API连接:", Fore.YELLOW)
        try:
            url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
            headers = {
                "Authorization": f"Bearer {env_vars['API_KEY']}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "qwen-turbo",
                "input": {
                    "messages": [
                        {"role": "user", "content": "你好"}
                    ]
                }
            }
            
            start_time = time.time()
            response = requests.post(url, headers=headers, json=data)
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                print_colored(f"✓ 阿里云API连接成功! (延迟: {elapsed_time:.2f}秒)", Fore.GREEN)
            else:
                print_colored(f"✗ 阿里云API返回错误: {response.status_code}, {response.text}", Fore.RED)
        except Exception as e:
            print_colored(f"✗ 阿里云API连接测试失败: {str(e)}", Fore.RED)
    else:
        print_colored("✗ 未配置阿里云API密钥", Fore.RED)
    
    # 测试OpenAI API
    if env_vars["OPENAI_API_KEY"]:
        print_colored("\n测试OpenAI API连接:", Fore.YELLOW)
        try:
            from openai import OpenAI
            client = OpenAI(api_key=env_vars["OPENAI_API_KEY"])
            
            start_time = time.time()
            response = client.models.list()
            elapsed_time = time.time() - start_time
            
            if response:
                print_colored(f"✓ OpenAI API连接成功! (延迟: {elapsed_time:.2f}秒)", Fore.GREEN)
                print_colored(f"  可用模型数量: {len(response.data)}", Fore.WHITE)
        except Exception as e:
            print_colored(f"✗ OpenAI API连接测试失败: {str(e)}", Fore.RED)
    else:
        print_colored("✗ 未配置OpenAI API密钥", Fore.RED)
    
    # 测试百度API
    if env_vars["BAIDU_API_KEY"] and env_vars["BAIDU_SECRET_KEY"]:
        print_colored("\n测试百度API连接:", Fore.YELLOW)
        try:
            # 获取access token
            token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={env_vars['BAIDU_API_KEY']}&client_secret={env_vars['BAIDU_SECRET_KEY']}"
            
            start_time = time.time()
            response = requests.post(token_url)
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200 and 'access_token' in response.json():
                print_colored(f"✓ 百度API连接成功! (延迟: {elapsed_time:.2f}秒)", Fore.GREEN)
            else:
                print_colored(f"✗ 百度API返回错误: {response.status_code}, {response.text}", Fore.RED)
        except Exception as e:
            print_colored(f"✗ 百度API连接测试失败: {str(e)}", Fore.RED)
    else:
        print_colored("✗ 未配置百度API密钥", Fore.RED)

def main_menu():
    """主菜单"""
    while True:
        print_colored("\n=== 模型管理工具 ===", Fore.CYAN, Style.BRIGHT)
        print_colored("1. 显示当前配置的模型", Fore.WHITE)
        print_colored("2. 添加新模型", Fore.WHITE)
        print_colored("3. 移除现有模型", Fore.WHITE)
        print_colored("4. 设置/取消默认模型", Fore.WHITE)
        print_colored("5. 测试模型连接", Fore.WHITE)
        print_colored("6. 测试API连接", Fore.WHITE)
        print_colored("0. 退出", Fore.WHITE)
        
        choice = input("\n请选择操作 [0-6]: ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            display_model_list(load_model_config())
        elif choice == '2':
            add_new_model()
        elif choice == '3':
            remove_model()
        elif choice == '4':
            toggle_default_model()
        elif choice == '5':
            config_data = load_model_config()
            display_model_list(config_data)
            model_name = input("\n请输入要测试的模型名称 [输入0取消]: ").strip()
            if model_name and model_name != "0":
                test_model(model_name)
            else:
                print_colored("已取消测试模型操作", Fore.YELLOW)
        elif choice == '6':
            test_api_connection()
        else:
            print_colored("无效的选择，请重新输入", Fore.RED)

if __name__ == "__main__":
    print_colored("欢迎使用模型管理工具!", Fore.CYAN, Style.BRIGHT)
    print_colored("该工具可以帮助您轻松地管理项目中使用的AI模型\n", Fore.CYAN)
    
    # 检查依赖
    try:
        import colorama
    except ImportError:
        print("缺少必要的依赖，正在安装...")
        os.system("pip install colorama")
        from colorama import init, Fore, Style
        init()
    
    main_menu()
