import os
import json
import threading
import requests
import time
import logging
from openai import OpenAI

def setup_logger(name):
    """创建并配置一个日志记录器"""
    logger = logging.getLogger(f"llm_service.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

class LLMService:
    def __init__(self, model_endpoints=None):
        """
        初始化LLM服务
        
        Args:
            model_endpoints: 字典，包含模型名称和对应的API端点，如果为None则使用默认端点
        """
        if model_endpoints is None:
            # 默认端点配置
            self.model_endpoints = {
                "model_chatglm": "http://0.0.0.0:8002/chat",
                "model_deepseek": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model_baidu": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
                "model_openai": "https://api.openai.com/v1"
            }
        else:
            self.model_endpoints = model_endpoints
            
        self.api_key = os.getenv("API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.baidu_api_key = os.getenv("BAIDU_API_KEY", "")
        self.baidu_secret_key = os.getenv("BAIDU_SECRET_KEY", "")
        self.lock = threading.Lock()
        
        # 获取百度访问令牌(如果配置了百度API)
        self.baidu_access_token = None
        if self.baidu_api_key and self.baidu_secret_key:
            self._get_baidu_access_token()
    
    def _get_baidu_access_token(self):
        """获取百度API访问令牌"""
        try:
            token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={self.baidu_api_key}&client_secret={self.baidu_secret_key}"
            response = requests.post(token_url)
            if response.status_code == 200:
                self.baidu_access_token = response.json().get("access_token")
                logger = setup_logger("baidu")
                logger.info("成功获取百度访问令牌")
            else:
                logger = setup_logger("baidu")
                logger.error(f"获取百度访问令牌失败: {response.text}")
        except Exception as e:
            logger = setup_logger("baidu")
            logger.error(f"获取百度访问令牌出错: {str(e)}")
    
    def call_model(self, model_name, prompt, max_retries=3):
        """
        调用指定的模型
        
        Args:
            model_name: 模型名称
            prompt: 发送给模型的文本
            max_retries: 最大重试次数
        
        Returns:
            模型返回的文本内容
        """
        logger = setup_logger(model_name)
        
        # 根据模型名称确定调用方法
        if model_name.startswith("qwen") or model_name.startswith("deepseek"):
            logger.info(f"使用 阿里云API 调用: {model_name}")
            return self.call_aliyun_api(prompt, max_retries, model_name)
        elif "chatglm" in model_name.lower():
            logger.info(f"使用 ChatGLM API 调用: {model_name}")
            return self.call_chatglm_api(prompt, max_retries, model_name)
        elif "ernie" in model_name.lower():
            logger.info(f"使用百度文心 API 调用: {model_name}")
            return self.call_baidu_api(prompt, max_retries, model_name)
        elif "gpt" in model_name.lower() and self.openai_api_key:
            logger.info(f"使用 OpenAI API 调用: {model_name}")
            return self.call_openai_api(prompt, max_retries, model_name)
        else:
            error_msg = f"未识别的模型名称: {model_name}，请检查配置"
            logger.error(error_msg)
            return None
    
    def call_aliyun_api(self, prompt, max_retries=3, model="qwen-turbo"):
        """
        调用阿里云API（支持Qwen, DeepSeek等模型）
        
        Args:
            prompt: 发送给模型的文本
            max_retries: 最大重试次数
            model: 具体模型名称
        
        Returns:
            模型返回的文本内容
        """
        logger = setup_logger(model)
        
        # 1. 根据模型类型定义正确的模型ID映射
        model_mapping = {
            # 通义千问系列模型映射
            "qwen-turbo": "qwen-turbo",
            "qwen-plus": "qwen-plus",
            "qwen-max": "qwen-max", 
            "qwen-72b-chat": "qwen-72b-chat",
            "qwen2-7b-instruct": "qwen2-7b-instruct",
            "qwen2-72b-instruct": "qwen2-72b-instruct",
            
            # DeepSeek模型映射
            "deepseek-r1": "deepseek-r1",  # 添加deepseek-r1的正确映射
            
            # 百川模型映射 - 正确的模型ID
            "baichuan2-7b-chat": "Baichuan2-7B-Chat",
            "baichuan2-13b-chat": "Baichuan2-13B-Chat",
            
            # Llama模型映射 - 正确的模型ID
            "llama2-7b-chat": "Llama-2-7b-chat",
            "llama2-13b-chat": "Llama-2-13b-chat",
            # alicloud模型映射
            "qwen-long": "qwen-long"
    
    ,
        # alicloud模型映射
        "deepseek-v3": "deepseek-v3"
    }
        
        # 获取正确的模型ID
        actual_model_id = model_mapping.get(model, model)
        
        # 为不同模型设置合适的max_tokens值
        max_tokens_value = 2000  # 设置为安全值
        
        # 针对特定模型调整max_tokens
        if "qwen-72b" in model or "qwen2-72b" in model:
            max_tokens_value = 2000  # 对于72B模型，限制为2000
        elif "qwen" in model or "baichuan" in model or "llama" in model:
            max_tokens_value = 4000  # 其他模型保持4000

        # 2. 确定使用的API调用方式
        # 对于通义千问系列和deepseek系列可以使用OpenAI兼容模式
        if model.startswith("qwen") or model == "deepseek-v3" or model == "qwen-long" or model == "deepseek-r1":
            # 使用OpenAI兼容模式
            return self._call_aliyun_openai_compatible(prompt, actual_model_id, max_retries, max_tokens_value)
        else:
            # 使用原生API模式
            return self._call_aliyun_native_api(prompt, actual_model_id, max_retries, max_tokens_value)
    
    def _call_aliyun_openai_compatible(self, prompt, model, max_retries=3, max_tokens=4000):
        """使用OpenAI兼容模式调用阿里云API (适用于通义千问系列)"""
        logger = setup_logger(model)
        
        for attempt in range(max_retries):
            try:
                client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
                )
                
                start_time = time.time()
                logger.info(f"开始使用OpenAI兼容模式调用阿里云API: {model}")
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "你是一个善于分析政策文本的助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    top_p=0.7,
                    max_tokens=max_tokens
                )
                
                elapsed_time = time.time() - start_time
                logger.info(f"阿里云API响应时间: {elapsed_time:.2f}秒")
                
                return response.choices[0].message.content
            
            except Exception as e:
                logger.warning(f"调用阿里云API错误: {str(e)} (第{attempt+1}次重试)")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"达到最大重试次数，放弃调用阿里云API，错误信息: {str(e)}")
                    return None
    
    def _call_aliyun_native_api(self, prompt, model, max_retries=3, max_tokens=4000):
        """使用原生API调用阿里云API (适用于Baichuan、Llama等基础模型)"""
        logger = setup_logger(model)
        
        # 确定API路径
        api_url = "https://dashscope.aliyuncs.com/api/v1/services/foundation-models/text-generation/generation"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                logger.info(f"开始使用原生模式调用阿里云API: {model}")
                
                # 构建请求数据 - 使用原生格式
                data = {
                    "model": model,
                    "input": {
                        "messages": [
                            {"role": "system", "content": "你是一个善于分析政策文本的助手。"},
                            {"role": "user", "content": prompt}
                        ]
                    },
                    "parameters": {
                        "temperature": 0.1,
                        "top_p": 0.7,
                        "max_tokens": max_tokens
                    }
                }
                
                response = requests.post(api_url, headers=headers, json=data)
                response.raise_for_status()  # 如果请求失败，会抛出异常
                
                elapsed_time = time.time() - start_time
                logger.info(f"阿里云API响应时间: {elapsed_time:.2f}秒")
                
                result = response.json()
                # 根据阿里云API返回格式提取内容
                if "output" in result and "text" in result["output"]:
                    return result["output"]["text"]
                elif "output" in result and "message" in result["output"]:
                    return result["output"]["message"]
                else:
                    logger.warning(f"无法解析API返回内容: {result}")
                    return str(result)
                
            except Exception as e:
                logger.warning(f"调用阿里云API错误: {str(e)} (第{attempt+1}次重试)")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"达到最大重试次数，放弃调用阿里云API，错误信息: {str(e)}")
                    return None
    
    def call_chatglm_api(self, prompt, max_retries=3, model="chatglm-local"):
        """调用本地ChatGLM API"""
        logger = setup_logger(model)
        endpoint = self.model_endpoints.get("model_chatglm", "http://0.0.0.0:8002/chat")
        
        for attempt in range(max_retries):
            try:
                headers = {"Content-Type": "application/json"}
                data = {
                    "prompt": prompt,
                    "history": [],
                    "temperature": 0.01,
                    "top_p": 0.3
                }
                
                start_time = time.time()
                logger.info(f"开始调用ChatGLM API...")
                
                response = requests.post(endpoint, headers=headers, json=data)
                response.raise_for_status()
                
                elapsed_time = time.time() - start_time
                logger.info(f"ChatGLM API响应时间: {elapsed_time:.2f}秒")
                
                result = response.json()
                return result.get("response", "")
            
            except Exception as e:
                logger.warning(f"调用ChatGLM API错误: {str(e)} (第{attempt+1}次重试)")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"达到最大重试次数，放弃调用ChatGLM API")
                    return None
    
    def call_baidu_api(self, prompt, max_retries=3, model="ernie-bot"):
        """调用百度文心API"""
        logger = setup_logger(model)
        
        # 如果没有访问令牌，尝试获取
        if not self.baidu_access_token:
            self._get_baidu_access_token()
            if not self.baidu_access_token:
                logger.error("无法获取百度访问令牌，无法调用百度模型")
                return None
        
        # 根据模型名称选择合适的API端点
        model_map = {
            "ernie-bot-4": "/ernie-bot-4",
            "ernie-bot": "/ernie-bot",
            "ernie-bot-turbo": "/ernie-bot-turbo"
        }
        
        # 默认使用ernie-bot
        model_endpoint = model_map.get(model.lower(), "/ernie-bot")
        api_url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat{model_endpoint}?access_token={self.baidu_access_token}"
        
        for attempt in range(max_retries):
            try:
                headers = {"Content-Type": "application/json"}
                data = {
                    "messages": [
                        {"role": "system", "content": "你是一个善于分析政策文本的助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "top_p": 0.7
                }
                
                start_time = time.time()
                logger.info(f"开始调用百度文心API: {model}")
                
                response = requests.post(api_url, headers=headers, json=data)
                response.raise_for_status()
                
                elapsed_time = time.time() - start_time
                logger.info(f"百度文心API响应时间: {elapsed_time:.2f}秒")
                
                result = response.json()
                return result.get("result", "")
            
            except Exception as e:
                logger.warning(f"调用百度文心API错误: {str(e)} (第{attempt+1}次重试)")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"达到最大重试次数，放弃调用百度文心API")
                    return None
    
    def call_openai_api(self, prompt, max_retries=3, model="gpt-3.5-turbo"):
        """调用OpenAI API"""
        logger = setup_logger(model)
        
        for attempt in range(max_retries):
            try:
                client = OpenAI(
                    api_key=self.openai_api_key
                )
                
                start_time = time.time()
                logger.info(f"开始调用OpenAI API: {model}")
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "你是一个善于分析政策文本的助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    top_p=0.7,
                    max_tokens=4000
                )
                
                elapsed_time = time.time() - start_time
                logger.info(f"OpenAI API响应时间: {elapsed_time:.2f}秒")
                
                return response.choices[0].message.content
            
            except Exception as e:
                logger.warning(f"调用OpenAI API错误: {str(e)} (第{attempt+1}次重试)")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"达到最大重试次数，放弃调用OpenAI API")
                    return None
    
    def process_prompts_parallel(self, models, prompt):
        """并行处理同一个提示使用不同模型"""
        threads = []
        results = {}
        self.lock = threading.Lock()

        def worker(model_name):
            try:
                start_time = time.time()
                logger = setup_logger(model_name)
                logger.info(f"开始处理模型 {model_name} 的请求...")
                
                result = self.call_model(model_name, prompt)
                elapsed_time = time.time() - start_time

                if result is None:
                    with self.lock:
                        results[model_name] = {
                            "content": None,
                            "time": elapsed_time,
                            "status": "error",
                            "error": f"未识别的模型名称或API调用失败: {model_name}"
                        }
                        logger.error(f"模型 {model_name} 调用失败")
                else:
                    with self.lock:
                        results[model_name] = {
                            "content": result,
                            "time": elapsed_time,
                            "status": "success"
                        }
                        logger.info(f"模型 {model_name} 处理成功，耗时: {elapsed_time:.2f}秒")

            except Exception as e:
                error_msg = f"处理时发生异常: {str(e)}"
                logger.error(f"模型 {model_name} {error_msg}")
                with self.lock:
                    results[model_name] = {
                        "content": None,
                        "time": time.time() - start_time if 'start_time' in locals() else 0,
                        "status": "error",
                        "error": error_msg
                    }
        
        # 创建并启动线程
        for model_name in models:
            thread = threading.Thread(target=worker, args=(model_name,))
            thread.daemon = True  # 设置为后台线程
            threads.append(thread)
            thread.start()

        # 等待所有线程完成，添加超时处理
        for thread in threads:
            thread.join(timeout=300)  # 设置5分钟超时
            
        # 检查是否所有模型都有结果
        for model_name in models:
            if model_name not in results:
                results[model_name] = {
                    "content": None,
                    "status": "error",
                    "error": "处理超时或线程未正常完成"
                }

        return results

