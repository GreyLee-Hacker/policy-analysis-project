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
│   ├── start_local_model.py       # 启动本地模型
│   ├── interact_with_local_model.py # 与本地模型交互
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
# 使用默认配置运行分析 (默认线程数为 3)
python scripts/run_analysis.py

# 指定使用的模型
python scripts/run_analysis.py --models qwen-turbo,qwen-max

# 指定提示词模板
python scripts/run_analysis.py --template public

# 指定输入文件或目录 (路径相对于项目根目录或使用绝对路径)
python scripts/run_analysis.py --input data/input/specific_file.txt
python scripts/run_analysis.py --input data/input/policy/2024/

# 指定工作线程数
python scripts/run_analysis.py --threads 4

# 启用通用断点续跑 (从上次中断的位置继续所有文件)
python scripts/run_analysis.py --resume

# 从指定文件和文档ID开始续跑 (仅指定文件从特定位置开始，其他文件从头开始)
# 例如：从 地方法规2_cleaned1_extract.json 文件的 doc_id 1016 开始
python scripts/run_analysis.py --resume-file 地方法规2_cleaned1_extract.json --resume-doc-id 1016

# 综合使用多个参数
python scripts/run_analysis.py --models qwen-max,qwen2-72b-instruct --template elements --threads 2
```

**注意:**
- `--resume-file` 和 `--resume-doc-id` 必须同时提供。
- 当使用 `--resume-file` 和 `--resume-doc-id` 时，只有指定的文件会从 `doc_id` 对应的句子开始处理，其他所有文件都会从头开始处理，并且它们之前的增量结果会被清除。
- 通用断点续跑 (`--resume` 或 `--start-from`) 与特定文件续跑 (`--resume-file`/`--resume-doc-id`) 互斥，后者优先级更高。

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

## 启动并使用本地大模型

本项目现在提供了更完善的本地大语言模型支持，包括模型启动和交互脚本，让您可以轻松部署和使用自己的大模型进行政策分析。

### 1. 启动本地模型服务

我们提供了一个功能强大的启动脚本，支持多种开源大语言模型：

```bash
# 使用默认设置启动(Qwen2-7B-Instruct)
python scripts/start_local_model.py

# 指定模型路径(本地模型或Hugging Face模型)
python scripts/start_local_model.py --model_path /path/to/your/model

# 使用特定端口
python scripts/start_local_model.py --port 8001

# 在CPU上运行模型(适用于没有GPU的设备)
python scripts/start_local_model.py --device cpu

# 使用半精度加载模型(节省GPU内存)
python scripts/start_local_model.py --use_half

# 指定每个GPU的最大内存使用
python scripts/start_local_model.py --max_memory "0:10GiB,1:10GiB"
```

服务启动后，将在指定地址(默认为`http://0.0.0.0:8001`)监听请求，提供两种API接口：
- 标准接口：`/chat` - 接受conversation_id和prompt参数
- 兼容接口：`/api/chat` - 兼容ChatGLM格式的接口，接受prompt和history参数

### 2. 与本地模型交互

启动模型服务后，您可以通过我们的交互式客户端与大模型进行对话：

```bash
# 启动交互式聊天界面
python scripts/interact_with_local_model.py

# 指定模型服务URL
python scripts/interact_with_local_model.py --url http://localhost:8001/chat

# 使用ChatGLM兼容接口
python scripts/interact_with_local_model.py --chatglm

# 分析特定政策文件
python scripts/interact_with_local_model.py --file data/input/specific_file.txt

# 直接分析政策文本
python scripts/interact_with_local_model.py --policy "这是一段政策文本..."
```

交互式界面支持以下命令：
- `quit`/`exit`/`q` - 退出聊天
- `clear` - 清除聊天历史
- `save` - 保存聊天历史到文件

### 3. 在政策分析项目中使用本地模型

本地模型服务启动后，您可以像使用云端模型一样将其集成到政策分析工作流中：

```bash
# 使用本地模型进行政策分析
python scripts/run_analysis.py --models chatglm-local --input data/input/your_policy.txt
```

### 4. 配置本地模型

您还可以使用模型管理工具配置本地模型：

```bash
# 启动模型管理工具
python scripts/manage_models.py

# 在菜单中选择选项7: 配置本地模型
```

这将引导您设置本地模型的URL、将其添加到可用模型列表，并选择性地将其设为默认模型。

### 5. 系统要求

- **Python 3.8+**
- **PyTorch 1.10+**
- **Transformers 4.28+**
- **20GB+ 内存**（取决于所使用的模型大小）
- **NVIDIA GPU**（建议用于大型模型，8GB+显存）
  - 也支持在CPU上运行，但会很慢
  - 支持Apple M系列芯片上的MPS加速

### 6. 故障排除

- **内存/显存不足**: 尝试使用`--use_half`参数降低精度，或选择更小的模型
- **模型加载错误**: 确保模型路径正确，并已完整下载所有模型文件
- **API连接失败**: 检查URL和端口配置是否正确，确保模型服务正在运行
- **响应速度慢**: 这是正常现象，本地模型在首次调用时需要加载和编译，后续响应会更快

## 配置本地大模型

项目支持使用本地部署的大语言模型，以下是详细配置步骤：

### 1. 本地模型准备

首先，您需要在本地部署一个大语言模型服务。推荐以下方案：

- **ChatGLM系列模型**：可通过[ChatGLM官方仓库](https://github.com/THUDM/ChatGLM3)获取安装指南
- **自行部署的API服务**：任何符合标准API格式的本地模型服务都可以集成

### 2. 使用模型管理工具进行配置

项目提供了专门的交互式配置向导，简化本地模型的接入流程：

```bash
# 启动模型管理工具
python scripts/manage_models.py

# 在菜单中选择选项7：配置本地模型
```

配置向导会引导您完成以下操作：
- 设置本地模型服务的URL地址（默认为`http://0.0.0.0:8002/chat`）
- 将URL保存到环境变量和配置文件中
- 添加本地模型到可用模型列表
- 设置本地模型为默认使用模型（可选）
- 测试模型连接状态

![本地模型配置向导示意图](docs/images/local_model_setup.png)

### 3. 本地模型API格式要求

项目默认支持ChatGLM系列模型的API格式：

- **请求格式**：
  ```json
  {
    "prompt": "你好",
    "history": []
  }
  ```

- **响应格式**：
  ```json
  {
    "response": "模型的回复内容"
  }
  ```

如果您的本地模型使用不同的API格式，有两种解决方案：

1. **修改您的模型服务器**：使其提供与上述格式兼容的API
2. **调整项目代码**：在`src/services/llm_service.py`文件中修改对应的处理逻辑

### 4. 常见问题解决

- **连接失败**：确保本地模型服务已启动并监听在配置的URL上
- **响应格式错误**：检查模型API的返回格式是否符合要求
- **响应超时**：适当增加超时时间，因为本地大模型处理可能较慢
- **无法识别模型**：确认模型名称已正确添加到配置中

### 5. 启动和使用本地模型的脚本示例

以下是启动ChatGLM服务的参考命令（具体命令可能因您的环境而有所不同）：

```bash
# 使用conda环境
conda activate chatglm

# 启动ChatGLM API服务
python -m app.py --server 0.0.0.0 --port 8002
```

在服务启动后，您可以使用以下命令来测试与分析：

```bash
# 测试本地模型
python scripts/test_multiple_models.py --models chatglm-local

# 使用本地模型进行政策分析
python scripts/run_analysis.py --models chatglm-local --input data/input/your_policy.txt
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