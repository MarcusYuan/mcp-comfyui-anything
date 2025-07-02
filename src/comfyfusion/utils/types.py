"""
ComfyFusion Engine 核心数据类型定义
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import time


class MediaType(Enum):
    """媒体类型枚举"""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    OTHER = "other"


class ComfyUIExecutionState(Enum):
    """ComfyUI执行状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class TaskStatus(Enum):
    """任务状态枚举"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class MediaFileInfo:
    """媒体文件信息"""
    filename: str
    subfolder: str
    media_type: MediaType
    file_size: int
    mime_type: str
    duration: Optional[float] = None  # 视频/音频时长
    dimensions: Optional[tuple] = None  # 图片/视频尺寸
    bitrate: Optional[int] = None  # 视频/音频比特率
    format_info: Optional[Dict] = None  # 格式详细信息
    url: Optional[str] = None  # 访问URL


@dataclass
class WorkflowInfo:
    """工作流信息"""
    name: str
    description: str
    file_path: Path
    template_path: Optional[Path] = None
    has_template: bool = False
    supported_params: List[str] = field(default_factory=list)
    example_params: Dict[str, Any] = field(default_factory=dict)
    media_types: List[MediaType] = field(default_factory=list)
    last_modified: float = field(default_factory=time.time)


@dataclass
class TaskExecutionResult:
    """任务执行结果"""
    task_id: str
    workflow_name: str
    status: TaskStatus
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    execution_time: Optional[float] = None
    
    # 输入参数
    input_params: Dict[str, Any] = field(default_factory=dict)
    use_template: bool = True
    
    # 执行结果
    media_files: List[MediaFileInfo] = field(default_factory=list)
    result_urls: List[str] = field(default_factory=list)
    
    # 错误信息
    error_message: Optional[str] = None
    error_details: Optional[Dict] = None
    
    # ComfyUI 相关
    prompt_id: Optional[str] = None
    comfyui_outputs: Optional[Dict] = None
    
    # 进度信息
    progress_value: int = 0
    progress_max: int = 100
    current_stage: str = "准备中"


@dataclass
class ComfyUIExecutionProgress:
    """ComfyUI执行进度信息"""
    prompt_id: str
    state: ComfyUIExecutionState = ComfyUIExecutionState.PENDING
    current_node: Optional[str] = None
    progress_value: int = 0
    progress_max: int = 100
    cached_nodes: List[str] = field(default_factory=list)
    executed_nodes: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    execution_time: float = 0.0
    queue_remaining: int = 0


# 类型别名
WorkflowDict = Dict[str, Any]  # ComfyUI工作流JSON格式
TemplateDict = Dict[str, Any]  # 模板文件JSON格式
ParameterDict = Dict[str, Any]  # 用户参数字典 