def call_models(prompt, models=None):
    """
    使用指定模型或默认模型调用LLM，处理给定的提示
    
    Args:
        prompt: 要发送给模型的提示文本
        models: 要使用的模型列表，如果为None，则使用默认模型列表
        
    Returns:
        不同模型的响应结果以及元数据
    """
    if models is None:
        # 使用环境变量来决定默认使用的模型
        if os.getenv("OPENAI_API_KEY"):
            # 如果有OpenAI API密钥，添加GPT模型
            models = ["qwen-turbo", "gpt-3.5-turbo"]
        elif os.getenv("BAIDU_API_KEY") and os.getenv("BAIDU_SECRET_KEY"):
            # 如果有百度API密钥，添加文心模型
            models = ["qwen-turbo", "ernie-bot"]
        else:
            # 默认只使用阿里云可用的模型
            models = ["qwen-turbo", "qwen-plus"]
    
    service = LLMService()
    model_results = service.process_prompts_parallel(models, prompt)
    
    # 添加原始提示作为结果的一部分
    for model_name in model_results:
        if model_results[model_name]["status"] == "success":
            model_results[model_name]["prompt"] = prompt
    
    return model_results

def save_results_to_json(results, output_dir, filename_prefix="model_comparison"):
    """将结果保存为JSON文件"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"{filename_prefix}_{timestamp}.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print(f"结果已保存到: {output_file}")
    return output_file

# 导出的函数和类
__all__ = ['LLMService', 'call_models', 'save_results_to_json', 'setup_logger']