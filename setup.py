from setuptools import setup, find_packages

setup(
    name="policy-analysis-project",
    version="0.1.0",
    description="政策文本分析工具",
    author="Policy Team",
    packages=find_packages(),
    install_requires=[
        "Flask>=2.0.1",
        "requests>=2.28.1",
        "pandas>=1.5.0",  # 更新到兼容Python 3.11的版本
        "numpy>=1.23.0",  # 更新到兼容Python 3.11的版本
        "openai>=1.0.0",
        "pytest>=6.2.4",
        "loguru>=0.5.3",
        "python-dotenv>=0.21.0",
        "tqdm>=4.64.1",
        "dashscope>=1.10.0",
        # 移除不存在的包 alibabacloud-dashscope>=0.0.2
        "retry>=0.9.2",
        "colorama>=0.4.4",
        # 添加本地模型服务所需依赖
        "fastapi>=0.95.0",
        "uvicorn>=0.21.0",
        "torch>=2.0.0",
        "transformers>=4.28.0",
        "pydantic>=1.10.7",
        # 可选依赖，用于加速推理
        "accelerate>=0.18.0",
        "bitsandbytes>=0.38.0",
        "sentencepiece>=0.1.99",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)