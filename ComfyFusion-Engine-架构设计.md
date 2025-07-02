# ComfyFusion Engine - 架构设计文档

## 1. 核心需求

### 1.1 用户现状与痛点

**用户现状**：
- 用户已经拥有 ComfyUI 并创建了一些调试好的工作流
- 这些工作流在 ComfyUI 界面中运行良好，能生成满意的内容
- 用户希望将这些 AI 生成能力集成到自己的应用程序中

**用户痛点**：
- ComfyUI API 过于底层，需要传递完整的复杂节点配置 JSON
- 每次调用都要重复传递大量技术参数和节点关系
- 用户只想修改核心参数（如 prompt、尺寸、风格），但需要修改整个工作流定义
- 缺乏标准化的集成接口，难以在现代应用架构中优雅地调用

**用户诉求**：
- 需要一个"智能代理"服务，隐藏 ComfyUI 的技术复杂性
- 用户只需指定工作流名称和关键参数，代理自动处理技术细节
- 通过标准化协议（MCP）提供与其他 AI 服务一致的调用体验
- 支持工作流的版本管理和预设复用

### 1.2 核心需求
构建一个基于 **FastMCP** 的 **ComfyUI 智能代理服务**，实现以下核心功能：

1. **工作流托管**：用户将调试好的 ComfyUI workflow 和对应模板托管到服务中
2. **自动发现**：服务自动识别新增的工作流，无需重启即可使用
3. **参数简化**：用户只需提供工作流名称和核心参数（prompt、size等）
4. **智能映射**：服务自动将用户参数映射到复杂的工作流节点配置
5. **并发执行**：支持多用户同时调用，智能队列管理执行顺序
6. **结果交付**：直接返回 ComfyUI 原生文件访问 URL，无需重复存储

### 1.3 用户使用流程
```
1. 用户准备文件
   ├── 将基础工作流保存为 {workflow_name}.json
   └── 将对应模板保存为 {workflow_name}_tp.json
   └── 两个文件都放到 workflows/ 目录

2. 系统自动发现
   ├── MCP Server 监控 workflows/ 目录变化
   ├── 自动识别 .json 和 _tp.json 文件对
   └── 动态注册新的工作流能力到 MCP 系统

3. 用户智能调用（三工具协作）
   ├── 步骤1：调用 list_workflows 查看可用工作流
   ├── 步骤2：调用 analyze_and_execute 完成智能生成
   │   ├── 阶段2.1：LLM分析用户需求，生成workflow补丁
   │   └── 阶段2.2：自动调用执行引擎，融合workflow并执行
   └── 获得最终结果：ComfyUI 原生文件访问 URL（格式：http://127.0.0.1:8188/view?filename=xxx）

4. 实际用户体验
   ├── 用户："我要生成一只可爱的猫咪，动漫风格"
   ├── 系统：自动选择合适workflow，构造参数，执行生成
   └── 返回：生成的图片URL，用户可直接访问
```

## 2. 核心设计思路："三位一体"的分层融合

### 2.1 架构概述
```
用户输入层 (Dynamic Patch)   [最高优先级 - 用户实时参数]
    ⬇️ 覆盖合并
静态配置层 (Template)        [中间优先级 - 预设风格补丁] 
    ⬇️ 覆盖合并
基础工作流层 (Workflow)       [基础蓝图 - 完整默认配置]
```

### 2.2 分层融合原理
通过"融合函数"将三层数据像图层一样从底层到顶层依次合并，最终生成一个独一无二、可直接执行的最终工作流。

## 3. 基于 FastMCP 的技术架构

### 3.1 流式协议架构设计

**MCP Server 流式协议支持**：
- **实时通信**：采用 FastMCP 2.0+ 的流式协议，支持服务端与客户端的实时双向通信
- **流式响应**：所有工具函数支持 `AsyncGenerator` 流式返回，提供实时执行反馈
- **进度跟踪**：通过流式协议实时推送任务执行状态、进度百分比和中间结果
- **错误流式处理**：异常和错误信息通过流式协议实时反馈，便于调试和监控
- **大数据流传输**：支持大型工作流文件和结果数据的流式传输，避免内存溢出

### 3.2 核心工具设计：智能化三工具架构

**设计哲学**：让每个组件都做自己最擅长的事情
- **MCP Server**：专注数据管理和执行引擎，通过流式协议提供实时反馈
- **Client LLM**：发挥语义理解和参数构造优势
- **工具协作**：通过工具链实现智能化自动执行，全程支持流式进度反馈

#### 3.2.1 工具1：`list_workflows` - 工作流枚举器

