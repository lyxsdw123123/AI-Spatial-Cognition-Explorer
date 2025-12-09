#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查道路坐标数据
"""

import geopandas as gpd
import os

def check_road_coordinates():
    print("=== 检查道路坐标数据 ===")
    
    # 设置环境变量
    os.environ['SHAPE_RESTORE_SHX'] = 'YES'
    
    regions = ['长沙五一广场', '武汉黄鹤楼', '北京天安门']
    
    for region in regions:
        print(f"\n--- {region} ---")
        road_path = f"data/{region}/道路数据.shp"
        
        try:
            roads_gdf = gpd.read_file(road_path)
            print(f"道路数量: {len(roads_gdf)}")
            
            # 检查几何数据
            if len(roads_gdf) > 0:
                first_road = roads_gdf.iloc[0]
                geom = first_road.geometry
                
                if hasattr(geom, 'coords'):
                    coords = list(geom.coords)
                    print(f"第一条道路坐标: {coords[:2]}")  # 只显示前两个点
                    
                    # 计算坐标范围
                    all_coords = []
                    for _, row in roads_gdf.iterrows():
                        if hasattr(row.geometry, 'coords'):
                            all_coords.extend(list(row.geometry.coords))
                    
                    if all_coords:
                        lngs = [coord[0] for coord in all_coords]
                        lats = [coord[1] for coord in all_coords]
                        print(f"经度范围: {min(lngs):.6f} ~ {max(lngs):.6f}")
                        print(f"纬度范围: {min(lats):.6f} ~ {max(lats):.6f}")
                        
                        # 判断坐标系统
                        if min(lngs) > 100 and max(lngs) < 130 and min(lats) > 20 and max(lats) < 50:
                            print("✓ 坐标看起来是中国境内的经纬度")
                        else:
                            print("✗ 坐标可能不正确或不是标准经纬度")
                
        except Exception as e:
            print(f"读取失败: {e}")

if __name__ == "__main__":
    check_road_coordinates()