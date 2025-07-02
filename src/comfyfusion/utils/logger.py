"""
简化的日志配置模块
"""

import logging
import sys
from typing import Optional


def get_logger(name: str) -> logging.Logger:
    """
    获取logger实例
    
    Args:
        name: logger名称
        
    Returns:
        Logger实例
    """
    return logging.getLogger(name)


def setup_logger(level: str = "INFO") -> None:
    """
    设置基础日志系统
    
    Args:
        level: 日志级别
    """
    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建控制台处理器
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    
    # 设置第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    logger = get_logger(__name__)
    logger.info(f"日志系统初始化完成，级别: {level}") 