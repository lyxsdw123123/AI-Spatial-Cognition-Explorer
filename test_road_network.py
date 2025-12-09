#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试道路网络路径规划功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_service.local_data_service import LocalDataService

def test_road_network():
    """测试道路网络功能"""
    print("🧪 开始测试道路网络功能...")
    
    # 初始化本地数据服务
    local_data_service = LocalDataService()
    
    # 加载道路数据
    print("📁 加载道路数据...")
    local_data_service.load_road_data()
    
    # 检查道路数据是否加载成功
    if local_data_service.roads_gdf is None:
        print("❌ 道路数据加载失败")
        return False
    
    print(f"✅ 道路数据加载成功，共{len(local_data_service.roads_gdf)}条道路")
    
    # 检查道路网络是否构建成功
    if local_data_service.road_network is None:
        print("❌ 道路网络未构建")
        return False
    
    print(f"✅ 道路网络构建成功，节点数: {local_data_service.road_network.number_of_nodes()}, 边数: {local_data_service.road_network.number_of_edges()}")
    
    # 测试路径规划
    print("\n🗺️ 测试路径规划功能...")
    
    # 天安门附近的两个测试点
    start_point = (116.3974, 39.9093)  # 天安门 (经度, 纬度)
    end_point = (116.4074, 39.9193)    # 天安门东北方向约1公里
    
    print(f"起点: {start_point}")
    print(f"终点: {end_point}")
    
    # 计算路径
    path = local_data_service.find_shortest_path(start_point, end_point)
    
    if not path:
        print("❌ 路径计算失败")
        return False
    
    print(f"✅ 路径计算成功，路径点数: {len(path)}")
    
    if len(path) > 2:
        print("✅ 使用了道路网络路径规划（路径点数 > 2）")
        print(f"路径预览: {path[:3]}...{path[-3:] if len(path) > 6 else path[3:]}")
    else:
        print("⚠️ 可能使用了直线路径（路径点数 = 2）")
        print(f"路径: {path}")
    
    return True

if __name__ == "__main__":
    success = test_road_network()
    if success:
        print("\n🎉 道路网络测试完成")
    else:
        print("\n❌ 道路网络测试失败")
        sys.exit(1)