**职责**：提供可用工作流的清单和基本信息

**输入**：无参数
**输出**：
```json
{
  "workflows": [
    {
      "name": "text2image_v1",
      "description": "文本到图像生成，支持多种风格",
      "category": "image_generation",
      "parameters": ["prompt", "style", "size", "quality"]
    },
    {
      "name": "img2img_v1", 
      "description": "图像到图像转换，支持风格迁移",
      "category": "image_transformation",
      "parameters": ["image_input", "prompt", "strength", "style"]
    }
  ]
}
```

**设计要点**：
- 自动扫描 `workflows/` 目录
- 提取模板文件中的描述信息
- 为用户和LLM提供工作流选择依据

#### 3.2.2 工具2：`analyze_and_execute` - 智能分析器

**职责**：智能分析用户需求，生成工作流补丁，并引导LLM调用执行工具

**核心设计原理**：
- 工具2只负责分析，不执行
- 通过返回引导信息让Client LLM自动调用工具3
- 实现真正的工具链协作

**执行流程**：
```python
async def analyze_and_execute(
    user_request: str,
    workflow_name: str,
    ctx: Context
) -> Dict[str, Any]:
    """
    智能分析用户需求并引导LLM调用执行工具
    
    流程：
    1. 加载指定workflow的模板信息
    2. 构造LLM提示词进行智能分析
    3. 生成完整的workflow补丁
    4. 返回分析结果和工具3的调用引导信息
    5. Client LLM自动理解并调用execute_workflow工具
    """
    
    # 分析用户需求，生成补丁
    workflow_patch = await analyze_user_request(user_request, template_info)
    
    # 返回引导信息，让LLM调用工具3
    return {
        "status": "analysis_complete",
        "workflow_name": workflow_name,
        "user_request": user_request,
        "generated_patch": workflow_patch,
        "next_action": "Please call execute_workflow tool to complete the generation",
        "recommended_call": {
            "tool": "execute_workflow",
            "arguments": {
                "workflow_name": workflow_name,
                "workflow_patch": workflow_patch
            }
        }
    }
```

**LLM引导的工具链协作流程**：
```
用户调用：analyze_and_execute("生成一只可爱的橘猫，动漫风格", "fluximage")
    ↓
工具2执行分析：
1. 加载fluximage模板信息
2. 智能分析用户需求
3. 生成参数补丁：{
     "prompt": "一只可爱的橘猫，毛茸茸的，大眼睛", 
     "style": "anime",
     "quality": "high",
     "size": "1024x1024"
   }
    ↓
工具2返回引导信息：{
    "status": "analysis_complete",
    "generated_patch": {...},
    "next_action": "Please call execute_workflow tool to complete the generation",
    "recommended_call": {
        "tool": "execute_workflow",
        "arguments": {...}
    }
}
    ↓
Client LLM理解引导信息
    ↓
LLM自动调用：execute_workflow(workflow_name="fluximage", workflow_patch={...})
    ↓
工具3执行：三层融合 + ComfyUI调用
    ↓
返回最终结果：生成文件的ComfyUI原生URL
```

#### 3.2.3 工具3：`execute_workflow` - 纯执行引擎

**职责**：接收完整的workflow补丁，执行融合和ComfyUI调用

**输入**：
```json
{
  "workflow_name": "text2image_v1",
  "workflow_patch": {
    "prompt": "一只可爱的橘猫",
    "style": "anime",
    "quality": "high", 
    "size": "1024x1024"
  }
}
```

**处理流程**：
1. **加载基础工作流**：读取 `{workflow_name}.json`
2. **应用模板补丁**：合并 `{workflow_name}_tp.json`
3. **应用用户补丁**：合并用户提供的参数
4. **执行融合函数**：生成最终可执行的workflow
5. **调用ComfyUI API**：提交到ComfyUI执行
6. **返回结果**：提供ComfyUI原生文件URL

**三层融合示例**：
```python
# 基础工作流 (workflow.json)
base_workflow = {
  "3": {
    "inputs": {
      "seed": 12345,
      "steps": 20,
      "cfg": 8.0,
      "sampler_name": "euler",
      "scheduler": "normal",
      "denoise": 1.0,
      "model": ["4", 0],
      "positive": ["6", 0],
      "negative": ["7", 0],
      "latent_image": ["5", 0]
    }
  }
}

# 模板补丁 (workflow_tp.json)
template_patch = {
  "6": {
    "inputs": {
      "text": "{prompt}"
    }
  },
  "5": {
    "inputs": {
      "width": "{width}",
      "height": "{height}"
    }
  }
}

# 用户补丁 (来自LLM分析)
user_patch = {
  "prompt": "一只可爱的橘猫",
  "width": 1024,
  "height": 1024
}

# 融合结果
final_workflow = fusion_engine.merge(base_workflow, template_patch, user_patch)
```

