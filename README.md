# 政策分析项目

本项目旨在使用多种大型语言模型(LLM)分析政策文档，高效地提取和处理政策信息。项目支持并行调用多个模型，并将结果以JSON格式保存。

## 项目结构

```
policy-analysis-project/
├── data/                  # 数据目录
│   ├── input/             # 输入文件目录
│   └── output/            # 输出结果目录
├── logs/                  # 日志文件目录
├── scripts/               # 脚本文件
│   ├── run_analysis.py    # 主分析脚本
│   ├── check_available_models.py  # 检查可用模型
│   ├── list_available_models.py   # 检查可用模型
│   ├── manage_models.py   # 模型管理器
│   ├── handle_model_errors.py     # 错误处理器
│   ├── test_multiple_models.py    # 测试多个模型
│   └── ...
├── src/                   # 源代码
│   ├── config/            # 配置文件
│   ├── core/              # 核心功能
│   ├── services/          # 服务组件
│   └── utils/             # 工具函数
├── tests/                 # 测试脚本
├── setup.py               # 快速初始化
└── .env                   # 环境变量配置文件
```

## 安装说明

1. 克隆仓库
```bash
git clone https://your-repository-url/policy-analysis-project.git
cd policy-analysis-project
```

2. 创建并激活虚拟环境
```bash
conda create -n policy_analysis python=3.11
conda activate policy_analysis
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
   - 在`.env`文件中填入您的API密钥信息

## 使用方法

### 1. 准备输入数据

将需要分析的政策文档放入`data/input/`目录，支持的格式包括：
- TXT文本文件
- JSON文件
- Markdown文件

### 2. 检查可用模型

```bash
python scripts/check_available_models.py
```
或
```bash
python scripts/list_available_models.py
```

此命令会列出当前环境中可用的所有模型。

### 3. 测试特定模型

```bash
# 列出所有可用模型
python scripts/test_multiple_models.py --list

# 测试指定模型
python scripts/test_multiple_models.py --models qwen-turbo,ernie-bot

# 使用自定义提示词测试
python scripts/test_multiple_models.py --prompt "分析广州市住房政策变化趋势"

# 组合使用多个参数
python scripts/test_multiple_models.py --models qwen-max --prompt "分析广州市住房政策变化趋势"
```

### 4. 模型管理工具

项目提供了一个交互式的模型管理工具，可以帮助您方便地添加、移除、测试模型：

```bash
python scripts/manage_models.py
```

该工具提供以下功能：

- **显示当前配置的模型**: 查看所有已配置的模型及其分类
- **添加新模型**: 通过交互式界面添加新模型到配置中
- **移除现有模型**: 从配置中删除不需要的模型
- **测试模型连接**: 测试特定模型是否能正常调用
- **测试API连接**: 测试阿里云、OpenAI和百度API的连接状态
- **自动代码更新功能**：当您添加新的阿里云模型时，工具会自动修改src/services/llm_service.py文件以支持该模型，无需手动编写代码。如果您添加非阿里云类别的模型（如百度、OpenAI等），可能需要手动扩展相应的代码。

<!-- 示例操作: -->
<!-- ![模型管理工具演示](docs/images/model_management_tool.png) -->

### 5. 提示词模板选择

项目支持多种预设的提示词模板，可通过`--template`参数指定：

- **standard**（默认）：标准政策分析模板，提供全面的八点分析
  - 政策基本信息
  - 政策背景与目的
  - 政策核心内容
  - 政策受益群体
  - 政策实施主体
  - 政策创新点
  - 政策影响评估
  - 政策关联分析

- **elements**：七步要素提取模板，精确提取政策的关键要素
  - 政策对象（住房类型）
  - 政策阶段（需求端/供给端/环境端）
  - 政策工具（税收优惠、财政补贴等）
  - 实施主体
  - 受益群体
  - 约束条件
  - 政策目标

- **public**：简明解读模板，面向普通民众的通俗解释
  - 用简单语言概括政策内容
  - 明确受益群体
  - 说明申请或参与步骤
  - 提示重要注意事项
  - 与以往政策的对比

- **housing**：住房政策分析提示词，包含七步要素
   - policy_object
   - policy_stage
   - policy_type
   - policy_tool
   - policy_geo_scope
   - policy_target_scope
   - tool_parameter
   
   *详细解释见提示词*

### 6. 运行分析

```bash
# 使用默认配置运行分析
python scripts/run_analysis.py

