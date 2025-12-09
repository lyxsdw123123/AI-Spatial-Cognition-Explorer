#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单验证长沙和武汉数据修复结果
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'frontend'))

from local_data_loader import load_local_shapefile_data

def test_simple_verification():
    """简单验证长沙和武汉数据修复结果"""
    
    print("=== 简单验证数据修复结果 ===\n")
    
    # 测试长沙五一广场
    print("--- 长沙五一广场数据验证 ---")
    changsha_result = load_local_shapefile_data("长沙五一广场")
    print(f"长沙返回结果类型: {type(changsha_result)}")
    print(f"长沙返回结果键: {list(changsha_result.keys()) if isinstance(changsha_result, dict) else 'Not a dict'}")
    
    if isinstance(changsha_result, dict):
        poi_success = changsha_result.get('poi_success', False)
        road_success = changsha_result.get('road_success', False)
        road_nodes_success = changsha_result.get('road_nodes_success', False)
        
        pois = changsha_result.get('pois', [])
        roads = changsha_result.get('roads', [])
        road_nodes = changsha_result.get('road_nodes', [])
        
        print(f"POI加载成功: {poi_success}, 数量: {len(pois)}")
        print(f"道路加载成功: {road_success}, 数量: {len(roads)}")
        print(f"道路节点加载成功: {road_nodes_success}, 数量: {len(road_nodes)}")
        
        if pois and len(pois) > 0:
            print("前3个POI:")
            for i, poi in enumerate(pois[:3]):
                print(f"  {i+1}. {poi}")
    
    print()
    
    # 测试武汉黄鹤楼
    print("--- 武汉黄鹤楼数据验证 ---")
    wuhan_result = load_local_shapefile_data("武汉黄鹤楼")
    print(f"武汉返回结果类型: {type(wuhan_result)}")
    print(f"武汉返回结果键: {list(wuhan_result.keys()) if isinstance(wuhan_result, dict) else 'Not a dict'}")
    
    if isinstance(wuhan_result, dict):
        poi_success = wuhan_result.get('poi_success', False)
        road_success = wuhan_result.get('road_success', False)
        road_nodes_success = wuhan_result.get('road_nodes_success', False)
        
        pois = wuhan_result.get('pois', [])
        roads = wuhan_result.get('roads', [])
        road_nodes = wuhan_result.get('road_nodes', [])
        
        print(f"POI加载成功: {poi_success}, 数量: {len(pois)}")
        print(f"道路加载成功: {road_success}, 数量: {len(roads)}")
        print(f"道路节点加载成功: {road_nodes_success}, 数量: {len(road_nodes)}")
        
        if roads and len(roads) > 0:
            print("前3个道路:")
            for i, road in enumerate(roads[:3]):
                print(f"  {i+1}. {road}")
    
    print()
    
    # 对比北京数据
    print("--- 北京天安门数据对比 ---")
    beijing_result = load_local_shapefile_data("北京天安门")
    print(f"北京返回结果类型: {type(beijing_result)}")
    print(f"北京返回结果键: {list(beijing_result.keys()) if isinstance(beijing_result, dict) else 'Not a dict'}")
    
    print("\n=== 修复结果总结 ===")
    
    changsha_ok = (isinstance(changsha_result, dict) and 
                   changsha_result.get('poi_success', False) and 
                   changsha_result.get('road_success', False) and 
                   changsha_result.get('road_nodes_success', False))
    
    wuhan_ok = (isinstance(wuhan_result, dict) and 
                wuhan_result.get('poi_success', False) and 
                wuhan_result.get('road_success', False) and 
                wuhan_result.get('road_nodes_success', False))
    
    if changsha_ok and wuhan_ok:
        print("🎉 所有数据修复完成！长沙和武汉的POI、道路和道路节点数据都能正确加载。")
        return True
    else:
        print("❌ 仍有数据问题需要解决。")
        if not changsha_ok:
            print("  - 长沙数据仍有问题")
        if not wuhan_ok:
            print("  - 武汉数据仍有问题")
        return False

if __name__ == "__main__":
    success = test_simple_verification()
    if success:
        print("\n✅ 数据修复验证通过！")
    else:
        print("\n❌ 数据修复验证失败！")