### 3.3 工具协作模式：LLM引导的智能工具链

**传统模式**：用户 → 工具 → 结果
**LLM引导的工具链模式**：用户 → 工具2(分析+引导) → LLM理解 → 工具3(执行) → 流式结果反馈

**核心创新设计**：
1. **工具引导LLM**：工具2不直接调用工具3，而是通过返回引导信息让LLM自动调用
2. **智能参数构造**：复杂的语义理解和参数映射由工具2的LLM分析完成
3. **自主工具链**：LLM看到引导信息后自主决定调用工具3，实现真正的智能协作
4. **职责完全分离**：
   - 工具2：只分析，不执行
   - LLM：理解引导信息，自主决策工具调用
   - 工具3：只执行，不分析
5. **流式反馈**：每个工具都支持流式协议，提供实时进度更新

**工具链协作的核心优势**：
- **符合MCP协议设计**：避免工具间直接内部调用的架构问题
- **LLM自主决策**：让LLM根据工具2的引导信息自主选择下一步行动
- **灵活性更强**：LLM可以根据情况选择是否调用工具3，或调用其他工具
- **错误处理更好**：每个工具独立，错误不会级联传播

### 3.4 核心架构设计原则

**基于 FastMCP 2.0+ 的企业级架构**：
- **异步优先**：所有核心功能采用 `async def` 实现，支持高并发
- **流式协议**：MCP Server 采用流式协议进行实时通信，提供流式响应能力
- **流式响应**：使用 `AsyncGenerator[dict, None]` 提供实时执行反馈
- **资源模板**：利用 FastMCP 的资源模板系统实现动态工作流发现
- **服务器组合**：采用模块化设计，支持功能服务器的动态挂载
- **Context 注入**：工具函数接收 Context 参数访问服务器能力
- **LLM协作**：工具主动利用Client LLM能力进行智能推理

### 3.5 核心组件设计

#### 3.5.1 工作流发现引擎

**基于 FastMCP 架构的文件系统监控和动态注册系统**：

```python
class WorkflowDiscoveryEngine:
    """
    企业级工作流发现引擎
    
    基于 FastMCP 架构的文件系统监控和动态注册系统：
    - 异步文件处理
    - 实时能力更新
    - 错误恢复和重试
    - 生命周期管理
    """
    
    def __init__(self, mcp_server: FastMCP, workflows_dir: str = "workflows"):
        self.mcp = mcp_server
        self.workflows_dir = Path(workflows_dir)
        self.observer = Observer()
        self.registered_workflows: Dict[str, Dict] = {}
        self.registered_templates: Dict[str, Dict] = {}
        self.file_handler = WorkflowFileHandler(self)
        self._running = False
```

#### 3.5.2 工作流融合引擎

**支持三层融合的核心引擎**：

```python
class WorkflowFusionEngine:
    """
    企业级工作流融合引擎
    
    基于 FastMCP 架构设计，支持：
    - 异步并发处理
    - 实时进度反馈
    - 错误恢复机制
    - 调试和监控
    """
    
    async def fusion_workflow_stream(
        self,
        config: FusionConfig,
        ctx: Context
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步流式融合执行器
        
        基于 FastMCP 最佳实践的企业级实现：
        - 使用 Context 进行日志记录和错误处理
        - 支持实时进度报告
        - 异步资源访问和处理
        """
```

#### 3.5.3 任务管理系统

**基于 FastMCP Context 和生命周期的任务队列设计**：

```python
class TaskManager:
    """
    企业级任务管理器
    
    基于 FastMCP 架构的异步任务队列系统：
    - 优先级队列支持
    - 并发控制和负载均衡
    - 错误重试和恢复机制
    - 实时进度跟踪
    - 生命周期管理
    """
    
    async def submit_task(
        self,
        task_context: TaskExecutionContext,
        ctx: Context
    ) -> str:
        """
        提交任务到队列
        
        支持优先级和队列位置估算
        """
```

#### 3.5.4 ComfyUI API 客户端

**企业级 ComfyUI API 集成**：

