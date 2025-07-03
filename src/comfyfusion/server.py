"""
ComfyFusion Engine - 智能化 ComfyUI 工作流执行引擎

基于 FastMCP 的3工具架构实现：
1. list_workflows - 工作流枚举器
2. analyze_and_execute - 智能分析器（只分析，返回引导信息）
3. execute_workflow - 纯执行引擎
"""

import asyncio
import json
import logging
import time  # 新增导入
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP, Context
from fastmcp.exceptions import McpError

from .utils.config import load_config
from .utils.logger import get_logger, setup_logger
from .utils.workflow_discovery import WorkflowDiscovery
from .fusion.engine import WorkflowFusionEngine
from .api.comfyui_client import ComfyUIClient

# 初始化日志
logger = get_logger(__name__)

# 全局配置和组件
config = load_config()
mcp = FastMCP(
    name=config.mcp.server_name,
    description=config.mcp.description
)

# 初始化核心组件
workflow_discovery = WorkflowDiscovery(config.paths.workflows)
fusion_engine = WorkflowFusionEngine()
comfyui_client = ComfyUIClient(
    host=config.comfyui.host,
    port=config.comfyui.port,
    timeout=config.comfyui.timeout
)


@mcp.tool()
async def list_workflows(ctx: Context) -> Dict[str, Any]:
    """
    工具1：列出所有可用的工作流
    
    返回所有已发现的工作流列表，包含基本信息和参数说明。
    这是用户了解可用工作流能力的入口工具。
    
    Args:
        ctx: FastMCP上下文对象
        
    Returns:
        Dict包含workflows列表，每个工作流包含name、description、category、parameters等信息
    """
    try:
        await ctx.info("正在扫描可用工作流...")
        
        # 发现所有工作流
        workflows = await workflow_discovery.discover_workflows()
        
        # 构造返回数据
        workflow_list = []
        for name, workflow_info in workflows.items():
            # 获取模板信息
            template_info = await workflow_discovery.get_template_info(name)
            
            workflow_data = {
                "name": name,
                "description": template_info.get("description", f"{name} 工作流"),
                "category": template_info.get("category", "general"),
                "parameters": template_info.get("parameters", []),
                "tags": template_info.get("tags", []),
                "version": template_info.get("version", "1.0")
            }
            workflow_list.append(workflow_data)
        
        result = {
            "workflows": workflow_list,
            "total_count": len(workflow_list),
            "status": "success"
        }
        
        await ctx.info(f"发现 {len(workflow_list)} 个可用工作流")
        return result
        
    except Exception as e:
        await ctx.error(f"列出工作流时发生错误: {e}")
        return {
            "workflows": [],
            "total_count": 0,
            "status": "error",
            "error": str(e)
        }


