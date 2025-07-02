#!/usr/bin/env python3
"""
ComfyFusion Engine 服务器启动脚本

使用方法:
    python run_server.py

这个脚本会启动基于 FastMCP 的 ComfyUI 智能代理服务，
实现三工具协作架构和流式协议支持。
"""

import sys
import os
from pathlib import Path

# 添加 src 目录到 Python 路径
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# 设置工作目录
os.chdir(project_root)

def main():
    """启动ComfyFusion Engine MCP服务器"""
    try:
        # 导入并启动服务器
        from comfyfusion.server import main as server_main
        
        print("🚀 启动 ComfyFusion Engine...")
        print("📁 项目目录:", project_root)
        print("🔧 基于 FastMCP 2.0+ 的三工具协作架构")
        print("📡 支持流式协议和实时反馈")
        print()
        
        # 启动服务器
        server_main()
        
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保已安装所有依赖:")
        print("pip install -e .")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 