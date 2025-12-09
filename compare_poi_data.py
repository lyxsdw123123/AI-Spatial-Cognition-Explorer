#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比较长沙、武汉和北京的POI数据，检查是否存在数据混淆问题
"""

import geopandas as gpd
import os

def compare_poi_data():
    """比较三个城市的POI数据"""
    
    regions = ["长沙五一广场", "武汉黄鹤楼", "北京天安门"]
    
    for region in regions:
        print(f"\n=== {region} POI数据分析 ===")
        
        data_dir = os.path.join(os.path.dirname(__file__), 'data', region)
        poi_file = os.path.join(data_dir, 'POI数据.shp')
        
        if os.path.exists(poi_file):
            try:
                poi_gdf = gpd.read_file(poi_file, encoding='utf-8')
                print(f"POI数量: {len(poi_gdf)}")
                print(f"字段: {list(poi_gdf.columns)}")
                
                # 显示前5个POI的名称和地址
                if 'name' in poi_gdf.columns:
                    print("前5个POI名称:")
                    for i, name in enumerate(poi_gdf['name'].head(5)):
                        print(f"  {i+1}. {name}")
                
                if 'address' in poi_gdf.columns:
                    print("前5个POI地址:")
                    for i, addr in enumerate(poi_gdf['address'].head(5)):
                        print(f"  {i+1}. {addr}")
                
                # 检查坐标范围
                bounds = poi_gdf.bounds
                print(f"坐标范围:")
                print(f"  经度: {bounds['minx'].min():.6f} ~ {bounds['maxx'].max():.6f}")
                print(f"  纬度: {bounds['miny'].min():.6f} ~ {bounds['maxy'].max():.6f}")
                
                # 分析地址中的城市信息
                if 'address' in poi_gdf.columns:
                    addresses = poi_gdf['address'].dropna()
                    beijing_count = sum(1 for addr in addresses if '北京' in str(addr))
                    changsha_count = sum(1 for addr in addresses if '长沙' in str(addr) or '湖南' in str(addr))
                    wuhan_count = sum(1 for addr in addresses if '武汉' in str(addr) or '湖北' in str(addr))
                    
                    print(f"地址分析:")
                    print(f"  包含'北京'的地址: {beijing_count}")
                    print(f"  包含'长沙'或'湖南'的地址: {changsha_count}")
                    print(f"  包含'武汉'或'湖北'的地址: {wuhan_count}")
                    
                    # 如果发现数据不匹配的情况
                    if region == "长沙五一广场" and beijing_count > changsha_count:
                        print("⚠️ 警告：长沙数据中北京地址数量异常多！")
                    elif region == "武汉黄鹤楼" and beijing_count > wuhan_count:
                        print("⚠️ 警告：武汉数据中北京地址数量异常多！")
                    elif region == "北京天安门" and (changsha_count > 0 or wuhan_count > 0):
                        print("⚠️ 警告：北京数据中包含其他城市地址！")
                
            except Exception as e:
                print(f"读取失败: {e}")
        else:
            print("POI文件不存在")

if __name__ == "__main__":
    compare_poi_data()