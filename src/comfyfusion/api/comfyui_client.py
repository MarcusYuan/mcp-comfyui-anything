"""
ComfyUI API 客户端

简化版本，专注于核心功能：
- 连接测试
- 执行工作流
- 获取结果文件URL
"""

import json
import time
import asyncio
from typing import Dict, Any, List, Optional
import httpx

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ComfyUIClient:
    """简化的ComfyUI API客户端"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8188, timeout: int = 300):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"
        
        # 初始化HTTP客户端
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=10)
        )
        
        logger.info(f"ComfyUI客户端初始化: {self.base_url}")
    
    async def test_connection(self) -> bool:
        """测试ComfyUI连接"""
        try:
            response = await self.client.get(f"{self.base_url}/system_stats")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"ComfyUI连接测试失败: {e}")
            return False
    
    async def execute_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工作流
        
        Args:
            workflow: 完整的工作流配置
            
        Returns:
            执行结果，包含文件URL等信息
        """
        logger.info("开始执行ComfyUI工作流")
        start_time = time.time()
        
        try:
            # 提交工作流到队列
            prompt_response = await self._submit_prompt(workflow)
            prompt_id = prompt_response["prompt_id"]
            
            logger.info(f"工作流已提交，prompt_id: {prompt_id}")
            
            # 等待执行完成
            result = await self._wait_for_completion(prompt_id)
            
            # 获取输出文件
            output_files = await self._get_output_files(prompt_id, result)
            
            execution_time = time.time() - start_time
            
            final_result = {
                "prompt_id": prompt_id,
                "queue_position": prompt_response.get("number", 0),
                "output_files": output_files,
                "comfyui_urls": self._generate_comfyui_urls(output_files),
                "execution_time": execution_time,
                "status": "completed"
            }
            
            logger.info(f"工作流执行完成，耗时: {execution_time:.2f}秒")
            return final_result
            
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def _submit_prompt(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """提交prompt到ComfyUI"""
        prompt_data = {
            "prompt": workflow,
            "client_id": "comfyfusion"
        }
        
        logger.debug(f"发送给ComfyUI的工作流 (prompt_data): {json.dumps(prompt_data, indent=2)}")
        
        response = await self.client.post(
            f"{self.base_url}/prompt",
            json=prompt_data
        )
        
        if response.status_code != 200:
            # 尝试解析错误响应
            logger.error(f"提交prompt失败，HTTP状态码: {response.status_code}")
            logger.error(f"ComfyUI原始响应: {response.text}")
            try:
                error_data = response.json()
                if "error" in error_data:
                    error_info = error_data["error"]
                    if isinstance(error_info, dict) and "message" in error_info:
                        error_message = error_info["message"]
                        if "details" in error_info:
                            error_message += f" - {error_info['details']}"
                        raise Exception(f"ComfyUI错误: {error_message}")
                    else:
                        raise Exception(f"ComfyUI错误: {error_info}")
                else:
                    raise Exception(f"提交prompt失败: {response.status_code} {error_data}")
            except (json.JSONDecodeError, ValueError):
                # 如果不是JSON，使用原始文本
                raise Exception(f"提交prompt失败: {response.status_code} {response.text}")
        
        return response.json()
    
    async def _wait_for_completion(self, prompt_id: str) -> Dict[str, Any]:
        """等待执行完成"""
        logger.info(f"等待执行完成: {prompt_id}")
        
        max_attempts = self.timeout // 2  # 每2秒检查一次
        
        for attempt in range(max_attempts):
            # 检查执行状态
            history_response = await self.client.get(f"{self.base_url}/history/{prompt_id}")
            
            if history_response.status_code == 200:
                history_data = history_response.json()
                logger.debug(f"ComfyUI历史响应 (prompt_id: {prompt_id}): {json.dumps(history_data, indent=2)}")

                if not history_data:
                    logger.debug(f"ComfyUI历史响应为空，继续等待... (prompt_id: {prompt_id})")
                    await asyncio.sleep(2) # 额外等待，避免频繁请求
                    continue
                
                if prompt_id in history_data:
                    result = history_data[prompt_id]
                    
                    # 检查是否完成
                    if result.get("status", {}).get("completed", False):
                        logger.info(f"执行完成: {prompt_id}")
                        return result
                    
                    # 检查是否出错
                    if "error" in result.get("status", {}):
                        error_msg = result["status"]["error"]
                        raise Exception(f"ComfyUI执行错误: {error_msg}")
                else:
                    logger.debug(f"ComfyUI历史响应中未找到prompt_id: {prompt_id}，继续等待...")
            
            # 等待一段时间后重试
            await asyncio.sleep(2)
            
            if attempt % 10 == 0:  # 每20秒打印一次进度
                logger.info(f"执行进行中... ({attempt * 2}秒)")
        
        raise Exception(f"执行超时: {prompt_id}")
    
    async def _get_output_files(self, prompt_id: str, result: Dict[str, Any]) -> List[str]:
        """获取输出文件列表"""
        output_files = []
        
        # 从结果中提取输出文件
        outputs = result.get("outputs", {})
        
        for node_id, node_outputs in outputs.items():
            # 查找图片输出
            if "images" in node_outputs:
                for image_info in node_outputs["images"]:
                    if "filename" in image_info:
                        output_files.append(image_info["filename"])
            
            # 查找视频输出
            if "videos" in node_outputs:
                for video_info in node_outputs["videos"]:
                    if "filename" in video_info:
                        output_files.append(video_info["filename"])
            
            # 查找其他文件输出
            if "files" in node_outputs:
                for file_info in node_outputs["files"]:
                    if "filename" in file_info:
                        output_files.append(file_info["filename"])
        
        logger.info(f"发现 {len(output_files)} 个输出文件")
        return output_files
    
    def _generate_comfyui_urls(self, filenames: List[str]) -> List[str]:
        """生成ComfyUI原生文件访问URL"""
        urls = []
        
        for filename in filenames:
            # 生成ComfyUI的view URL
            url = f"{self.base_url}/view?filename={filename}"
            urls.append(url)
        
        return urls
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        try:
            response = await self.client.get(f"{self.base_url}/queue")
            if response.status_code == 200:
                return response.json()
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            logger.error(f"获取队列状态失败: {e}")
            return {"error": str(e)}
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            response = await self.client.get(f"{self.base_url}/system_stats")
            if response.status_code == 200:
                return response.json()
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {"error": str(e)}
    
    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()
        logger.info("ComfyUI客户端连接已关闭") 