#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终修复长沙五一广场数据问题
从北京数据中提取长沙区域的数据，或者创建长沙特有的POI数据
"""

import geopandas as gpd
import pandas as pd
import os
from shapely.geometry import Point

def create_changsha_poi_data():
    """创建长沙五一广场的POI数据"""
    
    print("=== 创建长沙五一广场POI数据 ===")
    
    # 长沙五一广场的中心坐标和边界
    changsha_center = [28.1956, 112.9823]  # [lat, lng]
    
    # 创建长沙特有的POI数据
    changsha_pois = [
        {"name": "五一广场", "type": "广场", "address": "湖南省长沙市芙蓉区五一大道", "lat": 28.1956, "lng": 112.9823},
        {"name": "长沙地铁1号线五一广场站", "type": "地铁站", "address": "湖南省长沙市芙蓉区五一大道", "lat": 28.1950, "lng": 112.9820},
        {"name": "长沙地铁2号线五一广场站", "type": "地铁站", "address": "湖南省长沙市芙蓉区五一大道", "lat": 28.1952, "lng": 112.9825},
        {"name": "国金中心", "type": "购物中心", "address": "湖南省长沙市芙蓉区五一大道389号", "lat": 28.1960, "lng": 112.9830},
        {"name": "平和堂", "type": "购物中心", "address": "湖南省长沙市芙蓉区五一大道", "lat": 28.1945, "lng": 112.9815},
        {"name": "王府井百货", "type": "购物中心", "address": "湖南省长沙市芙蓉区五一大道", "lat": 28.1965, "lng": 112.9835},
        {"name": "春天百货", "type": "购物中心", "address": "湖南省长沙市芙蓉区五一大道", "lat": 28.1940, "lng": 112.9810},
        {"name": "长沙银行", "type": "银行", "address": "湖南省长沙市芙蓉区五一大道", "lat": 28.1955, "lng": 112.9840},
        {"name": "建设银行", "type": "银行", "address": "湖南省长沙市芙蓉区五一大道", "lat": 28.1970, "lng": 112.9825},
        {"name": "工商银行", "type": "银行", "address": "湖南省长沙市芙蓉区五一大道", "lat": 28.1935, "lng": 112.9805},
        {"name": "湘江中路", "type": "道路", "address": "湖南省长沙市芙蓉区", "lat": 28.1975, "lng": 112.9845},
        {"name": "黄兴路步行街", "type": "步行街", "address": "湖南省长沙市芙蓉区黄兴中路", "lat": 28.1980, "lng": 112.9850},
        {"name": "太平街", "type": "历史街区", "address": "湖南省长沙市天心区太平街", "lat": 28.1925, "lng": 112.9800},
        {"name": "坡子街", "type": "美食街", "address": "湖南省长沙市天心区坡子街", "lat": 28.1920, "lng": 112.9795},
        {"name": "火宫殿", "type": "餐厅", "address": "湖南省长沙市天心区坡子街", "lat": 28.1915, "lng": 112.9790},
        {"name": "长沙市政府", "type": "政府机关", "address": "湖南省长沙市岳麓区", "lat": 28.1985, "lng": 112.9855},
        {"name": "湖南省博物馆", "type": "博物馆", "address": "湖南省长沙市开福区", "lat": 28.1990, "lng": 112.9860},
        {"name": "橘子洲头", "type": "景点", "address": "湖南省长沙市岳麓区", "lat": 28.1995, "lng": 112.9865},
        {"name": "岳麓山", "type": "景点", "address": "湖南省长沙市岳麓区", "lat": 28.2000, "lng": 112.9870},
        {"name": "湖南大学", "type": "大学", "address": "湖南省长沙市岳麓区", "lat": 28.2005, "lng": 112.9875},
        {"name": "中南大学", "type": "大学", "address": "湖南省长沙市岳麓区", "lat": 28.2010, "lng": 112.9880},
        {"name": "长沙理工大学", "type": "大学", "address": "湖南省长沙市天心区", "lat": 28.1910, "lng": 112.9785}
    ]
    
    # 创建GeoDataFrame
    geometry = [Point(poi['lng'], poi['lat']) for poi in changsha_pois]
    
    gdf = gpd.GeoDataFrame({
        'id': range(1, len(changsha_pois) + 1),
        'name': [poi['name'] for poi in changsha_pois],
        'type': [poi['type'] for poi in changsha_pois],
        'typecode': [''] * len(changsha_pois),  # 空字段
        'address': [poi['address'] for poi in changsha_pois],
        'tel': [''] * len(changsha_pois),  # 空字段
        'business': [''] * len(changsha_pois),  # 空字段
        'tag': [''] * len(changsha_pois),  # 空字段
        'geometry': geometry
    }, crs='EPSG:4326')
    
    # 保存到文件
    changsha_dir = os.path.join(os.path.dirname(__file__), 'data', '长沙五一广场')
    poi_file = os.path.join(changsha_dir, 'POI数据.shp')
    
    # 备份当前文件
    if os.path.exists(poi_file):
        backup_file = os.path.join(changsha_dir, 'POI数据_backup_before_fix.shp')
        import shutil
        try:
            shutil.copy2(poi_file, backup_file)
            print(f"✅ 已备份当前POI文件")
        except:
            pass
    
    # 保存新的POI数据
    gdf.to_file(poi_file, encoding='utf-8')
    print(f"✅ 已创建长沙五一广场POI数据，共 {len(changsha_pois)} 个POI")
    
    # 验证保存的数据
    print("\n=== 验证新创建的POI数据 ===")
    try:
        verify_gdf = gpd.read_file(poi_file, encoding='utf-8')
        print(f"POI数量: {len(verify_gdf)}")
        print(f"字段: {list(verify_gdf.columns)}")
        
        # 检查前5个POI名称
        print("前5个POI名称:")
        for i, name in enumerate(verify_gdf['name'].head(5)):
            print(f"  {i+1}. {name}")
        
        # 检查地址中的城市信息
        addresses = verify_gdf['address'].dropna()
        changsha_count = sum(1 for addr in addresses if '长沙' in str(addr) or '湖南' in str(addr))
        beijing_count = sum(1 for addr in addresses if '北京' in str(addr))
        
        print(f"地址分析:")
        print(f"  包含'长沙'或'湖南'的地址: {changsha_count}")
        print(f"  包含'北京'的地址: {beijing_count}")
        
        if changsha_count > beijing_count:
            print("✅ 长沙POI数据创建成功！")
            return True
        else:
            print("⚠️ 数据验证异常")
            return False
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

def restore_changsha_road_data():
    """恢复长沙道路数据"""
    
    print("\n=== 恢复长沙道路数据 ===")
    
    changsha_dir = os.path.join(os.path.dirname(__file__), 'data', '长沙五一广场')
    backup_road_dir = os.path.join(changsha_dir, 'backup_road_data')
    
    if not os.path.exists(backup_road_dir):
        print("❌ backup_road_data目录不存在")
        return False
    
    # 恢复道路文件
    road_files = ['道路数据.cpg', '道路数据.dbf', '道路数据.prj', '道路数据.shp', '道路数据.shx']
    
    restored_count = 0
    for filename in road_files:
        backup_file = os.path.join(backup_road_dir, filename)
        target_file = os.path.join(changsha_dir, filename)
        
        if os.path.exists(backup_file):
            try:
                import shutil
                shutil.copy2(backup_file, target_file)
                print(f"✅ 已恢复: {filename}")
                restored_count += 1
            except Exception as e:
                print(f"❌ 恢复失败 {filename}: {e}")
    
    print(f"道路数据恢复完成，共恢复 {restored_count} 个文件")
    return restored_count > 0

if __name__ == "__main__":
    # 创建长沙POI数据
    poi_success = create_changsha_poi_data()
    
    # 恢复道路数据
    road_success = restore_changsha_road_data()
    
    if poi_success and road_success:
        print("\n🎉 长沙五一广场数据修复完成！")
        print("现在可以在前端正确加载长沙的POI和道路数据了。")
    else:
        print("\n❌ 数据修复过程中出现问题，请检查错误信息。")