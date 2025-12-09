#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复长沙POI和武汉道路的坐标问题
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point
import os
import shutil

def fix_coordinate_issues():
    """修复坐标问题"""
    
    # 设置环境变量
    os.environ['SHAPE_RESTORE_SHX'] = 'YES'
    
    # 城市中心坐标
    city_centers = {
        '长沙五一广场': (112.9823, 28.1949),  # 长沙五一广场
        '武汉黄鹤楼': (114.3055, 30.5467),   # 武汉黄鹤楼
        '北京天安门': (116.4074, 39.9042)    # 北京天安门（参考）
    }
    
    beijing_center = city_centers['北京天安门']
    
    print("=== 修复长沙POI坐标问题 ===")
    
    # 修复长沙POI数据
    changsha_center = city_centers['长沙五一广场']
    changsha_poi_path = "data/长沙五一广场/POI数据.shp"
    backup_path = "data/长沙五一广场/backup_poi_data"
    
    try:
        # 创建备份目录
        if not os.path.exists(backup_path):
            os.makedirs(backup_path)
        
        # 备份原始文件
        for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg', '.sbn', '.sbx']:
            src_file = f"data/长沙五一广场/POI数据{ext}"
            if os.path.exists(src_file):
                dst_file = f"{backup_path}/POI数据{ext}"
                shutil.copy2(src_file, dst_file)
                print(f"备份文件: {src_file}")
        
        # 读取POI数据
        poi_gdf = gpd.read_file(changsha_poi_path)
        print(f"读取到 {len(poi_gdf)} 个POI")
        
        # 计算坐标偏移量（从北京坐标转换为长沙坐标）
        lng_offset = changsha_center[0] - beijing_center[0]
        lat_offset = changsha_center[1] - beijing_center[1]
        
        print(f"长沙POI坐标偏移量: 经度 {lng_offset:.6f}, 纬度 {lat_offset:.6f}")
        
        # 转换几何坐标
        def transform_point(geom):
            if geom.geom_type == 'Point':
                x, y = geom.x, geom.y
                return Point(x + lng_offset, y + lat_offset)
            else:
                return geom
        
        # 应用坐标转换
        poi_gdf['geometry'] = poi_gdf['geometry'].apply(transform_point)
        
        # 保存修复后的数据
        poi_gdf.to_file(changsha_poi_path)
        print(f"保存修复后的长沙POI数据到: {changsha_poi_path}")
        
        # 验证修复结果
        test_gdf = gpd.read_file(changsha_poi_path)
        if len(test_gdf) > 0:
            first_poi = test_gdf.iloc[0]
            first_coord = (first_poi.geometry.x, first_poi.geometry.y)
            print(f"修复后第一个POI坐标: ({first_coord[0]:.6f}, {first_coord[1]:.6f})")
            
            # 检查坐标是否在长沙附近
            if abs(first_coord[0] - changsha_center[0]) < 0.1 and abs(first_coord[1] - changsha_center[1]) < 0.1:
                print("✓ 长沙POI坐标修复成功")
            else:
                print("✗ 长沙POI坐标修复可能有问题")
        
    except Exception as e:
        print(f"修复长沙POI坐标时出错: {e}")
    
    print("\n=== 检查武汉道路坐标问题 ===")
    
    # 检查武汉道路数据是否需要修复
    wuhan_road_path = "data/武汉黄鹤楼/道路数据.shp"
    
    try:
        wuhan_road_gdf = gpd.read_file(wuhan_road_path)
        print(f"武汉道路数量: {len(wuhan_road_gdf)}")
        
        if len(wuhan_road_gdf) > 0:
            # 获取道路坐标范围
            bounds = wuhan_road_gdf.bounds
            min_lng = bounds['minx'].min()
            max_lng = bounds['maxx'].max()
            min_lat = bounds['miny'].min()
            max_lat = bounds['maxy'].max()
            
            print(f"武汉道路当前坐标范围:")
            print(f"  经度: {min_lng:.6f} ~ {max_lng:.6f}")
            print(f"  纬度: {min_lat:.6f} ~ {max_lat:.6f}")
            
            # 检查是否在武汉地区 (武汉大致范围: 经度113.5-115.5, 纬度29.5-31.5)
            if 113.5 <= min_lng <= 115.5 and 113.5 <= max_lng <= 115.5 and 29.5 <= min_lat <= 31.5 and 29.5 <= max_lat <= 31.5:
                print("✓ 武汉道路坐标已经正确，无需修复")
            else:
                print("✗ 武汉道路坐标需要修复")
                # 这里可以添加修复逻辑，但根据检查结果，武汉道路坐标应该是正确的
        
    except Exception as e:
        print(f"检查武汉道路坐标时出错: {e}")

if __name__ == "__main__":
    fix_coordinate_issues()