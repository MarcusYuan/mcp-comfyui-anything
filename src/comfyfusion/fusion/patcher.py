import copy
from typing import Dict, Any

class Patcher:
    """
    补丁融合器，负责将用户补丁和模板补丁进行融合。
    支持不同的融合策略。
    """
    STRATEGIES = ['merge', 'override', 'smart'] # 定义支持的融合策略

    def __init__(self, strategy: str = 'merge'):
        if strategy not in self.STRATEGIES:
            raise ValueError(f"不支持的融合策略: {strategy}. 可用策略: {', '.join(self.STRATEGIES)}")
        self.strategy = strategy
        self.variables = {}  # 存储占位符变量

    def set_variables(self, variables: Dict[str, str]):
        """设置占位符变量值"""
        self.variables = variables

    def fuse(self, user_patch: Dict[str, Any], template_patch: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据设定的策略融合用户补丁和模板补丁。
        
        Args:
            user_patch: 用户提供的参数补丁。
            template_patch: 模板定义的参数补丁。
            
        Returns:
            融合后的统一补丁。
        """
        # 创建模板补丁的深拷贝
        merged = copy.deepcopy(template_patch)
        
        # 遍历模板补丁中的所有节点
        for node_id, node_config in merged.get("nodes", {}).items():
            # 遍历节点的所有输入字段
            inputs = node_config.get("inputs", {})
            for key, value in inputs.items():
                # 如果字段值是字符串且包含{}格式的变量
                if isinstance(value, str) and "{" in value and "}" in value:
                    # 提取变量名（去除{}）
                    var_name = value.strip("{}")
                    # 在用户补丁中查找变量值
                    if var_name in user_patch:
                        # 用用户补丁中的实际值替换变量
                        inputs[key] = user_patch[var_name]
        
        return merged

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """
        递归深度合并两个字典，update中的值会覆盖base中的值。
        """
        merged = copy.deepcopy(base)
        for key, value in update.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

