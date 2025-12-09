#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键启动脚本 - 同时启动前后端服务
"""

import sys
import os
import subprocess
import time
import threading
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.config import Config

def start_backend():
    """启动后端服务"""
    print("🚀 正在启动后端服务...")
    try:
        subprocess.run([sys.executable, "start_backend.py"], cwd=project_root)
    except Exception as e:
        print(f"❌ 后端启动失败: {e}")

def start_frontend():
    """启动前端应用"""
    print("🎨 正在启动前端应用...")
    # 等待后端启动
    time.sleep(3)
    try:
        subprocess.run([sys.executable, "start_frontend.py"], cwd=project_root)
    except Exception as e:
        print(f"❌ 前端启动失败: {e}")

def check_dependencies():
    """检查依赖包"""
    print("🔍 检查依赖包...")
    
    required_packages = [
        'streamlit', 'fastapi', 'uvicorn', 'folium', 
        'streamlit-folium', 'requests', 'pandas', 'langchain'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少以下依赖包: {', '.join(missing_packages)}")
        print("💡 请运行: pip install -r requirements.txt")
        return False
    
    print("✅ 所有依赖包已安装")
    return True

def main():
    """主函数"""
    print("="*60)
    print("🗺️  AI地图探索系统 - 一键启动")
    print("="*60)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    print(f"📍 后端服务: http://{Config.BACKEND_HOST}:{Config.BACKEND_PORT}")
    print(f"📍 前端应用: http://{Config.FRONTEND_HOST}:{Config.FRONTEND_PORT}")
    print(f"📝 API文档: http://{Config.BACKEND_HOST}:{Config.BACKEND_PORT}/docs")
    print("🛑 按 Ctrl+C 停止所有服务")
    print("-" * 60)
    
    try:
        # 创建线程启动后端
        backend_thread = threading.Thread(target=start_backend, daemon=True)
        backend_thread.start()
        
        # 等待一段时间后启动前端
        time.sleep(5)
        
        # 启动前端（主线程）
        start_frontend()
        
    except KeyboardInterrupt:
        print("\n👋 所有服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()