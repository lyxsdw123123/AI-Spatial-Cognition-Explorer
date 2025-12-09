#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
武汉黄鹤楼道路数据诊断脚本
检查道路数据的坐标系统、文件完整性和与POI数据的一致性
"""

import geopandas as gpd
import pandas as pd
import os
from pathlib import Path

def diagnose_wuhan_data():
    """诊断武汉黄鹤楼的POI和道路数据"""
    
    # 数据文件路径
    data_dir = Path("data/武汉黄鹤楼")
    poi_file = data_dir / "POI数据.shp"
    road_file = data_dir / "道路数据.shp"
    
    print("=" * 60)
    print("武汉黄鹤楼数据诊断报告")
    print("=" * 60)
    
    # 检查文件是否存在
    print("\n1. 文件存在性检查:")
    print(f"POI数据文件: {poi_file.exists()} - {poi_file}")
    print(f"道路数据文件: {road_file.exists()} - {road_file}")
    
    if not poi_file.exists() or not road_file.exists():
        print("❌ 缺少必要的数据文件!")
        return
    
    try:
        # 读取POI数据
        print("\n2. 读取POI数据:")
        poi_gdf = gpd.read_file(poi_file)
        print(f"✅ POI数据读取成功")
        print(f"   - 记录数: {len(poi_gdf)}")
        print(f"   - 坐标系统: {poi_gdf.crs}")
        print(f"   - 几何类型: {poi_gdf.geometry.geom_type.unique()}")
        
        # POI坐标范围
        poi_bounds = poi_gdf.total_bounds
        print(f"   - 坐标范围: [{poi_bounds[0]:.6f}, {poi_bounds[1]:.6f}, {poi_bounds[2]:.6f}, {poi_bounds[3]:.6f}]")
        print(f"   - 经度范围: {poi_bounds[0]:.6f} ~ {poi_bounds[2]:.6f}")
        print(f"   - 纬度范围: {poi_bounds[1]:.6f} ~ {poi_bounds[3]:.6f}")
        
        # 显示前几个POI的坐标
        print(f"   - 前3个POI坐标:")
        for i in range(min(3, len(poi_gdf))):
            geom = poi_gdf.iloc[i].geometry
            if hasattr(geom, 'x') and hasattr(geom, 'y'):
                print(f"     POI {i+1}: ({geom.x:.6f}, {geom.y:.6f})")
        
    except Exception as e:
        print(f"❌ POI数据读取失败: {e}")
        return
    
    try:
        # 读取道路数据
        print("\n3. 读取道路数据:")
        road_gdf = gpd.read_file(road_file)
        print(f"✅ 道路数据读取成功")
        print(f"   - 记录数: {len(road_gdf)}")
        print(f"   - 坐标系统: {road_gdf.crs}")
        print(f"   - 几何类型: {road_gdf.geometry.geom_type.unique()}")
        
        # 道路坐标范围
        road_bounds = road_gdf.total_bounds
        print(f"   - 坐标范围: [{road_bounds[0]:.6f}, {road_bounds[1]:.6f}, {road_bounds[2]:.6f}, {road_bounds[3]:.6f}]")
        print(f"   - 经度范围: {road_bounds[0]:.6f} ~ {road_bounds[2]:.6f}")
        print(f"   - 纬度范围: {road_bounds[1]:.6f} ~ {road_bounds[3]:.6f}")
        
        # 显示前几个道路的坐标
        print(f"   - 前3个道路坐标:")
        for i in range(min(3, len(road_gdf))):
            geom = road_gdf.iloc[i].geometry
            if hasattr(geom, 'coords'):
                coords = list(geom.coords)
                if coords:
                    print(f"     道路 {i+1}: 起点({coords[0][0]:.6f}, {coords[0][1]:.6f}) 终点({coords[-1][0]:.6f}, {coords[-1][1]:.6f})")
        
    except Exception as e:
        print(f"❌ 道路数据读取失败: {e}")
        return
    
    # 坐标系统比较
    print("\n4. 坐标系统比较:")
    if poi_gdf.crs == road_gdf.crs:
        print(f"✅ 坐标系统一致: {poi_gdf.crs}")
    else:
        print(f"❌ 坐标系统不一致!")
        print(f"   POI坐标系统: {poi_gdf.crs}")
        print(f"   道路坐标系统: {road_gdf.crs}")
    
    # 坐标范围比较
    print("\n5. 坐标范围比较:")
    poi_center_lon = (poi_bounds[0] + poi_bounds[2]) / 2
    poi_center_lat = (poi_bounds[1] + poi_bounds[3]) / 2
    road_center_lon = (road_bounds[0] + road_bounds[2]) / 2
    road_center_lat = (road_bounds[1] + road_bounds[3]) / 2
    
    print(f"   POI中心点: ({poi_center_lon:.6f}, {poi_center_lat:.6f})")
    print(f"   道路中心点: ({road_center_lon:.6f}, {road_center_lat:.6f})")
    
    # 计算中心点距离
    lon_diff = abs(poi_center_lon - road_center_lon)
    lat_diff = abs(poi_center_lat - road_center_lat)
    
    print(f"   中心点差异: 经度差 {lon_diff:.6f}, 纬度差 {lat_diff:.6f}")
    
    # 判断坐标是否在合理范围内（武汉地区）
    # 武汉大致坐标范围: 经度 113.68-115.05, 纬度 29.97-31.35
    wuhan_lon_range = (113.68, 115.05)
    wuhan_lat_range = (29.97, 31.35)
    
    poi_in_wuhan = (wuhan_lon_range[0] <= poi_center_lon <= wuhan_lon_range[1] and 
                    wuhan_lat_range[0] <= poi_center_lat <= wuhan_lat_range[1])
    road_in_wuhan = (wuhan_lon_range[0] <= road_center_lon <= wuhan_lon_range[1] and 
                     wuhan_lat_range[0] <= road_center_lat <= wuhan_lat_range[1])
    
    print(f"\n6. 地理位置合理性检查:")
    print(f"   POI数据在武汉范围内: {'✅' if poi_in_wuhan else '❌'}")
    print(f"   道路数据在武汉范围内: {'✅' if road_in_wuhan else '❌'}")
    
    # 检查是否有空几何
    print(f"\n7. 数据质量检查:")
    poi_empty = poi_gdf.geometry.is_empty.sum()
    road_empty = road_gdf.geometry.is_empty.sum()
    poi_null = poi_gdf.geometry.isnull().sum()
    road_null = road_gdf.geometry.isnull().sum()
    
    print(f"   POI空几何数量: {poi_empty}")
    print(f"   POI空值数量: {poi_null}")
    print(f"   道路空几何数量: {road_empty}")
    print(f"   道路空值数量: {road_null}")
    
    # 总结问题
    print(f"\n8. 问题总结:")
    issues = []
    
    if poi_gdf.crs != road_gdf.crs:
        issues.append("坐标系统不一致")
    
    if not poi_in_wuhan:
        issues.append("POI数据不在武汉地理范围内")
    
    if not road_in_wuhan:
        issues.append("道路数据不在武汉地理范围内")
    
    if lon_diff > 0.1 or lat_diff > 0.1:
        issues.append("POI和道路数据中心点相距过远")
    
    if poi_empty > 0 or road_empty > 0 or poi_null > 0 or road_null > 0:
        issues.append("存在空几何或空值数据")
    
    if issues:
        print("   发现的问题:")
        for issue in issues:
            print(f"   ❌ {issue}")
    else:
        print("   ✅ 未发现明显问题")
    
    return {
        'poi_gdf': poi_gdf,
        'road_gdf': road_gdf,
        'issues': issues,
        'poi_in_wuhan': poi_in_wuhan,
        'road_in_wuhan': road_in_wuhan
    }

if __name__ == "__main__":
    result = diagnose_wuhan_data()