#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从backup_poi_data恢复长沙五一广场的POI数据
"""

import shutil
import os
import geopandas as gpd

def restore_changsha_poi():
    """从backup_poi_data恢复长沙五一广场的POI数据"""
    
    print("=== 从backup_poi_data恢复长沙五一广场POI数据 ===")
    
    # 数据目录
    changsha_dir = os.path.join(os.path.dirname(__file__), 'data', '长沙五一广场')
    backup_poi_dir = os.path.join(changsha_dir, 'backup_poi_data')
    
    # 检查备份目录是否存在
    if not os.path.exists(backup_poi_dir):
        print("❌ backup_poi_data目录不存在")
        return False
    
    # 要恢复的POI文件列表
    poi_files = [
        'POI数据.cpg', 'POI数据.dbf', 'POI数据.prj', 'POI数据.shp', 'POI数据.shx',
        'POI数据.sbn', 'POI数据.sbx'  # 包含索引文件
    ]
    
    # 恢复POI文件
    restored_count = 0
    for filename in poi_files:
        backup_file = os.path.join(backup_poi_dir, filename)
        target_file = os.path.join(changsha_dir, filename)
        
        if os.path.exists(backup_file):
            try:
                shutil.copy2(backup_file, target_file)
                print(f"✅ 已恢复: {filename}")
                restored_count += 1
            except Exception as e:
                print(f"❌ 恢复失败 {filename}: {e}")
        else:
            print(f"⚠️ 备份文件不存在: {filename}")
    
    print(f"\n恢复完成，共恢复 {restored_count} 个POI文件")
    
    # 验证恢复后的POI数据
    print("\n=== 验证恢复后的POI数据 ===")
    poi_file = os.path.join(changsha_dir, 'POI数据.shp')
    
    if os.path.exists(poi_file):
        try:
            poi_gdf = gpd.read_file(poi_file, encoding='utf-8')
            print(f"POI数量: {len(poi_gdf)}")
            print(f"字段: {list(poi_gdf.columns)}")
            
            # 检查前5个POI名称
            if 'name' in poi_gdf.columns:
                print("前5个POI名称:")
                for i, name in enumerate(poi_gdf['name'].head(5)):
                    print(f"  {i+1}. {name}")
            
            # 检查地址中的城市信息
            if 'address' in poi_gdf.columns:
                addresses = poi_gdf['address'].dropna()
                beijing_count = sum(1 for addr in addresses if '北京' in str(addr))
                changsha_count = sum(1 for addr in addresses if '长沙' in str(addr) or '湖南' in str(addr))
                
                print(f"地址分析:")
                print(f"  包含'北京'的地址: {beijing_count}")
                print(f"  包含'长沙'或'湖南'的地址: {changsha_count}")
                
                if beijing_count > changsha_count:
                    print("⚠️ 警告：POI数据仍然存在问题")
                    return False
                else:
                    print("✅ POI数据验证通过")
                    return True
            else:
                print("✅ POI数据已恢复，但无address字段")
                return True
            
        except Exception as e:
            print(f"❌ 验证失败: {e}")
            return False
    else:
        print("❌ POI文件不存在")
        return False

if __name__ == "__main__":
    restore_changsha_poi()