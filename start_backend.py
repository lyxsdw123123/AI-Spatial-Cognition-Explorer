#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
后端服务启动脚本
"""

import sys
import os
import uvicorn
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.config import Config

def main():
    """启动后端服务"""
    print("🚀 启动AI地图探索后端服务...")
    print(f"📍 服务地址: http://{Config.BACKEND_HOST}:{Config.BACKEND_PORT}")
    print("📝 API文档: http://127.0.0.1:8000/docs")
    print("🛑 按 Ctrl+C 停止服务")
    print("-" * 50)
    
    try:
        uvicorn.run(
            "backend.app:app",
            host=Config.BACKEND_HOST,
            port=Config.BACKEND_PORT,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 后端服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()