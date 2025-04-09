import json
import re
import pandas as pd
import os
import time
import logging
from openai import OpenAI

###############################################################################
# 日志配置：同时输出到控制台和文件 (analysis.log)
###############################################################################
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("analysis.log", encoding="utf-8")
    ]
)

###############################################################################
# 1. 定义四大类住房 & 其子类，以及子类->大类映射
###############################################################################
housing_categories = {
    "保障性住房": [
        "公共租赁住房（公租房）",
        "廉租房",
        "保障性租赁住房",
        "共有产权房",
        "经济适用房",
        "企业自建福利房（企业人才住房）",
        "人才房",
        "配租房",
        "配售房"
    ],
    "市场化住房": [
        "商品房（新房、二手房）",
        "限价商品房（两限房：限房价限面积）",
        "安居型商品房",
        "限竞房",
        "小产权房",
        "商改住/工改住公寓"
    ],
    "历史与改革类住房": [
        "公有住房（房改房）",
        "棚改/旧改安置房（老旧小区改造）",
        "回迁房"
    ],
    "租赁住房": [
        "长租公寓",
        "集体土地租赁住房"
    ]
}

def build_all_housing_types(housing_dict):
    """
    将 {大类: [子类1, ...], ...} 转换为所有子类列表 + 子类->大类映射
    """
    all_subtypes = []
    subtype_to_category = {}
    for cat, subtypes in housing_dict.items():
        for st in subtypes:
            all_subtypes.append(st)
            subtype_to_category[st] = cat
    return all_subtypes, subtype_to_category

ALL_HOUSING_SUBTYPES, SUBTYPE_TO_CATEGORY = build_all_housing_types(housing_categories)

###############################################################################
# 2. 分句函数：以 。！？ 为分隔符并保留分隔符在句子末尾
###############################################################################
def chunk_text_into_sentences(text):
    pattern = r'([。！？])'
    parts = re.split(pattern, text)
    
    sentences = []
    temp_sentence = []
    
    for part in parts:
        if re.match(pattern, part):
            temp_sentence.append(part)
            sentence = "".join(temp_sentence).strip()
            if sentence:
                sentences.append(sentence)
            temp_sentence = []
        else:
            temp_sentence.append(part)
    
    if temp_sentence:
        sentence = "".join(temp_sentence).strip()
        if sentence:
            sentences.append(sentence)
    
    sentences = [s for s in sentences if s.strip()]
    return sentences

###############################################################################
# 3. 大模型调用封装
###############################################################################
import requests

def call_local_qwen(prompt, conversation_id="policy_analysis"):
    """
    调用本地部署的Qwen模型
    
    Args:
        prompt: 发送给模型的文本
        conversation_id: 会话ID，用于维护对话上下文
    
    Returns:
        模型的回复文本
    """
    LOCAL_QWEN_API_URL = "http://0.0.0.0:8001/chat"
    payload = {
        "conversation_id": conversation_id,
        "prompt": prompt
    }
    
    try:
        response = requests.post(LOCAL_QWEN_API_URL, json=payload)
        response_json = response.json()
        
        if response_json.get("response", "") == "":
            logging.warning(f"Qwen模型返回空响应: {response_json}")
            return None
            
        # 提取响应中的assistant部分
        result = response_json.get("response", "")
        if "assistant" in result:
            result = result[result.rfind('assistant') + len('assistant'):]
        
        return result.strip()
    except Exception as e:
        logging.error(f"调用本地Qwen模型失败: {str(e)}")
        return None

