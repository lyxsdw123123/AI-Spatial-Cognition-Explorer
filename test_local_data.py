#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append('frontend')

from frontend.local_data_loader import load_local_shapefile_data

def test_local_data_loading():
    """测试本地数据加载功能"""
    print("开始测试本地shapefile数据加载...")
    
    result = load_local_shapefile_data()
    
    if 'error' in result:
        print(f"❌ 加载失败: {result['error']}")
        return False
    
    print(f"POI加载成功: {result['poi_success']}")
    print(f"道路加载成功: {result['road_success']}")
    print(f"POI数量: {len(result['pois'])}")
    print(f"道路数量: {len(result['roads'])}")
    
    if result['poi_success'] and len(result['pois']) > 0:
        print("\n前3个POI示例:")
        for i, poi in enumerate(result['pois'][:3]):
            print(f"  {i+1}. {poi['name']} - {poi['type']} - {poi['location']}")
    
    if result['road_success'] and len(result['roads']) > 0:
        print("\n前3条道路示例:")
        for i, road in enumerate(result['roads'][:3]):
            coord_count = len(road['coordinates']) if 'coordinates' in road else 0
            print(f"  {i+1}. {road['name']} - 坐标点数: {coord_count}")
    
    success = result['poi_success'] and result['road_success']
    print(f"\n总体测试结果: {'✅ 成功' if success else '❌ 失败'}")
    return success

if __name__ == "__main__":
    test_local_data_loading()