#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试前端数据加载器
"""

from frontend.local_data_loader import load_local_shapefile_data

def test_frontend_loader():
    print("=== 测试长沙前端数据加载 ===")
    result = load_local_shapefile_data('长沙五一广场')
    print(f"POI成功: {result['poi_success']}")
    print(f"道路成功: {result['road_success']}")
    print(f"道路节点成功: {result['road_nodes_success']}")
    print(f"POI数量: {len(result['pois'])}")
    print(f"道路数量: {len(result['roads'])}")
    print(f"道路节点数量: {len(result['road_nodes'])}")
    
    print("\n=== 测试武汉前端数据加载 ===")
    result = load_local_shapefile_data('武汉黄鹤楼')
    print(f"POI成功: {result['poi_success']}")
    print(f"道路成功: {result['road_success']}")
    print(f"道路节点成功: {result['road_nodes_success']}")
    print(f"POI数量: {len(result['pois'])}")
    print(f"道路数量: {len(result['roads'])}")
    print(f"道路节点数量: {len(result['road_nodes'])}")
    
    # 检查武汉道路数据的具体内容
    if result['road_success'] and len(result['roads']) > 0:
        print(f"\n武汉道路数据示例:")
        for i, road in enumerate(result['roads'][:3]):  # 显示前3条道路
            print(f"  道路{i+1}: {road['name']}, 坐标点数: {len(road['coordinates'])}")
    else:
        print("\n武汉道路数据为空或加载失败")

if __name__ == "__main__":
    test_frontend_loader()