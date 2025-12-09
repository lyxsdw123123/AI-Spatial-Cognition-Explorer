#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查武汉黄鹤楼道路数据的字段结构
"""

import geopandas as gpd
import pandas as pd
from pathlib import Path

def check_wuhan_road_fields():
    """检查武汉黄鹤楼道路数据的字段结构"""
    
    print("=" * 60)
    print("武汉黄鹤楼道路数据字段结构检查")
    print("=" * 60)
    
    # 数据文件路径
    wuhan_road_file = Path("data/武汉黄鹤楼/道路数据.shp")
    
    if not wuhan_road_file.exists():
        print(f"❌ 道路数据文件不存在: {wuhan_road_file}")
        return
    
    try:
        # 读取道路数据
        road_gdf = gpd.read_file(wuhan_road_file)
        print(f"✅ 成功读取道路数据，共 {len(road_gdf)} 条道路")
        
        # 检查字段结构
        print(f"\n1. 字段列表:")
        for i, col in enumerate(road_gdf.columns):
            print(f"   {i+1}. {col} ({road_gdf[col].dtype})")
        
        # 检查name字段
        print(f"\n2. name字段检查:")
        if 'name' in road_gdf.columns:
            print(f"   ✅ name字段存在")
            print(f"   - 数据类型: {road_gdf['name'].dtype}")
            print(f"   - 非空值数量: {road_gdf['name'].notna().sum()}")
            print(f"   - 空值数量: {road_gdf['name'].isna().sum()}")
            
            # 显示前几个name值
            print(f"   - 前10个name值:")
            for i, name in enumerate(road_gdf['name'].head(10)):
                print(f"     {i+1}. {name}")
        else:
            print(f"   ❌ name字段不存在")
            
            # 查找可能的名称字段
            possible_name_fields = []
            for col in road_gdf.columns:
                if any(keyword in col.lower() for keyword in ['name', '名称', 'road', '道路', 'street', '街道']):
                    possible_name_fields.append(col)
            
            if possible_name_fields:
                print(f"   可能的名称字段: {possible_name_fields}")
                for field in possible_name_fields:
                    print(f"   - {field}: {road_gdf[field].head(3).tolist()}")
            else:
                print(f"   未找到可能的名称字段")
        
        # 检查几何数据
        print(f"\n3. 几何数据检查:")
        print(f"   - 几何类型: {road_gdf.geometry.geom_type.unique()}")
        print(f"   - 空几何数量: {road_gdf.geometry.is_empty.sum()}")
        print(f"   - 空值几何数量: {road_gdf.geometry.isnull().sum()}")
        
        # 显示前几条道路的详细信息
        print(f"\n4. 前3条道路详细信息:")
        for i in range(min(3, len(road_gdf))):
            row = road_gdf.iloc[i]
            print(f"   道路 {i+1}:")
            print(f"     - 几何类型: {row.geometry.geom_type}")
            if hasattr(row.geometry, 'coords'):
                coords = list(row.geometry.coords)
                print(f"     - 坐标点数: {len(coords)}")
                if coords:
                    print(f"     - 起点: ({coords[0][0]:.6f}, {coords[0][1]:.6f})")
                    print(f"     - 终点: ({coords[-1][0]:.6f}, {coords[-1][1]:.6f})")
            
            # 显示所有字段值
            for col in road_gdf.columns:
                if col != 'geometry':
                    print(f"     - {col}: {row[col]}")
        
        # 与长沙和北京数据对比
        print(f"\n5. 与其他城市数据对比:")
        
        # 检查长沙数据
        changsha_road_file = Path("data/长沙五一广场/道路数据.shp")
        if changsha_road_file.exists():
            try:
                changsha_gdf = gpd.read_file(changsha_road_file)
                print(f"   长沙道路数据字段: {list(changsha_gdf.columns)}")
                if 'name' in changsha_gdf.columns:
                    print(f"   长沙name字段示例: {changsha_gdf['name'].head(3).tolist()}")
            except Exception as e:
                print(f"   长沙数据读取失败: {e}")
        
        # 检查北京数据
        beijing_road_file = Path("data/北京天安门/道路数据.shp")
        if beijing_road_file.exists():
            try:
                beijing_gdf = gpd.read_file(beijing_road_file)
                print(f"   北京道路数据字段: {list(beijing_gdf.columns)}")
                if 'name' in beijing_gdf.columns:
                    print(f"   北京name字段示例: {beijing_gdf['name'].head(3).tolist()}")
            except Exception as e:
                print(f"   北京数据读取失败: {e}")
        
        return road_gdf
        
    except Exception as e:
        print(f"❌ 读取道路数据失败: {e}")
        return None

if __name__ == "__main__":
    result = check_wuhan_road_fields()