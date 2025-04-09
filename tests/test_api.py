# 保存为test_api.py并运行
import os
import requests

api_key = os.getenv("API_KEY")
headers = {
    "Authorization": f"Bearer {api_key}", 
    "Content-Type": "application/json"
}

url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

data = {
    "model": "qwen-turbo",
    "input": {
        "messages": [
            {"role": "user", "content": "你好"}
        ]
    }
}

response = requests.post(url, headers=headers, json=data)
print(f"状态码: {response.status_code}")
print(f"响应内容: {response.text}")