# 指定使用的模型
python scripts/run_analysis.py --models qwen-turbo,qwen-max

# 指定提示词模板
python scripts/run_analysis.py --template public

# 指定输入文件（此处的根目录必须是项目根目录） 
python scripts/run_analysis.py --input data/input/specific_file.txt

# 综合使用多个参数
python scripts.run_analysis.py --models qwen-max,qwen2-72b-instruct --template elements
```

### 7. 查看结果

分析结果将保存在`data/output/`目录中，每个模型的结果会保存在单独的JSON文件中，同时各个模型的结果也会汇总到all文件夹中便于模型比较。
日志文件保存在`logs/`目录，可用于查看处理过程和诊断问题。

## 配置提示词模板

您可以通过修改`src/config/prompt_templates.py`文件来自定义提示词模板：

1. 修改现有模板内容
2. 添加新的模板类型
3. 更改默认使用的模板

示例：
```python
# 添加新的模板
TAX_ANALYSIS_TEMPLATE = """请分析以下政策中的税收相关内容：
1. 税种类型
2. 税率变化
3. 计税方式
4. 纳税主体
5. 征管要求

政策文本：
{policy_text}
"""

# 更新模板字典
TEMPLATES["tax"] = TAX_ANALYSIS_TEMPLATE
```

## 支持的模型

项目支持多种语言模型，包括：

1. **阿里云通义千问系列**（需要百炼API密钥）
   - qwen-turbo
   - qwen-plus
   - qwen-max
   - qwen-72b-chat
   - qwen2-7b-instruct
   - qwen2-72b-instruct
   - 和其他通过模型管理工具添加的模型

2. **百度文心一言**（需要百度API密钥）
   - ernie-bot-4
   - ernie-bot
   - ernie-bot-turbo

3. **智谱AI**（需要智谱API密钥）
   - chatglm-turbo
   - chatglm-pro
   - chatglm-std

4. **OpenAI模型**（需要OpenAI API密钥）
   - gpt-3.5-turbo
   - gpt-4

5. **本地部署模型**
   - chatglm-local（需要本地部署ChatGLM服务）

> **注意：** 百川和Llama模型目前在阿里云API中不可用或已更换名称。如果您需要使用这些模型，请参考阿里云最新文档，或使用模型管理工具添加新的可用模型。

## 自定义配置

您可以使用以下两种方式自定义模型配置：

1. **使用模型管理工具(推荐)**
   ```bash
   python scripts/manage_models.py
   ```
   这个交互式工具可以帮助您轻松地添加、移除和测试模型，无需手动编辑配置文件。

2. **手动编辑配置文件**
   您也可以通过修改`src/config/model_config.py`文件来自定义模型配置：
   - 修改`DEFAULT_MODELS`列表以更改默认使用的模型
   - 调整`MODEL_ENDPOINTS`字典以更改模型API端点

## 高级用法

项目的核心功能是使用不同的模型和提示词模板来分析政策文档。您可以通过以下方式扩展功能：

1. 在`src/config/prompt_templates.py`中添加新的提示词模板
2. 使用模型管理工具(`scripts/manage_models.py`)添加和配置新的模型
3. 使用`scripts/run_analysis.py`的命令行参数组合不同的分析选项

注意：项目的主要功能已在上述使用方法部分详细说明。如需进一步定制或扩展功能，请参考源代码和注释。

## 常见问题

1. **模型访问错误**
   - 检查API密钥是否正确设置
   - 确认网络连接正常
   - 使用`scripts/manage_models.py`工具中的"测试API连接"功能检查API状态
   - 查看日志文件了解详细错误信息

2. **处理速度慢**
   - 考虑减少并行处理的模型数量
   - 使用响应更快的模型（如qwen-turbo）

3. **结果质量不佳**
   - 尝试使用更强大的模型（如qwen-max或gpt-4）
   - 优化输入的提示词

4. **无法找到或使用某些模型**
   - 使用`scripts/list_available_models.py`检查当前账户可用的模型
   - 使用模型管理工具添加新的可用模型
   - 确保您的API密钥有权限访问这些模型

<!-- ## 授权协议 -->

<!-- 本项目采用MIT许可证。详情请参阅LICENSE文件。 -->