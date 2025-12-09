#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看北京天安门区域道路节点数据的详细信息
"""

import os
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

def check_road_nodes_data():
    """检查道路节点数据的详细信息"""
    
    # 道路节点数据文件路径
    road_nodes_file = "data/北京天安门/道路节点数据.shp"
    
    print("=" * 80)
    print("🗺️ 北京天安门区域道路节点数据分析")
    print("=" * 80)
    
    # 检查文件是否存在
    if not os.path.exists(road_nodes_file):
        print(f"❌ 道路节点数据文件不存在: {road_nodes_file}")
        return
    
    try:
        # 设置环境变量以修复shapefile索引文件
        os.environ['SHAPE_RESTORE_SHX'] = 'YES'
        
        # 读取道路节点数据
        print(f"📂 正在读取文件: {road_nodes_file}")
        road_nodes_gdf = gpd.read_file(road_nodes_file, encoding='utf-8')
        
        print(f"✅ 文件读取成功!")
        print()
        
        # 1. 显示基本统计信息
        print("📊 基本统计信息:")
        print(f"   节点总数: {len(road_nodes_gdf)}")
        print(f"   坐标系统: {road_nodes_gdf.crs}")
        print()
        
        # 2. 显示所有字段名称和数据类型
        print("📋 字段信息:")
        print("-" * 50)
        for i, (column, dtype) in enumerate(road_nodes_gdf.dtypes.items(), 1):
            if column != 'geometry':
                print(f"   {i:2d}. {column:<20} | {str(dtype)}")
        print(f"   {len(road_nodes_gdf.columns):2d}. {'geometry':<20} | geometry")
        print()
        
        # 3. 显示坐标范围
        print("🌍 坐标范围:")
        print("-" * 50)
        bounds = road_nodes_gdf.bounds
        min_x, min_y = bounds.minx.min(), bounds.miny.min()
        max_x, max_y = bounds.maxx.max(), bounds.maxy.max()
        
        print(f"   经度范围: {min_x:.6f} ~ {max_x:.6f}")
        print(f"   纬度范围: {min_y:.6f} ~ {max_y:.6f}")
        print(f"   中心点: ({(min_x + max_x) / 2:.6f}, {(min_y + max_y) / 2:.6f})")
        print()
        
        # 4. 显示前10个节点的详细信息
        print("🔍 前10个节点详细信息:")
        print("=" * 80)
        
        for idx in range(min(10, len(road_nodes_gdf))):
            node = road_nodes_gdf.iloc[idx]
            print(f"节点 #{idx + 1}:")
            print("-" * 40)
            
            # 显示所有非geometry字段
            for column in road_nodes_gdf.columns:
                if column != 'geometry':
                    value = node[column]
                    if pd.isna(value):
                        value = "NULL"
                    print(f"   {column:<15}: {value}")
            
            # 显示坐标信息
            geometry = node.geometry
            if isinstance(geometry, Point):
                print(f"   {'坐标':<15}: ({geometry.x:.6f}, {geometry.y:.6f})")
            else:
                print(f"   {'几何类型':<15}: {type(geometry).__name__}")
            
            print()
        
        # 5. 显示字段值的统计信息（针对数值字段）
        print("📈 数值字段统计:")
        print("-" * 50)
        numeric_columns = road_nodes_gdf.select_dtypes(include=['number']).columns
        if len(numeric_columns) > 0:
            for col in numeric_columns:
                if col != 'geometry':
                    print(f"   {col}:")
                    print(f"     最小值: {road_nodes_gdf[col].min()}")
                    print(f"     最大值: {road_nodes_gdf[col].max()}")
                    print(f"     平均值: {road_nodes_gdf[col].mean():.2f}")
                    print(f"     非空值: {road_nodes_gdf[col].count()}")
                    print()
        else:
            print("   没有数值字段")
        
        # 6. 显示文本字段的唯一值统计（如果字段值较少）
        print("📝 文本字段统计:")
        print("-" * 50)
        text_columns = road_nodes_gdf.select_dtypes(include=['object']).columns
        for col in text_columns:
            if col != 'geometry':
                unique_count = road_nodes_gdf[col].nunique()
                null_count = road_nodes_gdf[col].isnull().sum()
                print(f"   {col}:")
                print(f"     唯一值数量: {unique_count}")
                print(f"     空值数量: {null_count}")
                
                # 如果唯一值较少，显示所有唯一值
                if unique_count <= 20:
                    unique_values = road_nodes_gdf[col].dropna().unique()
                    print(f"     唯一值: {list(unique_values)}")
                print()
        
        print("=" * 80)
        print("✅ 道路节点数据分析完成!")
        
    except Exception as e:
        print(f"❌ 读取道路节点数据时发生错误: {str(e)}")
        print(f"错误类型: {type(e).__name__}")

if __name__ == "__main__":
    check_road_nodes_data()