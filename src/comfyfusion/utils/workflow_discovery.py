"""
工作流发现模块

简化版本，专注于核心功能：
- 发现workflow和template文件对
- 加载工作流和模板内容
- 提取模板信息
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import aiofiles

from .logger import get_logger

logger = get_logger(__name__)


class WorkflowFileHandler(FileSystemEventHandler):
    """工作流文件变化处理器"""
    
    def __init__(self, discovery):
        self.discovery = discovery
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            logger.info(f"检测到工作流文件变化: {event.src_path}")
            # 触发重新发现
            try:
                asyncio.create_task(self.discovery._scan_workflows())
            except RuntimeError:
                # 如果没有运行的事件循环，跳过
                logger.warning("没有运行的事件循环，跳过工作流重新扫描")


class WorkflowDiscovery:
    """简化的工作流发现引擎"""
    
    def __init__(self, workflows_dir: str):
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(exist_ok=True)
        
        self.workflows: Dict[str, Dict] = {}
        self.templates: Dict[str, Dict] = {}
        
        self.observer = Observer()
        self.file_handler = WorkflowFileHandler(self)
        
        logger.info(f"工作流发现引擎初始化，监控目录: {self.workflows_dir}")
    
    async def start_discovery(self):
        """启动工作流发现"""
        logger.info("启动工作流发现...")
        
        # 初始扫描
        await self._scan_workflows()
        
        # 启动文件监控
        try:
            self.observer.schedule(
                self.file_handler, 
                str(self.workflows_dir), 
                recursive=False
            )
            self.observer.start()
            logger.info("文件监控启动成功")
        except Exception as e:
            logger.warning(f"文件监控启动失败: {e}")
        
        logger.info(f"工作流发现启动完成，发现 {len(self.workflows)} 个工作流")
    
    async def discover_workflows(self) -> Dict[str, Dict]:
        """发现所有工作流"""
        await self._scan_workflows()
        return self.workflows.copy()
    
    async def _scan_workflows(self):
        """扫描工作流目录"""
        
        
        workflows = {}
        templates = {}
        
        try:
            # 扫描所有.json文件
            for file_path in self.workflows_dir.glob("*.json"):
                if file_path.name.endswith("_tp.json"):
                    # 模板文件
                    workflow_name = file_path.stem[:-3]  # 去掉_tp后缀
                    try:
                        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                            content = await f.read()
                            templates[workflow_name] = json.loads(content)
                            
                    except Exception as e:
                        logger.error(f"加载模板文件失败 {file_path}: {e}")
                else:
                    # 工作流文件
                    workflow_name = file_path.stem
                    try:
                        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                            content = await f.read()
                            workflows[workflow_name] = json.loads(content)
                            
                    except Exception as e:
                        logger.error(f"加载工作流文件失败 {file_path}: {e}")
            
            # 只保留有配对模板的工作流
            valid_workflows = {}
            for name, workflow in workflows.items():
                if name in templates:
                    valid_workflows[name] = workflow
                    
                else:
                    logger.warning(f"工作流 {name} 没有对应的模板文件")
            
            self.workflows = valid_workflows
            self.templates = templates
            
            logger.info(f"扫描完成，发现 {len(self.workflows)} 个工作流")
            
        except Exception as e:
            logger.error(f"扫描工作流目录时发生错误: {e}")
    
    async def load_workflow(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """加载基础工作流"""
        if workflow_name not in self.workflows:
            await self._scan_workflows()  # 重新扫描
        
        return self.workflows.get(workflow_name)
    
    async def load_template(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """加载模板补丁"""
        if workflow_name not in self.templates:
            await self._scan_workflows()  # 重新扫描
        
        return self.templates.get(workflow_name)
    
    async def get_template_info(self, workflow_name: str) -> Dict[str, Any]:
        """获取模板信息"""
        template = await self.load_template(workflow_name)
        if not template:
            return {}
        
        # 从模板的_meta字段获取信息
        meta_info = template.get("_meta", {})
        
        # 从模板的节点中提取参数信息
        parameters = self._extract_parameters_from_template(template)
        
        # 构造标准化的模板信息
        info = {
            "description": meta_info.get("description", f"{workflow_name} 工作流"),
            "category": meta_info.get("category", "general"),
            "parameters": parameters,
            "tags": meta_info.get("tags", ["comfyui", "workflow"]),
            "version": meta_info.get("version", "1.0"),
            "author": meta_info.get("author", "unknown"),
            "created_at": meta_info.get("created_at", ""),
            "updated_at": meta_info.get("updated_at", "")
        }
        
        return info
    
    def _extract_parameters_from_template(self, template: Dict[str, Any]) -> Dict[str, str]:
        """从模板中提取参数信息"""
        parameters = {}
        
        def extract_from_dict(d, path=""):
            if isinstance(d, dict):
                for key, value in d.items():
                    if key == "_meta":  # 跳过元数据
                        continue
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                        param_name = value[1:-1]  # 去掉大括号
                        parameters[param_name] = f"模板参数: {current_path}"
                    elif isinstance(value, (dict, list)):
                        extract_from_dict(value, current_path)
            elif isinstance(d, list):
                for i, item in enumerate(d):
                    extract_from_dict(item, f"{path}[{i}]")
        
        extract_from_dict(template)
        
        return parameters
    
    def stop_discovery(self):
        """停止工作流发现"""
        try:
            if self.observer.is_alive():
                self.observer.stop()
                self.observer.join()
                logger.info("工作流发现停止")
        except Exception as e:
            logger.warning(f"停止工作流发现时发生错误: {e}")
    
    def get_workflow_count(self) -> int:
        """获取已发现的工作流数量"""
        return len(self.workflows)
    
    def get_workflow_names(self) -> List[str]:
        """获取所有工作流名称"""
        return list(self.workflows.keys())
    
    def validate_workflow_pair(self, workflow_name: str) -> bool:
        """验证工作流和模板文件对是否有效"""
        workflow_file = self.workflows_dir / f"{workflow_name}.json"
        template_file = self.workflows_dir / f"{workflow_name}_tp.json"
        
        return workflow_file.exists() and template_file.exists() 