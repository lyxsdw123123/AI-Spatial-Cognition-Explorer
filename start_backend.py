#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
后端服务启动脚本
"""

import sys
import os
import uvicorn
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.config import Config

def main():
    """启动后端服务"""
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=Config.BACKEND_HOST)
    p.add_argument("--port", type=int, default=Config.BACKEND_PORT)
    p.add_argument("--reload", action="store_true", default=True)
    p.add_argument("--no-reload", dest="reload", action="store_false")
    args = p.parse_args()

    print("🚀 启动AI地图探索后端服务...")
    print(f"📍 服务地址: http://{args.host}:{args.port}")
    print(f"📝 API文档: http://{args.host}:{args.port}/docs")
    print("🛑 按 Ctrl+C 停止服务")
    print("-" * 50)
    
    candidate_ports = [int(args.port), 8010, 8020, 8100, 8200, 8500, 9000]
    tried = set()
    for port in candidate_ports:
        if port in tried:
            continue
        tried.add(port)
        try:
            uvicorn.run(
                "backend.app:app",
                host=str(args.host),
                port=int(port),
                reload=bool(args.reload),
                log_level="info",
            )
            return
        except KeyboardInterrupt:
            print("\n👋 后端服务已停止")
            return
        except OSError as e:
            if os.name == "nt" and getattr(e, "winerror", None) == 10013:
                print(f"❌ 端口 {port} 无权限/被系统保留，尝试下一个端口...", flush=True)
                continue
            print(f"❌ 启动失败: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ 启动失败: {e}")
            sys.exit(1)

    print("❌ 启动失败: 没有可用端口（可能被系统保留或被安全软件拦截）")
    sys.exit(1)

if __name__ == "__main__":
    main()