@mcp.tool()
async def analyze_and_execute(
    user_request: str,
    workflow_name: str,
    additional_params: Optional[Dict[str, Any]] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """
    工具2：智能分析器（只负责分析，不执行）
    
    分析用户需求并生成工作流补丁，然后返回引导信息让Client LLM自动调用工具3。
    这符合MCP协议的工具协作原则：工具不直接调用其他工具。
    
    Args:
        user_request: 用户的自然语言需求描述
        workflow_name: 要使用的工作流名称
        additional_params: 可选的额外参数覆盖
        ctx: FastMCP上下文对象
        
    Returns:
        分析结果和引导信息，让Client LLM自动调用execute_workflow工具
    """
    try:
        await ctx.info(f"开始智能分析用户需求，工作流: {workflow_name}")
        await ctx.info(f"用户需求: {user_request}")
        
        # 智能分析阶段
        await ctx.info("开始智能分析用户需求...")
        await ctx.report_progress(progress=10, total=100)
        
        # 获取工作流模板信息
        template_info = await workflow_discovery.get_template_info(workflow_name)
        if not template_info:
            raise McpError(f"未找到工作流模板: {workflow_name}")
        
        await ctx.report_progress(progress=30, total=100)
        
        # 验证工作流名称
        if workflow_name not in workflow_discovery.get_workflow_names():
            raise McpError(f"无效工作流名称: {workflow_name}")
        
        # 构造LLM提示词
        llm_prompt = _construct_llm_prompt(user_request, workflow_name, template_info)
        
        # 返回引导信息
        guidance_text = f"""用户需求分析请求已准备完成：

**用户原始需求**：{user_request}
**目标工作流**：{workflow_name}
**工作流描述**：{template_info.get('description', '无描述')}

**可用参数模板**：
{json.dumps(template_info.get('template', {}).get('nodes', {}), ensure_ascii=False, indent=2)}

请根据用户需求和工作流模板，智能分析并生成合适的参数补丁，然后调用 execute_workflow 工具执行。

**建议的分析方向**：
1. 提取用户需求中的核心描述作为 prompt
2. 推导合适的技术参数（如尺寸、质量、风格等）
3. 生成随机seed确保每次结果不同
4. 构造完整的 workflow_patch 参数

**执行步骤**：调用 execute_workflow 工具，传入 workflow_name="{workflow_name}" 和分析得出的 workflow_patch。"""
        
        await ctx.report_progress(progress=80, total=100)
        await ctx.info("需求分析引导信息已准备完成")
        await ctx.debug(f"LLM分析提示词: {llm_prompt}")
        
        # 构造引导信息，让Client LLM自动分析并调用工具3
        result = {
            "status": "analysis_ready", 
            "workflow_name": workflow_name,
            "user_request": user_request,
            "template_info": template_info,
            "llm_prompt": llm_prompt,
            
            # 关键：引导信息，让Client LLM进行智能分析
            "next_action": "Please analyze the user request and call execute_workflow tool to complete the generation",
            "recommended_analysis": {
                "step1": "Extract core description as prompt",
                "step2": "Infer appropriate parameters (size, quality, style, etc.)",
                "step3": "Generate random seed for unique results", 
                "step4": "Call execute_workflow with workflow_name and constructed workflow_patch"
            },
            "guidance": guidance_text
        }
        
        await ctx.report_progress(progress=100, total=100)
        await ctx.info("分析完成，请调用execute_workflow工具执行生成")
        
        return result
        
    except Exception as e:
        await ctx.error(f"智能分析过程中发生错误: {e}")
        return {
            "status": "error",
            "error": str(e),
            "workflow_name": workflow_name,
            "user_request": user_request
        }


@mcp.tool()
async def execute_workflow(
    workflow_name: str,
    workflow_patch: Dict[str, Any],
    ctx: Context = None
) -> Dict[str, Any]:
    """
    工具3：纯执行引擎，执行融合后的工作流
    
    接收完整的workflow补丁，执行两级融合并调用ComfyUI API。
    
    Args:
        workflow_name: 工作流名称
        workflow_patch: 已填充的参数补丁
        ctx: FastMCP上下文对象
        
    Returns:
        执行结果，包含生成文件的ComfyUI原生URL
    """
    try:
        await ctx.debug("进入execute_workflow函数")
        await ctx.info(f"开始执行工作流: {workflow_name}")
        # 添加更显眼的日志，打印传入的 workflow_patch
        logger.error(f"DEBUG_WORKFLOW_PATCH: {json.dumps(workflow_patch, indent=2, ensure_ascii=False)}")
        
        await ctx.debug(f"使用补丁: {workflow_patch}")
        await ctx.report_progress(progress=0, total=100)
        
        # 1. 加载基础工作流
        await ctx.info("加载基础工作流...")
        base_workflow = await workflow_discovery.load_workflow(workflow_name)
        if not base_workflow:
            raise McpError(f"未找到基础工作流: {workflow_name}")
        
        await ctx.debug("基础工作流加载完成")
        logger.debug(f"基础工作流节点数: {len(base_workflow)}")  # 新增节点数日志
        await ctx.report_progress(progress=20, total=100)
        
        # 2. 加载模板补丁
        await ctx.info("加载模板补丁...")
        template_patch = await workflow_discovery.load_template(workflow_name)
        
        await ctx.debug("模板补丁加载完成")
        logger.debug(f"模板补丁节点数: {len(template_patch)}")  # 新增节点数日志
        await ctx.report_progress(progress=30, total=100)
        
        # 3. 执行两级融合
        await ctx.info("执行两级工作流融合...")
        start_fusion = time.time()  # 新增融合开始时间
        final_workflow = await fusion_engine.fusion_workflow(
            base_workflow=base_workflow,
            template_patch=template_patch,
            user_patch=workflow_patch
        )
        fusion_time = time.time() - start_fusion  # 新增融合耗时
        logger.debug(f"工作流融合耗时: {fusion_time:.2f}秒")  # 新增耗时日志
        
        await ctx.debug("工作流融合完成")
        await ctx.info("工作流融合完成")
        await ctx.debug(f"最终工作流节点数: {len(final_workflow)}")
        
        # 验证工作流格式
        if not fusion_engine.validate_workflow(final_workflow):
            error_msg = "融合后的工作流格式无效"
            logger.error(error_msg)
            await ctx.debug("工作流验证失败")
            return {"status": "error", "error": error_msg}
        
        await ctx.debug("工作流验证完成")
        
        # 详细调试输出融合后的工作流结构
        # 检查每个顶级键
        for key, value in final_workflow.items():
            if isinstance(value, dict):
                if 'class_type' in value:
                    pass
                else:
                    pass
            else:
                pass
        
        # 查找所有无效节点（缺少class_type的节点）
        invalid_nodes = []
        for node_id, node_config in final_workflow.items():
            if isinstance(node_config, dict) and "class_type" not in node_config:
                invalid_nodes.append(node_id)
                logger.warning(f"发现无效节点: {node_id}, 配置: {node_config}")
        
        if invalid_nodes:
            logger.error(f"发现 {len(invalid_nodes)} 个无效节点: {invalid_nodes}")
            # 尝试移除无效节点
            for invalid_node in invalid_nodes:
                logger.info(f"移除无效节点: {invalid_node}")
                del final_workflow[invalid_node]
        
        await ctx.report_progress(progress=50, total=100)
        logger.debug(f"移除无效节点后剩余节点数: {len(final_workflow)}")  # 新增节点数日志
        
        # 4. 调用ComfyUI API执行
        await ctx.info("提交到ComfyUI执行...")
        start_execution = time.time()  # 新增执行开始时间
        execution_result = await comfyui_client.execute_workflow(final_workflow)
        execution_time = time.time() - start_execution  # 新增执行耗时
        logger.debug(f"ComfyUI执行耗时: {execution_time:.2f}秒")  # 新增耗时日志
        
        await ctx.debug("ComfyUI执行完成")
        await ctx.report_progress(progress=90, total=100)
        
        # 5. 构造返回结果
        result = {
            "status": "success",
            "workflow_name": workflow_name,
            "execution_id": execution_result.get("prompt_id"),
            "queue_position": execution_result.get("queue_position", 0),
            "output_files": execution_result.get("output_files", []),
            "comfyui_urls": execution_result.get("comfyui_urls", []),
            "execution_time": execution_result.get("execution_time"),
            "node_count": len(final_workflow)
        }
        
        await ctx.report_progress(progress=100, total=100)
        await ctx.debug("工作流执行结果处理完成")
        await ctx.info(f"工作流执行完成，生成 {len(result['output_files'])} 个文件")
        logger.debug(f"输出文件详情: {json.dumps(result['output_files'], indent=2)}")  # 新增文件详情日志
        
        return result
        
    except Exception as e:
        error_type = type(e).__name__  # 获取异常类型
        await ctx.debug(f"execute_workflow异常 [{error_type}]: {str(e)}")
        await ctx.error(f"执行工作流时发生错误 [{error_type}]: {e}")
        logger.exception("工作流执行失败详情")  # 新增详细异常日志
        return {
            "status": "error",
            "error_type": error_type,  # 新增异常类型
            "error": str(e),
            "workflow_name": workflow_name,
            "workflow_patch": workflow_patch
        }


def _construct_llm_prompt(
    user_request: str,
    workflow_name: str,
    template_info: Dict[str, Any]
) -> str:
    """
    构造给LLM的提示词，用于生成工作流补丁
    
    Args:
        user_request: 用户原始需求
        workflow_name: 工作流名称
        template_info: 模板信息
        
    Returns:
        构造好的LLM提示词
    """
    prompt = f"""
请分析以下用户需求，并根据工作流模板生成相应的参数补丁。

用户需求：
{user_request}

工作流名称：{workflow_name}
工作流描述：{template_info.get('description', '无描述')}

可用参数模板：
{json.dumps(template_info.get('parameters', {}), indent=2, ensure_ascii=False)}

请生成一个JSON格式的参数补丁，将用户的自然语言需求转换为具体的参数值。
只返回JSON数据，不要包含其他文本。

示例格式：
{{
    "prompt": "用户描述的具体内容",
    "style": "推导出的风格参数",
    "size": "合适的尺寸参数",
    "quality": "质量设置"
}}
"""
    return prompt



async def initialize_server():
    """初始化服务器组件"""
    try:
        logger.info("正在初始化ComfyFusion Engine...")
        
        # 启动工作流发现
        await workflow_discovery.start_discovery()
        
        # 测试ComfyUI连接
        if await comfyui_client.test_connection():
            logger.info("ComfyUI连接测试成功")
        else:
            logger.warning("ComfyUI连接测试失败，请检查ComfyUI是否运行")
        
        logger.info("ComfyFusion Engine初始化完成")
        
    except Exception as e:
        logger.error(f"服务器初始化失败: {e}")
        raise


def main():
    """主函数：运行MCP服务器"""
    try:
        # 初始化日志系统
        log_level = "INFO"
        if hasattr(config, 'logging') and config.logging:
            log_level = config.logging.get("level", "INFO")
        setup_logger(log_level)
        
        # 初始化服务器
        asyncio.run(initialize_server())
        
        # 根据配置选择传输协议
        transport = "stdio"  # 默认值
        host = "127.0.0.1"
        port = 8000
        
        if hasattr(config, 'mcp') and config.mcp:
            if hasattr(config.mcp, 'protocol') and config.mcp.protocol == "streaming":
                transport = "streamable-http"  # 使用流式HTTP协议
                if hasattr(config.mcp, 'host'):
                    host = config.mcp.host
                if hasattr(config.mcp, 'port'):
                    port = config.mcp.port
        
        # 启动MCP服务器
        if transport == "streamable-http":
            logger.info(f"启动ComfyFusion MCP服务器 (Streamable HTTP协议) - {host}:{port}")
            mcp.run(transport="streamable-http", host=host, port=port)
        else:
            logger.info("启动ComfyFusion MCP服务器 (STDIO协议)")
            mcp.run(transport="stdio")
        
    except KeyboardInterrupt:
        logger.info("服务器被用户中断")
    except Exception as e:
        logger.error(f"服务器运行错误: {e}")
        raise


if __name__ == "__main__":
    main()