"""
工作流融合引擎

简化版本，专注于三层融合核心逻辑：
1. 基础工作流 (Workflow) - 完整的默认配置
2. 模板补丁 (Template) - 预设风格补丁
3. 用户补丁 (User Patch) - 用户实时参数
"""

import json
import copy
from typing import Dict, Any, Optional
from deepmerge import always_merger

from ..utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowFusionEngine:
    """简化的工作流融合引擎"""
    
    def __init__(self):
        logger.info("工作流融合引擎初始化")
    
    async def fusion_workflow(
        self,
        base_workflow: Dict[str, Any],
        template_patch: Optional[Dict[str, Any]] = None,
        user_patch: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行三层融合
        
        Args:
            base_workflow: 基础工作流（完整配置）
            template_patch: 模板补丁（预设风格）
            user_patch: 用户补丁（实时参数）
            
        Returns:
            融合后的最终工作流
        """
        logger.info("开始执行三层工作流融合")
        
        # 深拷贝基础工作流，避免修改原始数据
        final_workflow = copy.deepcopy(base_workflow)
        
        # 第一层：应用模板补丁
        if template_patch:
            logger.debug("应用模板补丁...")
            final_workflow = self._apply_template_patch(final_workflow, template_patch)
        
        # 第二层：应用用户补丁
        if user_patch:
            logger.debug("应用用户补丁...")
            final_workflow = self._apply_user_patch(final_workflow, user_patch)
        
        logger.info(f"工作流融合完成，最终节点数: {len(final_workflow)}")
        logger.debug(f"融合后的最终工作流: {json.dumps(final_workflow, indent=2)}")
        # 打印最终工作流中 seed 参数的值
        seed_value = final_workflow.get("31", {}).get("inputs", {}).get("seed", "未找到")
        logger.info(f"融合后工作流中节点31的seed值: {seed_value}")
        return final_workflow
    
    def _apply_template_patch(
        self,
        workflow: Dict[str, Any],
        template_patch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        应用模板补丁
        
        结构化合并节点配置，支持占位符参数
        """
        # 提取节点补丁配置
        node_patches = template_patch.get("nodes", {})
        
        # 深度合并每个节点配置
        for node_id, node_config in node_patches.items():
            if node_id in workflow:
                workflow[node_id] = always_merger.merge(
                    workflow[node_id],
                    node_config
                )
            else:
                logger.warning(f"模板补丁引用不存在的节点: {node_id}")
        
        logger.debug(f"应用模板补丁完成，修改了 {len(node_patches)} 个节点")
        return workflow
    
    def _apply_user_patch(
        self,
        workflow: Dict[str, Any],
        user_patch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        应用用户补丁
        
        递归注入参数值到占位符位置
        """
        def inject_params(obj):
            if isinstance(obj, dict):
                return {k: inject_params(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [inject_params(item) for item in obj]
            elif isinstance(obj, str) and obj.startswith("{") and obj.endswith("}"):
                param_name = obj[1:-1]
                resolved_value = user_patch.get(param_name, obj)
                logger.debug(f"处理占位符: {obj}, 参数名: {param_name}, 解析值: {resolved_value}")
                return resolved_value
            return obj
        
        logger.debug("应用用户补丁...")
        return inject_params(workflow)
    
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
            
            return True
            
        except Exception as e:
            logger.error(f"工作流验证失败: {e}")
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