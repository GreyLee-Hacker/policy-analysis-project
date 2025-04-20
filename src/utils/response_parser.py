import re
import json
import logging

logger = logging.getLogger(__name__)

def parse_housing_elements(response_text):
    """
    将housing模板的文本响应解析为JSON格式，支持提取多个七步要素集合
    
    一个完整的七步要素集合包括：
    policy_object, policy_stage, policy_type, policy_tool, 
    policy_geo_scope, policy_target_scope, tool_parameter
    
    返回结果是一个列表，每个元素是一个七步要素的字典
    """
    # 定义要提取的元素
    elements = ["policy_object", "policy_stage", "policy_type", "policy_tool", 
                "policy_geo_scope", "policy_target_scope", "tool_parameter"]
    
    # 检查是否存在多个七步要素集合（可能多个policy_object标记）
    policy_objects = re.findall(r"policy_object:\s*([^;]+)", response_text)
    
    # 如果找不到任何policy_object，返回空结果
    if not policy_objects:
        logger.warning("未找到任何policy_object")
        return [{"error": "未提取到七步要素"}]
    
    # 如果只有一个policy_object，使用原来的方式处理
    if len(policy_objects) == 1:
        result = {}
        for element in elements:
            pattern = rf"{element}:\s*([^;]+)"
            match = re.search(pattern, response_text)
            if match:
                result[element] = match.group(1).strip()
            else:
                result[element] = "未提取"
        return [result]
    
    # 如果有多个policy_object，需要尝试匹配每个完整的七步要素集合
    # 先尝试划分文本为多个部分
    results = []
    
    # 使用policy_object作为分隔点
    parts = re.split(r"(?=policy_object:)", response_text)
    
    for part in parts:
        if not part.strip():
            continue
            
        if not re.search(r"policy_object:", part):
            continue
            
        # 提取当前部分的所有元素
        current_result = {}
        for element in elements:
            pattern = rf"{element}:\s*([^;]+)"
            match = re.search(pattern, part)
            if match:
                current_result[element] = match.group(1).strip()
            else:
                # 如果缺少某个元素，尝试从整个文本中查找
                match_full = re.search(pattern, response_text)
                if match_full:
                    current_result[element] = match_full.group(1).strip()
                else:
                    current_result[element] = "未提取"
        
        # 只有当至少有policy_object有值时，才添加到结果中
        if current_result.get("policy_object") and current_result.get("policy_object") != "未提取":
            results.append(current_result)
    
    # 如果没有成功解析出任何集合，返回原始的单一解析结果
    if not results:
        logger.warning("无法提取多个七步要素，尝试提取单一结果")
        result = {}
        for element in elements:
            pattern = rf"{element}:\s*([^;]+)"
            match = re.search(pattern, response_text)
            if match:
                result[element] = match.group(1).strip()
            else:
                result[element] = "未提取"
        return [result]
    
    return results