```python
class EnterpriseComfyUIClient:
    """
    企业级 ComfyUI API 客户端
    
    基于 FastMCP 架构的高级 ComfyUI 集成：
    - 支持多媒体工作流（图片、视频、音频）
    - 异步流式执行和进度监控
    - 自动错误恢复和重试机制
    - WebSocket 连接池管理
    - 文件上传和下载优化
    - 全面的执行状态跟踪
    """
    
    async def execute_workflow_stream(
        self, 
        workflow: Dict, 
        ctx: Context,
        progress_callback: Optional[Callable] = None
    ) -> AsyncGenerator[ComfyUIExecutionProgress, None]:
        """
        执行工作流并返回流式进度更新
        
        支持全媒体类型工作流的执行和监控
        """
```

### 3.6 文件架构设计

#### 3.6.1 基础工作流文件 (Workflow)
**位置**: `workflows/{workflow_name}.json`

**特点**:
- 标准的 ComfyUI "Save (API Format)" 导出文件
- 包含完整的节点定义和默认参数
- 是不可变的基础蓝图

#### 3.6.2 模板文件 (Template)
**位置**: `workflows/{workflow_name}_tp.json`

**命名规范**: `{workflow_name}_tp.json` (tp = template)

**特点**:
- 纯粹的"补丁"文件，只包含需要修改的部分
- 包含模板描述信息
- 支持参数化替换（如 `{prompt}` 占位符）
- 与对应的基础工作流文件放在同一目录

### 3.7 中间件架构理念

**MCP 服务器作为纯中间件**：
- **ComfyUI 负责**：AI 计算和文件存储管理
- **MCP 服务器负责**：工作流融合、任务调度、参数简化
- **用户获得**：简化的接口 + ComfyUI 原生文件访问能力

**文件服务架构对比**：

| 传统架构 | 中间件架构 |
|---------|-----------|
| MCP下载文件到本地 | 直接返回ComfyUI URL |
| 需要额外存储空间 | 零额外存储需求 |
| 文件传输耗时 | 即时返回链接 |
| 需要清理逻辑 | ComfyUI原生管理 |
| 复杂文件服务器 | 简单URL生成 |

## 4. 项目结构

```
mcp-comfyui-anything/
├── src/
│   └── comfyfusion/
│       ├── __init__.py
│       ├── server.py              # FastMCP 服务器主文件
│       ├── fusion/
│       │   ├── __init__.py
│       │   ├── engine.py          # 融合引擎核心逻辑
│       │   └── mapping.py         # 参数映射配置
│       ├── api/
│       │   ├── __init__.py
│       │   └── comfyui_client.py  # ComfyUI API 客户端 (支持流式)
│       ├── task_manager.py        # 任务队列管理系统
│       ├── workflow_manager.py    # 工作流管理器
│       └── utils/
│           ├── __init__.py
│           ├── config.py          # 配置管理
│           ├── logger.py          # 日志系统
│           ├── types.py           # 类型定义
│           └── workflow_discovery.py  # 工作流自动发现
├── workflows/                     # 工作流和模板统一存储目录
│   ├── text2image_v1.json        # 基础工作流
│   ├── text2image_v1_tp.json     # 对应模板
│   ├── text2video_v1.json        # 基础工作流  
│   ├── text2video_v1_tp.json     # 对应模板
│   ├── img2img_v1.json           # 基础工作流
│   └── img2img_v1_tp.json        # 对应模板
├── config/
│   ├── settings.json             # 基础配置
│   └── parameter_mapping.json   # 参数映射规则
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 5. 核心特性

### 5.1 技术特性
- **智能化三工具架构**：通过工具协作和LLM增强实现智能化自动执行
- **流式协议支持**：MCP Server 采用流式协议，支持实时双向通信和数据流传输
- **动态加载**：无需重启服务即可添加新的工作流和模板
- **参数友好**：用户只需提供自然语言描述，无需关心技术参数
- **LLM协作**：工具主动利用Client LLM能力进行智能推理和参数构造
- **预设复用**：通过模板系统快速应用不同风格
- **完全解耦**：工作流、模板、执行逻辑完全分离
- **职责分离**：服务端专注数据和执行，LLM专注理解和推理
- **自动化执行链**：一次调用完成分析→构造→执行的完整流程
- **并发处理**：基于内存队列的多任务并发执行，提高资源利用率
- **流式体验**：实时反馈任务状态和执行进度，提升用户体验
- **架构简化**：直接使用 ComfyUI 原生文件服务，避免重复存储

### 5.2 扩展性
- **新工作流**：只需添加 JSON 文件到 workflows 目录
- **新模板**：只需添加补丁文件到对应模板目录
- **新参数**：通过配置文件扩展参数映射规则

### 5.3 容错性
- 参数验证和类型检查
- 工作流文件格式验证
- ComfyUI 连接状态检测
- 详细的错误日志和诊断信息

## 6. 部署配置

### 6.1 环境要求
```bash
# Python 环境
Python >= 3.9