def call_llm(prompt, api_key, model="deepseek-r1", max_retries=3):
    """
    调用大语言模型，使用阿里云API
    
    Args:
        prompt: 发送给模型的文本
        api_key: API密钥
        model: 模型名称
        max_retries: 最大重试次数
        
    Returns:
        模型返回的文本内容
    """
    # 使用阿里云API调用
    client = OpenAI(
        api_key=api_key,  # 使用传入的api_key
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个善于分析政策文本的助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                top_p=0.3
            )
            logging.info(f"阿里云API调用成功: 第{attempt+1}次尝试，prompt长度={len(prompt)}")
            return response.choices[0].message.content
        except Exception as e:
            logging.warning(f"阿里云API调用错误: {str(e)} (第{attempt+1}次重试)")
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
            else:
                logging.error("达到最大重试次数，放弃调用阿里云API")
                return None

###############################################################################
# 4. 七步要素提取 Prompt
###############################################################################
def generate_prompt_for_extraction(sentence, housing_subtypes):
    """
    我们定义七步要素：
    1. policy_object
    2. policy_stage
    3. policy_type
    4. policy_tool
    5. policy_geo_scope
    6. policy_target_scope
    7. tool_parameter
    """
    housing_types_str = "、".join(housing_subtypes)
    prompt = f"""
请从以下句子中提取“七步要素”，每个要素用“冒号+空格”表示，最后用分号分隔，不要添加多余描述：
1. policy_object: 从以下列表中匹配，如无则"未匹配"
   {housing_types_str}
2. policy_stage: 在 ["需求端","供给端","环境端"] 中选，不确定则"未确定"
3. policy_type: 在 ["强制性","激励型","信息型","能力建设型"] 中选，不确定则"未确定"
4. policy_tool: 用不超过6个字描述，无则写"未定义"
5. policy_geo_scope: 针对哪些地理范围(区、街道、乡镇、小区、楼盘、项目等)，无则"未指定"
6. policy_target_scope: 针对哪些人群/身份(如户籍、产权人、企业、事业单位、亲属关系等)，无则"未指定"
7. tool_parameter: 若有数字或量化内容(金额、数量、期限等)，写在这里，否则"无"

句子：{sentence}

输出示例：
policy_object: 公共租赁住房（公租房）; policy_stage: 需求端; policy_type: 激励型; policy_tool: 一次性补贴; policy_geo_scope: 花都、番禺; policy_target_scope: 本市户籍、企业; tool_parameter: 最高不超过100万
"""
    return prompt

###############################################################################
# 5. 解析大模型七要素的文本输出
###############################################################################
def parse_extraction_result(raw_text):
    """
    期望输出形如：
    policy_object: XXX; policy_stage: XXX; policy_type: XXX; policy_tool: XXX;
    policy_geo_scope: XXX; policy_target_scope: XXX; tool_parameter: XXX
    """
    result = {
        "policy_object": "未匹配",
        "policy_stage": "未确定",
        "policy_type": "未确定",
        "policy_tool": "未定义",
        "policy_geo_scope": "未指定",
        "policy_target_scope": "未指定",
        "tool_parameter": "无"
    }
    
    pairs = raw_text.split(";")
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        if ":" in pair:
            key, val = pair.split(":", 1)
            key = key.strip()
            val = val.strip()
            if key in result:
                result[key] = val
    return result

###############################################################################
# 6. 写入Excel：每行一条句子结果
###############################################################################
def append_record_to_excel(record, excel_filename):
    df_part = pd.DataFrame([record])
    if os.path.exists(excel_filename):
        existing_df = pd.read_excel(excel_filename)
        combined_df = pd.concat([existing_df, df_part], ignore_index=True)
        combined_df.to_excel(excel_filename, index=False)
    else:
        df_part.to_excel(excel_filename, index=False)

