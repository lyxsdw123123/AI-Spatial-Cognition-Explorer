#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试长沙和武汉数据加载问题
"""

import geopandas as gpd
import os
import sys

def check_data_files(region_name):
    """检查指定区域的数据文件"""
    print(f"\n=== 检查 {region_name} 数据文件 ===")
    
    # 数据文件路径
    data_dir = os.path.join(os.path.dirname(__file__), 'data', region_name)
    poi_file = os.path.join(data_dir, 'POI数据.shp')
    road_file = os.path.join(data_dir, '道路数据.shp')
    road_nodes_file = os.path.join(data_dir, '道路节点数据.shp')
    
    print(f"数据目录: {data_dir}")
    print(f"目录是否存在: {os.path.exists(data_dir)}")
    
    # 检查POI文件
    print(f"\nPOI文件: {poi_file}")
    print(f"POI文件是否存在: {os.path.exists(poi_file)}")
    if os.path.exists(poi_file):
        try:
            poi_gdf = gpd.read_file(poi_file, encoding='utf-8')
            print(f"POI数据行数: {len(poi_gdf)}")
            print(f"POI数据列: {list(poi_gdf.columns)}")
            if len(poi_gdf) > 0:
                print(f"前3个POI名称: {poi_gdf['name'].head(3).tolist() if 'name' in poi_gdf.columns else '无name字段'}")
        except Exception as e:
            print(f"读取POI数据失败: {e}")
    
    # 检查道路文件
    print(f"\n道路文件: {road_file}")
    print(f"道路文件是否存在: {os.path.exists(road_file)}")
    if os.path.exists(road_file):
        try:
            road_gdf = gpd.read_file(road_file, encoding='utf-8')
            print(f"道路数据行数: {len(road_gdf)}")
            print(f"道路数据列: {list(road_gdf.columns)}")
            if len(road_gdf) > 0:
                print(f"前3个道路名称: {road_gdf['name'].head(3).tolist() if 'name' in road_gdf.columns else '无name字段'}")
        except Exception as e:
            print(f"读取道路数据失败: {e}")
    
    # 检查道路节点文件
    print(f"\n道路节点文件: {road_nodes_file}")
    print(f"道路节点文件是否存在: {os.path.exists(road_nodes_file)}")
    if os.path.exists(road_nodes_file):
        try:
            nodes_gdf = gpd.read_file(road_nodes_file, encoding='utf-8')
            print(f"道路节点数据行数: {len(nodes_gdf)}")
            print(f"道路节点数据列: {list(nodes_gdf.columns)}")
        except Exception as e:
            print(f"读取道路节点数据失败: {e}")

def test_loader_function():
    """测试加载器函数"""
    print("\n=== 测试加载器函数 ===")
    
    # 导入加载器函数
    sys.path.append(os.path.join(os.path.dirname(__file__), 'frontend'))
    from local_data_loader import load_local_shapefile_data
    
    # 测试长沙数据加载
    print("\n--- 测试长沙五一广场数据加载 ---")
    changsha_result = load_local_shapefile_data("长沙五一广场")
    print(f"POI加载成功: {changsha_result['poi_success']}")
    print(f"道路加载成功: {changsha_result['road_success']}")
    print(f"道路节点加载成功: {changsha_result['road_nodes_success']}")
    print(f"POI数量: {len(changsha_result['pois'])}")
    print(f"道路数量: {len(changsha_result['roads'])}")
    print(f"道路节点数量: {len(changsha_result['road_nodes'])}")
    
    # 测试武汉数据加载
    print("\n--- 测试武汉黄鹤楼数据加载 ---")
    wuhan_result = load_local_shapefile_data("武汉黄鹤楼")
    print(f"POI加载成功: {wuhan_result['poi_success']}")
    print(f"道路加载成功: {wuhan_result['road_success']}")
    print(f"道路节点加载成功: {wuhan_result['road_nodes_success']}")
    print(f"POI数量: {len(wuhan_result['pois'])}")
    print(f"道路数量: {len(wuhan_result['roads'])}")
    print(f"道路节点数量: {len(wuhan_result['road_nodes'])}")
    
    # 对比北京数据加载
    print("\n--- 测试北京天安门数据加载（对比） ---")
    beijing_result = load_local_shapefile_data("北京天安门")
    print(f"POI加载成功: {beijing_result['poi_success']}")
    print(f"道路加载成功: {beijing_result['road_success']}")
    print(f"道路节点加载成功: {beijing_result['road_nodes_success']}")
    print(f"POI数量: {len(beijing_result['pois'])}")
    print(f"道路数量: {len(beijing_result['roads'])}")
    print(f"道路节点数量: {len(beijing_result['road_nodes'])}")

if __name__ == "__main__":
    # 检查长沙和武汉的数据文件
    check_data_files("长沙五一广场")
    check_data_files("武汉黄鹤楼")
    check_data_files("北京天安门")  # 对比
    
    # 测试加载器函数
    test_loader_function()