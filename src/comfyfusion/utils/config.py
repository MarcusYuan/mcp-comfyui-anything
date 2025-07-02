"""
配置管理模块

简化版本，专注于基本配置加载
"""

import json
import argparse # 导入 argparse
from pathlib import Path
from typing import Any, Dict
from dataclasses import dataclass

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class ComfyUIConfig:
    """ComfyUI连接配置"""
    host: str = "127.0.0.1"
    port: int = 8188
    timeout: int = 300


@dataclass 
class MCPConfig:
    """MCP服务器配置"""
    server_name: str = "comfyfusion-engine"
    description: str = "ComfyUI 智能工作流执行引擎"
    version: str = "1.0.0"
    protocol: str = "streaming"
    enable_streams: bool = True
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass
class PathConfig:
    """路径配置"""
    workflows: str = "./workflows"


@dataclass
class AppConfig:
    """应用配置"""
    comfyui: ComfyUIConfig
    mcp: MCPConfig
    paths: PathConfig
    logging: Dict[str, Any] = None


def load_config(config_path: str = "config/settings.json") -> AppConfig:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        应用配置对象
    """
    config_file = Path(config_path)

    # 默认配置
    default_config = {
        "comfyui": {
            "host": "127.0.0.1",
            "port": 8188,
            "timeout": 300
        },
        "mcp": {
            "server_name": "comfyfusion-engine",
            "description": "ComfyUI 智能工作流执行引擎",
            "version": "1.0.0",
            "protocol": "streaming",
            "enable_streams": True,
            "host": "127.0.0.1",
            "port": 8000
        },
        "paths": {
            "workflows": "./workflows"
        },
        "logging": {
            "level": "INFO"
        }
    }

    # 尝试加载配置文件
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)

            # 合并配置
            merged_config = {**default_config, **file_config}
            logger.info(f"配置文件加载成功: {config_path}")

        except Exception as e:
            logger.warning(f"配置文件加载失败，使用默认配置: {e}")
            merged_config = default_config
    else:
        logger.info("配置文件不存在，使用默认配置")
        merged_config = default_config

    # 解析命令行参数
    parser = argparse.ArgumentParser(description="ComfyFusion Engine Configuration")
    parser.add_argument("--comfyui-host", type=str, help="ComfyUI host address")
    parser.add_argument("--comfyui-port", type=int, help="ComfyUI port")
    parser.add_argument("--mcp-protocol", type=str, help="MCP server protocol")
    parser.add_argument("--mcp-host", type=str, help="MCP server host address")
    parser.add_argument("--mcp-port", type=int, help="MCP server port")
    parser.add_argument("--workflows-path", type=str, help="Path to workflows directory")

    args = parser.parse_args()

    # 应用命令行参数覆盖
    if args.comfyui_host:
        merged_config["comfyui"]["host"] = args.comfyui_host
    if args.comfyui_port:
        merged_config["comfyui"]["port"] = args.comfyui_port
    if args.mcp_protocol:
        merged_config["mcp"]["protocol"] = args.mcp_protocol
    if args.mcp_host:
        merged_config["mcp"]["host"] = args.mcp_host
    if args.mcp_port:
        merged_config["mcp"]["port"] = args.mcp_port
    if args.workflows_path:
        merged_config["paths"]["workflows"] = args.workflows_path

    # 创建配置对象
    comfyui_config = ComfyUIConfig(**merged_config["comfyui"])
    mcp_config = MCPConfig(**merged_config["mcp"])
    path_config = PathConfig(**merged_config["paths"])

    config = AppConfig(
        comfyui=comfyui_config,
        mcp=mcp_config,
        paths=path_config,
        logging=merged_config.get("logging", {"level": "INFO"})
    )

    logger.info("应用配置初始化完成")
    return config