###############################################################################
# 7. 核心分析函数：对单个文件进行处理，“每一句都输出一行”
###############################################################################
def analyze_policy_doc(policy_data, doc_id, meta_data, api_key, excel_filename):
    # 1) 获取正文
    content_field = policy_data.get("正文", [])
    if isinstance(content_field, list):
        full_text = "\n".join(content_field)
    elif isinstance(content_field, str):
        full_text = content_field
    else:
        full_text = ""
    
    # 2) 分句
    sentences = chunk_text_into_sentences(full_text)
    
    for sent_id, sentence in enumerate(sentences):
        # 针对每一句，直接进行七步要素提取
        extraction_prompt = generate_prompt_for_extraction(sentence, ALL_HOUSING_SUBTYPES)
        extraction_resp = call_llm(extraction_prompt, api_key=api_key)
        
        # 初始化行记录
        record = {
            "doc_id": doc_id,
            "sent_id": sent_id,
            "sentence_text": sentence,
            "policy_object": "未匹配",
            "housing_category": "未匹配",
            "policy_stage": "未确定",
            "policy_type": "未确定",
            "policy_tool": "未定义",
            "policy_geo_scope": "未指定",
            "policy_target_scope": "未指定",
            "tool_parameter": "无"
        }
        
        # 在行记录里附加元数据
        for k, v in meta_data.items():
            record[k] = v
        
        if extraction_resp is None:
            # 如果模型调用失败
            record["policy_object"] = "解析失败"
        else:
            # 成功返回 -> 解析
            parsed = parse_extraction_result(extraction_resp)
            record["policy_object"]        = parsed["policy_object"]
            record["policy_stage"]         = parsed["policy_stage"]
            record["policy_type"]          = parsed["policy_type"]
            record["policy_tool"]          = parsed["policy_tool"]
            record["policy_geo_scope"]     = parsed["policy_geo_scope"]
            record["policy_target_scope"]  = parsed["policy_target_scope"]
            record["tool_parameter"]       = parsed["tool_parameter"]
            
            # 大类映射
            if record["policy_object"] in SUBTYPE_TO_CATEGORY:
                record["housing_category"] = SUBTYPE_TO_CATEGORY[record["policy_object"]]
        
        # 最后写入Excel
        append_record_to_excel(record, excel_filename)

###############################################################################
# 8. 批量处理
###############################################################################
def process_json_files_in_directory(directory_path, api_key, excel_filename):
    doc_counter = 0
    
    logging.info(f"开始处理目录: {directory_path}")
    file_list = [fn for fn in os.listdir(directory_path) if fn.lower().endswith(".json")]
    logging.info(f"共发现 {len(file_list)} 个JSON文件。")

    for filename in file_list:
        file_path = os.path.join(directory_path, filename)
        logging.info(f"处理文件: {filename}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            policy_data = json.load(f)
        
        # 读取元数据(如果有)
        meta_data = policy_data.get("元数据", {})
        
        # 逐一分析并写入Excel
        analyze_policy_doc(
            policy_data=policy_data,
            doc_id=doc_counter,
            meta_data=meta_data,
            api_key=api_key,
            excel_filename=excel_filename
        )
        
        doc_counter += 1

    logging.info(f"全部处理完成，共计处理 {doc_counter} 个文件。")
    logging.info(f"结果写入：{excel_filename}")

###############################################################################
# 主函数入口
###############################################################################
if __name__ == "__main__":
    # 在此处填入您的OpenAI API Key
    MY_OPENAI_API_KEY = "sk-5ccc48320e3341b6b273861358dffdec"
    
    # JSON文件所在的目录
    directory_path = "/home/greylee/Projects/Policy_2024_12/guangzhou_1"
    
    # 输出目录（绝对路径）
    OUTPUT_DIR = "/home/greylee/Projects/Policy_2024_12"
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    excel_path = os.path.join(OUTPUT_DIR, "policy_results.xlsx")
    
    # 若您想在每次运行前清空旧结果，可取消注释：
    # if os.path.exists(excel_path):
    #     os.remove(excel_path)
    
    process_json_files_in_directory(
        directory_path=directory_path,
        api_key=MY_OPENAI_API_KEY,
        excel_filename=excel_path
    )
    
    print("处理完成！请查看Excel输出及日志analysis.log。")
