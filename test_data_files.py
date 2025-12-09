#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试长沙和武汉的数据文件
"""

import geopandas as gpd
import os

def test_data_files():
    os.environ['SHAPE_RESTORE_SHX'] = 'YES'
    
    print("=== 测试长沙五一广场数据 ===")
    
    # 测试长沙POI数据
    try:
        poi_gdf = gpd.read_file('data/长沙五一广场/POI数据.shp', encoding='utf-8')
        print(f"✓ 长沙POI数据: {len(poi_gdf)} 行")
        if len(poi_gdf) > 0:
            print(f"  列名: {list(poi_gdf.columns)}")
    except Exception as e:
        print(f"✗ 长沙POI数据错误: {e}")
    
    # 测试长沙道路数据
    try:
        road_gdf = gpd.read_file('data/长沙五一广场/道路数据.shp', encoding='utf-8')
        print(f"✓ 长沙道路数据: {len(road_gdf)} 行")
        if len(road_gdf) > 0:
            print(f"  列名: {list(road_gdf.columns)}")
    except Exception as e:
        print(f"✗ 长沙道路数据错误: {e}")
    
    # 测试长沙道路节点数据
    try:
        node_gdf = gpd.read_file('data/长沙五一广场/道路节点数据.shp', encoding='utf-8')
        print(f"✓ 长沙道路节点数据: {len(node_gdf)} 行")
        if len(node_gdf) > 0:
            print(f"  列名: {list(node_gdf.columns)}")
    except Exception as e:
        print(f"✗ 长沙道路节点数据错误: {e}")
    
    print("\n=== 测试武汉黄鹤楼数据 ===")
    
    # 测试武汉POI数据
    try:
        poi_gdf = gpd.read_file('data/武汉黄鹤楼/POI数据.shp', encoding='utf-8')
        print(f"✓ 武汉POI数据: {len(poi_gdf)} 行")
        if len(poi_gdf) > 0:
            print(f"  列名: {list(poi_gdf.columns)}")
    except Exception as e:
        print(f"✗ 武汉POI数据错误: {e}")
    
    # 测试武汉道路数据
    try:
        road_gdf = gpd.read_file('data/武汉黄鹤楼/道路数据.shp', encoding='utf-8')
        print(f"✓ 武汉道路数据: {len(road_gdf)} 行")
        if len(road_gdf) > 0:
            print(f"  列名: {list(road_gdf.columns)}")
    except Exception as e:
        print(f"✗ 武汉道路数据错误: {e}")
    
    # 测试武汉道路节点数据
    try:
        node_gdf = gpd.read_file('data/武汉黄鹤楼/道路节点数据.shp', encoding='utf-8')
        print(f"✓ 武汉道路节点数据: {len(node_gdf)} 行")
        if len(node_gdf) > 0:
            print(f"  列名: {list(node_gdf.columns)}")
    except Exception as e:
        print(f"✗ 武汉道路节点数据错误: {e}")

if __name__ == "__main__":
    test_data_files()