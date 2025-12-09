#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查长沙和武汉的坐标问题
"""

import geopandas as gpd
import os
from frontend.local_data_loader import load_local_shapefile_data

def check_coordinate_issues():
    """检查长沙和武汉的坐标问题"""
    
    # 设置环境变量
    os.environ['SHAPE_RESTORE_SHX'] = 'YES'
    
    print("=== 检查长沙五一广场坐标问题 ===")
    
    # 检查长沙POI数据
    changsha_poi_path = "data/长沙五一广场/POI数据.shp"
    changsha_road_path = "data/长沙五一广场/道路数据.shp"
    
    try:
        # 读取长沙POI数据
        changsha_poi_gdf = gpd.read_file(changsha_poi_path)
        print(f"长沙POI数量: {len(changsha_poi_gdf)}")
        
        if len(changsha_poi_gdf) > 0:
            # 获取POI坐标范围
            bounds = changsha_poi_gdf.bounds
            min_lng = bounds['minx'].min()
            max_lng = bounds['maxx'].max()
            min_lat = bounds['miny'].min()
            max_lat = bounds['maxy'].max()
            
            print(f"长沙POI坐标范围:")
            print(f"  经度: {min_lng:.6f} ~ {max_lng:.6f}")
            print(f"  纬度: {min_lat:.6f} ~ {max_lat:.6f}")
            
            # 检查是否在长沙地区 (长沙大致范围: 经度111.5-114.5, 纬度27.5-29.0)
            if 111.5 <= min_lng <= 114.5 and 111.5 <= max_lng <= 114.5 and 27.5 <= min_lat <= 29.0 and 27.5 <= max_lat <= 29.0:
                print("✓ 长沙POI坐标在正确范围内")
            else:
                print("✗ 长沙POI坐标可能不正确")
                
        # 读取长沙道路数据
        changsha_road_gdf = gpd.read_file(changsha_road_path)
        print(f"长沙道路数量: {len(changsha_road_gdf)}")
        
        if len(changsha_road_gdf) > 0:
            # 获取道路坐标范围
            bounds = changsha_road_gdf.bounds
            min_lng = bounds['minx'].min()
            max_lng = bounds['maxx'].max()
            min_lat = bounds['miny'].min()
            max_lat = bounds['maxy'].max()
            
            print(f"长沙道路坐标范围:")
            print(f"  经度: {min_lng:.6f} ~ {max_lng:.6f}")
            print(f"  纬度: {min_lat:.6f} ~ {max_lat:.6f}")
            
            # 检查是否在长沙地区
            if 111.5 <= min_lng <= 114.5 and 111.5 <= max_lng <= 114.5 and 27.5 <= min_lat <= 29.0 and 27.5 <= max_lat <= 29.0:
                print("✓ 长沙道路坐标在正确范围内")
            else:
                print("✗ 长沙道路坐标可能不正确")
                
    except Exception as e:
        print(f"读取长沙数据时出错: {e}")
    
    print("\n=== 检查武汉黄鹤楼坐标问题 ===")
    
    # 检查武汉数据
    wuhan_poi_path = "data/武汉黄鹤楼/POI数据.shp"
    wuhan_road_path = "data/武汉黄鹤楼/道路数据.shp"
    
    try:
        # 读取武汉POI数据
        wuhan_poi_gdf = gpd.read_file(wuhan_poi_path)
        print(f"武汉POI数量: {len(wuhan_poi_gdf)}")
        
        if len(wuhan_poi_gdf) > 0:
            # 获取POI坐标范围
            bounds = wuhan_poi_gdf.bounds
            min_lng = bounds['minx'].min()
            max_lng = bounds['maxx'].max()
            min_lat = bounds['miny'].min()
            max_lat = bounds['maxy'].max()
            
            print(f"武汉POI坐标范围:")
            print(f"  经度: {min_lng:.6f} ~ {max_lng:.6f}")
            print(f"  纬度: {min_lat:.6f} ~ {max_lat:.6f}")
            
            # 检查是否在武汉地区 (武汉大致范围: 经度113.5-115.5, 纬度29.5-31.5)
            if 113.5 <= min_lng <= 115.5 and 113.5 <= max_lng <= 115.5 and 29.5 <= min_lat <= 31.5 and 29.5 <= max_lat <= 31.5:
                print("✓ 武汉POI坐标在正确范围内")
            else:
                print("✗ 武汉POI坐标可能不正确")
                
        # 读取武汉道路数据
        wuhan_road_gdf = gpd.read_file(wuhan_road_path)
        print(f"武汉道路数量: {len(wuhan_road_gdf)}")
        
        if len(wuhan_road_gdf) > 0:
            # 获取道路坐标范围
            bounds = wuhan_road_gdf.bounds
            min_lng = bounds['minx'].min()
            max_lng = bounds['maxx'].max()
            min_lat = bounds['miny'].min()
            max_lat = bounds['maxy'].max()
            
            print(f"武汉道路坐标范围:")
            print(f"  经度: {min_lng:.6f} ~ {max_lng:.6f}")
            print(f"  纬度: {min_lat:.6f} ~ {max_lat:.6f}")
            
            # 检查是否在武汉地区
            if 113.5 <= min_lng <= 115.5 and 113.5 <= max_lng <= 115.5 and 29.5 <= min_lat <= 31.5 and 29.5 <= max_lat <= 31.5:
                print("✓ 武汉道路坐标在正确范围内")
            else:
                print("✗ 武汉道路坐标可能不正确")
                
    except Exception as e:
        print(f"读取武汉数据时出错: {e}")
    
    print("\n=== 使用前端加载器检查数据 ===")
    
    # 使用前端加载器检查数据
    try:
        changsha_result = load_local_shapefile_data('长沙五一广场')
        print(f"前端加载器 - 长沙POI: {len(changsha_result['pois'])}, 道路: {len(changsha_result['roads'])}")
        
        if changsha_result['pois']:
            poi = changsha_result['pois'][0]
            print(f"长沙第一个POI位置: {poi['location']}")
            
        if changsha_result['roads']:
            road = changsha_result['roads'][0]
            print(f"长沙第一条道路坐标: {road['coordinates'][0]}")
            
    except Exception as e:
        print(f"前端加载器检查长沙数据时出错: {e}")
    
    try:
        wuhan_result = load_local_shapefile_data('武汉黄鹤楼')
        print(f"前端加载器 - 武汉POI: {len(wuhan_result['pois'])}, 道路: {len(wuhan_result['roads'])}")
        
        if wuhan_result['pois']:
            poi = wuhan_result['pois'][0]
            print(f"武汉第一个POI位置: {poi['location']}")
            
        if wuhan_result['roads']:
            road = wuhan_result['roads'][0]
            print(f"武汉第一条道路坐标: {road['coordinates'][0]}")
            
    except Exception as e:
        print(f"前端加载器检查武汉数据时出错: {e}")

if __name__ == "__main__":
    check_coordinate_issues()