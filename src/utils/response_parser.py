import re
import json
import logging

logger = logging.getLogger(__name__)

def parse_housing_elements(response_text):
    """
    将housing模板的文本响应解析为JSON格式
    """
    
    # 使用正则表达式解析分号分隔的字段
    result = {}
    elements = ["policy_object", "policy_stage", "policy_type", "policy_tool", 
                "policy_geo_scope", "policy_target_scope", "tool_parameter"]
    
    for element in elements:
        pattern = rf"{element}:\s*([^;]+)"
        match = re.search(pattern, response_text)
        if match:
            result[element] = match.group(1).strip()
        else:
            result[element] = "未提取"
    
    return result