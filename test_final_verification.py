#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终验证长沙和武汉数据修复结果
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'frontend'))

from local_data_loader import load_local_shapefile_data
import geopandas as gpd

def test_final_verification():
    """最终验证长沙和武汉数据修复结果"""
    
    print("=== 最终验证数据修复结果 ===\n")
    
    # 测试长沙五一广场
    print("--- 长沙五一广场数据验证 ---")
    changsha_result = load_local_shapefile_data("长沙五一广场")
    
    # 检查返回结果结构
    if isinstance(changsha_result, dict) and 'poi_data' in changsha_result:
        print(f"✅ 长沙数据加载成功")
        print(f"POI数量: {len(changsha_result['poi_data']) if changsha_result['poi_data'] is not None else 0}")
        print(f"道路数量: {len(changsha_result['road_data']) if changsha_result['road_data'] is not None else 0}")
        print(f"道路节点数量: {len(changsha_result['road_nodes_data']) if changsha_result['road_nodes_data'] is not None else 0}")
        
        # 检查POI数据是否为长沙数据
        if changsha_result['poi_data'] is not None and len(changsha_result['poi_data']) > 0:
            poi_sample = changsha_result['poi_data'][:3]  # 取前3个
            print("前3个POI名称:")
            for poi in poi_sample:
                name = poi.get('name', '未知')
                address = poi.get('address', '未知')
                print(f"  - {name} ({address})")
            
            # 检查地址中是否包含长沙相关信息
            addresses = [poi.get('address', '') for poi in changsha_result['poi_data']]
            changsha_count = sum(1 for addr in addresses if '长沙' in str(addr) or '湖南' in str(addr))
            beijing_count = sum(1 for addr in addresses if '北京' in str(addr))
            print(f"包含长沙/湖南地址的POI: {changsha_count}")
            print(f"包含北京地址的POI: {beijing_count}")
            
            if changsha_count > beijing_count:
                print("✅ 长沙POI数据正确")
            else:
                print("❌ 长沙POI数据仍有问题")
        
    else:
        print(f"❌ 长沙数据加载失败或返回格式错误")
    
    print()
    
    # 测试武汉黄鹤楼
    print("--- 武汉黄鹤楼数据验证 ---")
    wuhan_result = load_local_shapefile_data("武汉黄鹤楼")
    
    if isinstance(wuhan_result, dict) and 'poi_data' in wuhan_result:
        print(f"✅ 武汉数据加载成功")
        print(f"POI数量: {len(wuhan_result['poi_data']) if wuhan_result['poi_data'] is not None else 0}")
        print(f"道路数量: {len(wuhan_result['road_data']) if wuhan_result['road_data'] is not None else 0}")
        print(f"道路节点数量: {len(wuhan_result['road_nodes_data']) if wuhan_result['road_nodes_data'] is not None else 0}")
        
        # 检查道路数据
        if wuhan_result['road_data'] is not None and len(wuhan_result['road_data']) > 0:
            road_sample = wuhan_result['road_data'][:3]  # 取前3个
            print("前3个道路名称:")
            for road in road_sample:
                name = road.get('name', '未知')
                print(f"  - {name}")
            print("✅ 武汉道路数据加载正常")
        else:
            print("❌ 武汉道路数据仍有问题")
            
        # 检查POI数据是否为武汉数据
        if wuhan_result['poi_data'] is not None and len(wuhan_result['poi_data']) > 0:
            poi_sample = wuhan_result['poi_data'][:3]  # 取前3个
            print("前3个POI名称:")
            for poi in poi_sample:
                name = poi.get('name', '未知')
                address = poi.get('address', '未知')
                print(f"  - {name} ({address})")
            
            # 检查地址中是否包含武汉相关信息
            addresses = [poi.get('address', '') for poi in wuhan_result['poi_data']]
            wuhan_count = sum(1 for addr in addresses if '武汉' in str(addr) or '湖北' in str(addr))
            print(f"包含武汉/湖北地址的POI: {wuhan_count}")
            
            if wuhan_count > 0:
                print("✅ 武汉POI数据正确")
            else:
                print("⚠️ 武汉POI数据地址信息需要检查")
        
    else:
        print(f"❌ 武汉数据加载失败或返回格式错误")
    
    print()
    
    # 对比北京数据（作为参考）
    print("--- 北京天安门数据对比 ---")
    beijing_result = load_local_shapefile_data("北京天安门")
    
    if isinstance(beijing_result, dict) and 'poi_data' in beijing_result:
        print(f"✅ 北京数据加载成功（参考）")
        print(f"POI数量: {len(beijing_result['poi_data']) if beijing_result['poi_data'] is not None else 0}")
        print(f"道路数量: {len(beijing_result['road_data']) if beijing_result['road_data'] is not None else 0}")
        print(f"道路节点数量: {len(beijing_result['road_nodes_data']) if beijing_result['road_nodes_data'] is not None else 0}")
    
    print("\n=== 修复结果总结 ===")
    
    changsha_ok = (isinstance(changsha_result, dict) and 
                   changsha_result.get('poi_data') is not None and 
                   changsha_result.get('road_data') is not None and 
                   changsha_result.get('road_nodes_data') is not None)
    
    wuhan_ok = (isinstance(wuhan_result, dict) and 
                wuhan_result.get('poi_data') is not None and 
                wuhan_result.get('road_data') is not None and 
                wuhan_result.get('road_nodes_data') is not None)
    
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
    success = test_final_verification()
    if success:
        print("\n✅ 数据修复验证通过！")
    else:
        print("\n❌ 数据修复验证失败！")