# 核心依赖
fastmcp >= 2.0.0
httpx >= 0.24.0
pydantic >= 2.0.0
aiofiles >= 23.0.0
deepmerge >= 1.1.0
```

### 6.2 配置文件
```json
// config/settings.json
{
  "comfyui": {
    "host": "127.0.0.1",
    "port": 8188,
    "timeout": 300
  },
  "mcp": {
    "server_name": "comfyfusion-engine",
    "version": "1.0.0",
    "protocol": "streaming",
    "enable_streams": true
  },
  "paths": {
    "workflows": "./workflows",
    "templates": "./templates"
  }
}
```

### 6.3 启动方式
```bash
# 安装依赖
pip install -e .

# 启动 MCP 服务器
comfyfusion-mcp

# 或者直接运行
python -m comfyfusion.server
```

## 7. 最佳实践

### 7.1 工作流管理
- 使用语义化的命名约定：`{功能}_{版本}.json`
- 为每个工作流创建说明文档
- 定期备份和版本控制

### 7.2 模板设计
- 模板应该专注于单一场景或风格
- 提供清晰的描述信息
- 合理使用参数占位符提高灵活性

### 7.3 参数映射
- 使用用户友好的参数名称
- 提供合理的默认值
- 考虑参数间的依赖关系

## 8. 监控与管理

### 8.1 输入验证与资源管理

**数据验证**：
- **参数验证**：确保输入参数格式正确和类型匹配
- **文件验证**：工作流文件格式和JSON结构验证
- **数据完整性**：流式传输数据的完整性校验

**资源管理**：
- **资源限制**：CPU、内存和执行时间的合理限制
- **并发控制**：控制同时执行的工作流数量
- **存储管理**：临时文件和缓存的自动清理

### 8.2 监控与日志

**流式监控**：
- **实时状态**：通过流式协议实时监控所有工具执行状态
- **性能指标**：延迟、吞吐量、成功率等关键指标监控
- **资源使用**：CPU、内存、磁盘使用情况实时跟踪
- **错误追踪**：异常和错误的详细日志记录和告警

**审计日志**：
- **操作记录**：所有工具调用和工作流执行记录
- **用户追踪**：用户行为和操作历史记录
- **性能分析**：执行时间和资源消耗分析

### 8.3 错误处理与恢复

**流式错误处理**：
- **实时错误反馈**：通过流式协议即时推送错误信息
- **优雅降级**：部分功能故障时的服务降级策略
- **自动重试**：网络或临时故障的智能重试机制
- **状态恢复**：服务重启后的状态恢复能力

## 9. 未来扩展方向

- **批量处理**：支持批量图像生成和并行执行
- **结果管理**：生成结果的存储、检索和版本管理
- **用户管理**：基于用户的基础管理功能（非认证）
- **监控告警**：执行状态监控、性能告警和异常通知
- **模板市场**：社区共享的模板生态和插件系统
- **多模态支持**：扩展支持音频、视频等多媒体工作流
- **云原生部署**：支持容器化部署和Kubernetes编排
- **API网关集成**：与现有API网关和微服务架构集成

---

**这个架构通过 FastMCP 的流式协议能力和智能化三工具设计，将 ComfyUI 的复杂性隐藏在简洁的接口背后。通过工具协作和LLM增强，结合实时流式反馈，用户只需提供自然语言描述，系统就能自动完成参数构造和执行，为用户提供了一个真正智能、实时和实用的 AI 内容生成服务。**

## 10. 三工具架构优势总结

### 10.1 用户体验优势
- **极简交互**：用户只需要自然语言描述需求
- **一步到位**：一次调用完成从理解到执行的全流程
- **智能理解**：LLM自动处理复杂的参数映射和语义理解
- **实时反馈**：通过流式协议获得实时执行进度和状态更新

### 10.2 技术架构优势
- **职责清晰**：每个组件都专注于自己最擅长的领域
- **扩展性强**：新增workflow不需要修改复杂的参数映射逻辑
- **维护简单**：服务端逻辑简化，减少bug和维护成本
- **实时通信**：流式协议提供高效的双向通信能力

### 10.3 创新设计价值
- **工具调用LLM**：开创性的"工具主动利用LLM"设计模式
- **智能自动化**：将复杂的多步骤流程封装为智能化单步调用
- **流式架构**：首创MCP流式协议在AI内容生成领域的应用
- **最佳实践**：体现了现代AI应用架构的最佳设计思路 