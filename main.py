#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI地图探索系统 - 主入口文件
"""

import sys
import os
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="AI地图探索系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py --mode all          # 启动完整系统（前端+后端）
  python main.py --mode backend      # 仅启动后端服务
  python main.py --mode frontend     # 仅启动前端应用
  python main.py --check             # 检查环境和依赖
        """
    )
    
    parser.add_argument(
        "--mode", 
        choices=["all", "backend", "frontend"],
        default="all",
        help="启动模式 (默认: all)"
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="检查环境和依赖"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="AI地图探索系统 v1.0.0"
    )
    
    args = parser.parse_args()
    
    # 显示欢迎信息
    print_welcome()
    
    # 检查环境
    if args.check or args.mode:
        if not check_environment():
            sys.exit(1)
    
    if args.check:
        print("✅ 环境检查完成，系统可以正常运行")
        return
    
    # 根据模式启动相应服务
    if args.mode == "all":
        start_all_services()
    elif args.mode == "backend":
        start_backend_only()
    elif args.mode == "frontend":
        start_frontend_only()

def print_welcome():
    """打印欢迎信息"""
    print("="*70)
    print("🗺️  AI地图探索系统 (AI Map Explorer)")
    print("="*70)
    print("📋 项目描述: 让AI在陌生地图中自主探索并形成心理地图")
    print("🔧 技术栈: Streamlit + FastAPI + LangChain + 高德地图")
    print("👨‍💻 版本: v1.0.0")
    print("-"*70)

def check_environment():
    """检查环境和依赖"""
    print("🔍 正在检查环境...")
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ Python版本过低，需要Python 3.8+")
        return False
    print(f"✅ Python版本: {sys.version.split()[0]}")
    
    # 检查必要的依赖包
    required_packages = {
        'streamlit': 'Streamlit前端框架',
        'fastapi': 'FastAPI后端框架',
        'uvicorn': 'ASGI服务器',
        'folium': '地图可视化',
        'requests': 'HTTP请求库',
        'pandas': '数据处理',
        'pydantic': '数据验证'
    }
    
    missing_packages = []
    for package, description in required_packages.items():
        try:
            __import__(package)
            print(f"✅ {description}: {package}")
        except ImportError:
            print(f"❌ {description}: {package} (未安装)")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n💡 请安装缺少的依赖包:")
        print(f"   pip install {' '.join(missing_packages)}")
        print(f"   或者运行: pip install -r requirements.txt")
        return False
    
    # 检查配置文件
    env_file = project_root / ".env"
    if not env_file.exists():
        print("⚠️  未找到.env配置文件")
        print("💡 请复制.env.example为.env并配置API密钥")
        print("   cp .env.example .env")
    else:
        print("✅ 配置文件: .env")
    
    # 检查项目结构
    required_dirs = ['frontend', 'backend', 'ai_agent', 'map_service', 'config']
    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists():
            print(f"✅ 目录结构: {dir_name}/")
        else:
            print(f"❌ 目录结构: {dir_name}/ (缺失)")
            return False
    
    return True

def start_all_services():
    """启动完整系统"""
    print("🚀 启动完整系统...")
    try:
        import subprocess
        subprocess.run([sys.executable, "start_all.py"], cwd=project_root)
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

def start_backend_only():
    """仅启动后端"""
    print("🚀 启动后端服务...")
    try:
        import subprocess
        subprocess.run([sys.executable, "start_backend.py"], cwd=project_root)
    except Exception as e:
        print(f"❌ 后端启动失败: {e}")
        sys.exit(1)

def start_frontend_only():
    """仅启动前端"""
    print("🎨 启动前端应用...")
    try:
        import subprocess
        subprocess.run([sys.executable, "start_frontend.py"], cwd=project_root)
    except Exception as e:
        print(f"❌ 前端启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 程序已退出")
    except Exception as e:
        print(f"❌ 程序异常: {e}")
        sys.exit(1)