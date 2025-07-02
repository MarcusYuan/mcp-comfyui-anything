"""
ComfyFusion Engine - 智能化 ComfyUI 工作流执行引擎

基于 FastMCP 的3工具架构：
1. list_workflows - 工作流枚举器
2. analyze_and_execute - 智能分析执行器
3. execute_workflow - 纯执行引擎
"""

__version__ = "1.0.0"
__author__ = "ComfyFusion Team"
__description__ = "智能化 ComfyUI 工作流执行引擎"

from .server import mcp, main

__all__ = ["mcp", "main"] 