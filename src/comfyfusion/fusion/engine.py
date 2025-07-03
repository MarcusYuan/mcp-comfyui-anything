"""
工作流融合引擎

简化版本，专注于三层融合核心逻辑：
1. 基础工作流 (Workflow) - 完整的默认配置
2. 模板补丁 (Template) - 预设风格补丁
3. 用户补丁 (User Patch) - 用户实时参数
"""

import json
import copy
from typing import Dict, Any, Optional, List
from deepmerge import always_merger

from ..utils.logger import get_logger
from .patcher import Patcher # 导入Patcher

logger = get_logger(__name__)


class WorkflowFusionEngine:
    """简化的工作流融合引擎"""
    
    def __init__(self):
        logger.info("工作流融合引擎初始化")
        self.patcher = Patcher(strategy='merge') # 初始化Patcher

    async def fusion_workflow(
        self,
        base_workflow: Dict[str, Any],
        template_patch: Optional[Dict[str, Any]] = None,
        user_patch: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行两级融合：
        1. 融合用户补丁和模板补丁，生成统一补丁（无占位符）。
        2. 将统一补丁应用到基础工作流。
        
        Args:
            base_workflow: 基础工作流（完整配置）
            template_patch: 模板补丁（预设风格）
            user_patch: 用户补丁（实时参数）
            
        Returns:
            融合后的最终工作流
        """
        logger.info("开始执行两级工作流融合")
        
        # 第一步：融合用户补丁和模板补丁
        unified_patch = self.patcher.fuse(user_patch, template_patch)
        logger.info(f"统一补丁生成完成，节点数: {len(unified_patch.get('nodes', {}))}")
        
        
        # 第二步：应用统一补丁到基础工作流
        final_workflow = self._apply_unified_patch(base_workflow, unified_patch)
        
        logger.info(f"工作流融合完成，最终节点数: {len(final_workflow)}")
        
        # 打印最终工作流中 seed 参数的值
        seed_value = final_workflow.get("31", {}).get("inputs", {}).get("seed", "未找到")
        logger.info(f"融合后工作流中节点31的seed值: {seed_value}")
        return final_workflow
    
    def _apply_unified_patch(
        self,
        workflow: Dict[str, Any],
        unified_patch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        将统一补丁（无占位符）应用到工作流。
        仅更新工作流中已存在的节点的输入字段（不添加新节点或新字段）。
        """
        final_workflow = copy.deepcopy(workflow)
        
        # 提取节点补丁配置
        node_patches = unified_patch.get("nodes", {})
        
        for node_id, node_patch in node_patches.items():
            if node_id not in final_workflow:
                logger.warning(f"统一补丁引用不存在的节点: {node_id}，已跳过。")
                continue
                
            # 仅处理节点中的输入字段
            patch_inputs = node_patch.get("inputs", {})
            base_node = final_workflow[node_id]
            
            if "inputs" not in base_node:
                logger.warning(f"节点 {node_id} 缺少 inputs 字段，无法应用补丁")
                continue
                
            # 仅更新基础节点中已存在的输入字段
            for key, value in patch_inputs.items():
                if key in base_node["inputs"]:
                    base_node["inputs"][key] = value
                else:
                    logger.warning(f"节点 {node_id} 的输入字段 {key} 不存在于基础工作流，已跳过。")
        
        return final_workflow
    
    def validate_workflow(self, workflow: Dict[str, Any]) -> bool:
        """
        验证工作流格式
        
        Args:
            workflow: 要验证的工作流
            
        Returns:
            是否有效
        """
        try:
            # 基本格式检查
            if not isinstance(workflow, dict):
                return False
            
            # 检查是否包含节点
            if not workflow:
                return False
            
            # 检查节点格式
            for node_id, node_config in workflow.items():
                if not isinstance(node_config, dict):
                    return False
                
                # 检查必要字段
                if "class_type" not in node_config:
                    logger.warning(f"节点 {node_id} 缺少 class_type 字段")
                    return False
                
                if "inputs" not in node_config:
                    logger.warning(f"节点 {node_id} 缺少 inputs 字段")
                    return False
                
                # 新增：检查占位符是否被替换
                if self._contains_placeholders(node_config):
                    logger.warning(f"节点 {node_id} 包含未替换的占位符")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"工作流验证失败: {e}")
            return False

    def _contains_placeholders(self, config: Dict[str, Any]) -> bool:
        """
        检查配置中是否包含占位符 {var}
        """
        for key, value in config.items():
            if isinstance(value, str) and "{" in value and "}" in value:
                return True
            elif isinstance(value, dict) and self._contains_placeholders(value):
                return True
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and self._contains_placeholders(item):
                        return True
        return False
    
    def get_workflow_info(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取工作流信息
        
        Args:
            workflow: 工作流配置
            
        Returns:
            工作流信息统计
        """
        if not workflow:
            return {"node_count": 0, "node_types": []}
        
        node_types = []
        for node_config in workflow.values():
            if isinstance(node_config, dict) and "class_type" in node_config:
                class_type = node_config["class_type"]
                if class_type not in node_types:
                    node_types.append(class_type)
        
        return {
            "node_count": len(workflow),
            "node_types": node_types,
            "unique_node_types": len(node_types)
        }