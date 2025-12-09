#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前端应用启动脚本
"""

import sys
import os
import subprocess
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.config import Config

def main():
    """启动前端应用"""
    print("🎨 启动AI地图探索前端应用...")
    print(f"📍 应用地址: http://{Config.FRONTEND_HOST}:{Config.FRONTEND_PORT}")
    print("🛑 按 Ctrl+C 停止应用")
    print("-" * 50)
    
    try:
        # 构建streamlit命令
        cmd = [
            sys.executable, 
            "-m", "streamlit", "run", 
            "frontend/app.py",
            "--server.port", str(Config.FRONTEND_PORT),
            "--server.address", Config.FRONTEND_HOST,
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false"
        ]
        
        # 启动streamlit应用
        subprocess.run(cmd, cwd=project_root)
        
    except KeyboardInterrupt:
        print("\n👋 前端应用已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()