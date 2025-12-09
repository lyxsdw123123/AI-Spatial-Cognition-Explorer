#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复长沙和武汉道路数据的坐标问题
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point
import os
import shutil

def fix_road_coordinates():
    """修复道路坐标数据"""
    
    # 设置环境变量
    os.environ['SHAPE_RESTORE_SHX'] = 'YES'
    
    # 城市中心坐标
    city_centers = {
        '长沙五一广场': (112.9823, 28.1949),  # 长沙五一广场
        '武汉黄鹤楼': (114.3055, 30.5467),   # 武汉黄鹤楼
        '北京天安门': (116.4074, 39.9042)    # 北京天安门（参考）
    }
    
    # 北京的中心坐标（当前道路数据使用的坐标）
    beijing_center = city_centers['北京天安门']
    
    for city, target_center in city_centers.items():
        if city == '北京天安门':
            continue  # 跳过北京，它的坐标是正确的
            
        print(f"\n=== 修复 {city} 道路坐标 ===")
        
        # 文件路径
        road_path = f"data/{city}/道路数据.shp"
        backup_path = f"data/{city}/backup_road_data"
        
        try:
            # 创建备份目录
            if not os.path.exists(backup_path):
                os.makedirs(backup_path)
            
            # 备份原始文件
            for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                src_file = f"data/{city}/道路数据{ext}"
                if os.path.exists(src_file):
                    dst_file = f"{backup_path}/道路数据{ext}"
                    shutil.copy2(src_file, dst_file)
                    print(f"备份文件: {src_file}")
            
            # 读取道路数据
            roads_gdf = gpd.read_file(road_path)
            print(f"读取到 {len(roads_gdf)} 条道路")
            
            # 计算坐标偏移量
            lng_offset = target_center[0] - beijing_center[0]
            lat_offset = target_center[1] - beijing_center[1]
            
            print(f"坐标偏移量: 经度 {lng_offset:.6f}, 纬度 {lat_offset:.6f}")
            
            # 转换几何坐标
            def transform_geometry(geom):
                if geom.geom_type == 'LineString':
                    coords = list(geom.coords)
                    new_coords = [(x + lng_offset, y + lat_offset) for x, y in coords]
                    return LineString(new_coords)
                elif geom.geom_type == 'MultiLineString':
                    new_lines = []
                    for line in geom.geoms:
                        coords = list(line.coords)
                        new_coords = [(x + lng_offset, y + lat_offset) for x, y in coords]
                        new_lines.append(LineString(new_coords))
                    return MultiLineString(new_lines)
                else:
                    return geom
            
            # 应用坐标转换
            roads_gdf['geometry'] = roads_gdf['geometry'].apply(transform_geometry)
            
            # 保存修复后的数据
            roads_gdf.to_file(road_path)
            print(f"保存修复后的道路数据到: {road_path}")
            
            # 验证修复结果
            test_gdf = gpd.read_file(road_path)
            if len(test_gdf) > 0:
                first_road = test_gdf.iloc[0]
                if hasattr(first_road.geometry, 'coords'):
                    coords = list(first_road.geometry.coords)
                    first_coord = coords[0]
                    print(f"修复后第一个坐标: ({first_coord[0]:.6f}, {first_coord[1]:.6f})")
                    
                    # 检查坐标是否在目标城市附近
                    if abs(first_coord[0] - target_center[0]) < 0.1 and abs(first_coord[1] - target_center[1]) < 0.1:
                        print("✓ 坐标修复成功")
                    else:
                        print("✗ 坐标修复可能有问题")
            
        except Exception as e:
            print(f"修复 {city} 道路坐标时出错: {e}")

if __name__ == "__main__":
    fix_road_coordinates()