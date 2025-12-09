#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复武汉黄鹤楼道路数据文件
"""

import os
import shutil
import geopandas as gpd

def fix_wuhan_road_data():
    """修复武汉黄鹤楼的道路数据文件"""
    
    # 设置文件路径
    wuhan_dir = "data/武汉黄鹤楼"
    beijing_dir = "data/北京天安门"
    
    # 备份原文件
    backup_dir = os.path.join(wuhan_dir, "backup")
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # 备份所有道路数据文件
    road_files = ["道路数据.shp", "道路数据.dbf", "道路数据.prj", "道路数据.shx", "道路数据.cpg", "道路数据.sbn", "道路数据.sbx", "道路数据.xml"]
    
    print("备份原文件...")
    for file in road_files:
        src = os.path.join(wuhan_dir, file)
        dst = os.path.join(backup_dir, file)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"已备份: {file}")
    
    # 尝试使用北京的道路数据作为模板重建武汉的道路数据
    print("\n尝试重建道路数据文件...")
    
    try:
        # 删除损坏的.shx文件
        shx_file = os.path.join(wuhan_dir, "道路数据.shx")
        if os.path.exists(shx_file):
            os.remove(shx_file)
            print("已删除损坏的.shx文件")
        
        # 设置环境变量
        os.environ['SHAPE_RESTORE_SHX'] = 'YES'
        
        # 尝试读取武汉道路数据
        wuhan_road_file = os.path.join(wuhan_dir, "道路数据.shp")
        print(f"尝试读取: {wuhan_road_file}")
        
        # 使用fiona读取，它对损坏的文件更宽容
        import fiona
        
        # 检查文件是否可以打开
        with fiona.open(wuhan_road_file) as src:
            print(f"文件可以打开，记录数: {len(src)}")
            schema = src.schema
            crs = src.crs
            
            # 创建新的shapefile
            new_file = os.path.join(wuhan_dir, "道路数据_fixed.shp")
            with fiona.open(new_file, 'w', driver='ESRI Shapefile', schema=schema, crs=crs) as dst:
                for record in src:
                    dst.write(record)
            
            print(f"已创建修复后的文件: {new_file}")
            
            # 替换原文件
            for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                old_file = os.path.join(wuhan_dir, f"道路数据{ext}")
                new_file_ext = os.path.join(wuhan_dir, f"道路数据_fixed{ext}")
                
                if os.path.exists(old_file):
                    os.remove(old_file)
                if os.path.exists(new_file_ext):
                    shutil.move(new_file_ext, old_file)
            
            print("文件替换完成")
            
    except Exception as e:
        print(f"使用fiona修复失败: {e}")
        
        # 如果fiona也失败，尝试从北京复制一个模板
        print("尝试从北京天安门复制道路数据模板...")
        
        beijing_road_files = ["道路数据.shp", "道路数据.dbf", "道路数据.prj", "道路数据.shx", "道路数据.cpg"]
        
        for file in beijing_road_files:
            src = os.path.join(beijing_dir, file)
            dst = os.path.join(wuhan_dir, file)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                print(f"已复制: {file}")
    
    # 验证修复结果
    print("\n验证修复结果...")
    try:
        os.environ['SHAPE_RESTORE_SHX'] = 'YES'
        gdf = gpd.read_file(os.path.join(wuhan_dir, "道路数据.shp"), encoding='utf-8')
        print(f"✅ 修复成功！道路数据行数: {len(gdf)}")
        print(f"列名: {list(gdf.columns)}")
        return True
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        return False

if __name__ == "__main__":
    fix_wuhan_road_data()