#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
启动本地大语言模型服务的脚本
基于Transformers和FastAPI实现的简易模型服务器
支持多种开源大语言模型，默认使用Qwen系列模型
"""

import os
import sys
import argparse
import torch
from pathlib import Path
import logging
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("local_model_server.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# 默认设置
DEFAULT_MODEL_PATH = os.getenv("LOCAL_MODEL_PATH", "Qwen/Qwen2-7B-Instruct")  # 默认Qwen2-7B模型
DEFAULT_PORT = int(os.getenv("LOCAL_MODEL_PORT", "8001"))
DEFAULT_HOST = os.getenv("LOCAL_MODEL_HOST", "0.0.0.0")
DEFAULT_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# FastAPI实例
app = FastAPI()

# 定义请求模型
class ChatRequest(BaseModel):
    conversation_id: str  # 会话ID
    prompt: str           # 用户输入的提示词
    history: Optional[List[Dict[str, str]]] = []  # 聊天历史
    max_new_tokens: Optional[int] = 512  # 生成的最大token数
    temperature: Optional[float] = 0.7  # 温度参数
    top_p: Optional[float] = 0.9  # 采样参数

# 定义响应模型
class ChatResponse(BaseModel):
    conversation_id: str  # 会话ID
    response: str         # 模型生成的回复
    history: Optional[List[Dict[str, str]]] = None  # 更新后的聊天历史

# 保存对话历史的全局字典
conversation_histories: Dict[str, List[Dict[str, str]]] = {}

# 全局变量用于存储模型和分词器
model = None
tokenizer = None

def initialize_model(model_path, device="cuda", use_half_precision=True, max_memory=None):
    """初始化模型和分词器"""
    global model, tokenizer
    
    logger.info(f"正在加载模型和分词器: {model_path}")
    logger.info(f"设备: {device}")
    
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        # 根据设备和内存限制设置加载参数
        load_kwargs = {"device_map": "auto"}
        
        # 如果指定了最大内存，则添加到加载参数中
        if max_memory:
            load_kwargs["max_memory"] = max_memory
        
        # 如果设备为CUDA且启用了半精度，则添加到加载参数中
        if device == "cuda" and use_half_precision:
            load_kwargs["torch_dtype"] = torch.float16
        
        # 加载分词器
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        
        # 加载模型
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            **load_kwargs
        )
        
        logger.info("模型和分词器加载成功")
        logger.info(f"模型部署情况: {getattr(model, 'hf_device_map', device)}")
        
        # 清理CUDA缓存
        if device == "cuda":
            torch.cuda.empty_cache()
            
        return True
    except Exception as e:
        logger.error(f"加载模型失败: {str(e)}")
        return False

@app.on_event("startup")
async def startup_event():
    """服务启动时执行"""
    # 模型初始化将在命令行参数中处理，而不是在这里
    pass

@app.get("/")
async def root():
    """根路径处理函数"""
    return {"message": "本地大模型API服务已启动", "status": "running"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """聊天API接口"""
    global model, tokenizer
    
    # 检查模型是否已加载
    if model is None or tokenizer is None:
        raise HTTPException(status_code=500, detail="模型尚未加载，请先初始化模型")
    
    try:
        # 获取请求参数
        conversation_id = request.conversation_id
        prompt = request.prompt
        history = request.history or []
        
        # 更新或创建会话历史
        if not history:
            if conversation_id in conversation_histories:
                history = conversation_histories[conversation_id]
            else:
                # 新会话，添加系统指令
                history = [{"role": "system", "content": "你是一个有用的AI助手。请提供准确、有益的回答。"}]
        
        # 添加用户输入到历史记录
        history.append({"role": "user", "content": prompt})
        
        # 使用模型和分词器生成回复
        text = tokenizer.apply_chat_template(
            history,
            tokenize=False, 
            add_generation_prompt=True
        )
        
        inputs = tokenizer([text], return_tensors="pt").to(model.device)
        
        # 生成回复
        outputs = model.generate(
            **inputs,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
            top_p=request.top_p
        )
        
        # 解码输出
        response_text = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
        
        # 提取模型的实际回复部分 - 根据模型不同可能需要调整
        # 这里假设回复在最后一个assistant角色的内容之后
        response_parts = response_text.split("assistant")
        if len(response_parts) > 1:
            response = response_parts[-1].strip()
        else:
            response = response_text
        
        # 清理回复中可能存在的提示词痕迹
        if ":" in response[:20]:  # 检查是否有类似 ":" 开头的模式
            response = response.split(":", 1)[-1].strip()
        
        # 添加回复到历史记录
        history.append({"role": "assistant", "content": response})
        
        # 更新会话历史
        conversation_histories[conversation_id] = history
        
        # 安排后台任务清理CUDA缓存
        if torch.cuda.is_available():
            background_tasks.add_task(torch.cuda.empty_cache)
        
        return ChatResponse(
            conversation_id=conversation_id,
            response=response,
            history=history
        )
        
    except torch.cuda.OutOfMemoryError:
        # 清理CUDA缓存
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        raise HTTPException(status_code=500, detail="GPU内存不足，请尝试减小max_new_tokens或使用更小的模型")
    except Exception as e:
        logger.error(f"生成回复时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")

@app.post("/api/chat")
async def chatglm_compatible_api(request: dict, background_tasks: BackgroundTasks):
    """兼容ChatGLM API格式的接口"""
    try:
        # 提取ChatGLM格式的请求参数
        prompt = request.get("prompt", "")
        history = request.get("history", [])
        
        # 转换为本系统的请求格式
        transformed_history = []
        for h_pair in history:
            if isinstance(h_pair, list) and len(h_pair) == 2:
                transformed_history.extend([
                    {"role": "user", "content": h_pair[0]},
                    {"role": "assistant", "content": h_pair[1]}
                ])
        
        # 创建内部请求
        internal_request = ChatRequest(
            conversation_id="chatglm_compatible",
            prompt=prompt,
            history=transformed_history,
            temperature=request.get("temperature", 0.7),
            max_new_tokens=request.get("max_length", 512),
            top_p=request.get("top_p", 0.9)
        )
        
        # 调用内部聊天接口
        response = await chat(internal_request, background_tasks)
        
        # 转换为ChatGLM格式的响应
        chatglm_response = {
            "response": response.response,
            "history": history + [[prompt, response.response]]
        }
        
        return chatglm_response
    except Exception as e:
        logger.error(f"处理兼容API请求时出错: {str(e)}")
        return {"response": f"处理请求时出错: {str(e)}", "history": history}

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='启动本地大语言模型服务')
    parser.add_argument('--model_path', type=str, default=DEFAULT_MODEL_PATH,
                        help='模型路径，支持本地路径或Hugging Face模型名称')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help='服务端口号')
    parser.add_argument('--host', type=str, default=DEFAULT_HOST,
                        help='服务主机地址')
    parser.add_argument('--device', type=str, default=DEFAULT_DEVICE,
                        choices=['cpu', 'cuda', 'mps'],
                        help='运行设备，支持cpu、cuda或mps(苹果M系列芯片)')
    parser.add_argument('--use_half', action='store_true',
                        help='使用FP16半精度加载模型，可减少显存占用')
    parser.add_argument('--max_memory', type=str, 
                        help='每个GPU设备的最大显存限制，格式为"0:10GiB,1:10GiB"')
    
    return parser.parse_args()

def parse_max_memory(max_memory_str):
    """解析最大内存参数"""
    if not max_memory_str:
        return None
    
    try:
        # 处理格式如 "0:10GiB,1:10GiB"
        memory_dict = {}
        for device_mem in max_memory_str.split(','):
            device, mem = device_mem.strip().split(':')
            memory_dict[int(device) if device.isdigit() else device] = mem
        return memory_dict
    except Exception as e:
        logger.error(f"无法解析最大内存参数: {str(e)}")
        return None

def main():
    """主函数"""
    # 解析命令行参数
    args = parse_args()
    
    # 解析最大内存设置
    max_memory = parse_max_memory(args.max_memory)
    
    # 初始化模型
    success = initialize_model(
        args.model_path, 
        args.device, 
        args.use_half,
        max_memory
    )
    
    if not success:
        logger.error("模型初始化失败，无法启动服务")
        sys.exit(1)
    
    # 启动FastAPI服务
    logger.info(f"正在启动API服务，地址: {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()