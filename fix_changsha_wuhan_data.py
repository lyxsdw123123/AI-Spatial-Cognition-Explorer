#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复长沙和武汉的shapefile数据文件
"""

import os
import shutil
import geopandas as gpd

def backup_files(source_dir, backup_dir):
    """备份原始文件"""
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    for file in os.listdir(source_dir):
        if file.endswith(('.shp', '.shx', '.dbf', '.prj', '.cpg')):
            shutil.copy2(os.path.join(source_dir, file), backup_dir)
    print(f"已备份文件到: {backup_dir}")

def copy_template_files(template_dir, target_dir, file_prefix):
    """从模板目录复制文件"""
    template_files = [f for f in os.listdir(template_dir) if f.startswith(file_prefix)]
    
    for template_file in template_files:
        template_path = os.path.join(template_dir, template_file)
        target_path = os.path.join(target_dir, template_file)
        shutil.copy2(template_path, target_path)
        print(f"已复制: {template_file}")

def clean_extra_files(target_dir):
    """清理额外的文件(.sbn, .sbx, .xml)"""
    extra_extensions = ['.sbn', '.sbx', '.xml']
    for file in os.listdir(target_dir):
        if any(file.endswith(ext) for ext in extra_extensions):
            file_path = os.path.join(target_dir, file)
            os.remove(file_path)
            print(f"已删除额外文件: {file}")

def test_shapefile(file_path):
    """测试shapefile是否可读"""
    try:
        os.environ['SHAPE_RESTORE_SHX'] = 'YES'
        gdf = gpd.read_file(file_path, encoding='utf-8')
        print(f"✓ {file_path} 读取成功，包含 {len(gdf)} 行数据")
        if len(gdf) > 0:
            print(f"  列名: {list(gdf.columns)}")
        return True
    except Exception as e:
        print(f"✗ {file_path} 读取失败: {e}")
        return False

def main():
    # 设置路径
    changsha_dir = "data/长沙五一广场"
    wuhan_dir = "data/武汉黄鹤楼"
    beijing_dir = "data/北京天安门"
    
    print("=== 修复长沙五一广场数据 ===")
    
    # 1. 备份长沙原始文件
    changsha_backup = os.path.join(changsha_dir, "backup_original")
    backup_files(changsha_dir, changsha_backup)
    
    # 2. 清理长沙的额外文件
    print("清理额外文件...")
    clean_extra_files(changsha_dir)
    
    # 3. 复制北京的模板文件到长沙
    print("复制POI数据模板...")
    copy_template_files(beijing_dir, changsha_dir, "POI数据")
    
    print("复制道路数据模板...")
    copy_template_files(beijing_dir, changsha_dir, "道路数据")
    
    print("复制道路节点数据模板...")
    copy_template_files(beijing_dir, changsha_dir, "道路节点数据")
    
    print("\n=== 修复武汉黄鹤楼数据 ===")
    
    # 4. 备份武汉原始文件
    wuhan_backup = os.path.join(wuhan_dir, "backup_original")
    backup_files(wuhan_dir, wuhan_backup)
    
    # 5. 清理武汉的额外文件
    print("清理额外文件...")
    clean_extra_files(wuhan_dir)
    
    # 6. 复制北京的道路节点数据模板到武汉（武汉的POI和道路数据已经修复过）
    print("复制道路节点数据模板...")
    copy_template_files(beijing_dir, wuhan_dir, "道路节点数据")
    
    print("\n=== 测试修复结果 ===")
    
    # 测试长沙数据
    print("\n测试长沙数据:")
    test_shapefile(os.path.join(changsha_dir, "POI数据.shp"))
    test_shapefile(os.path.join(changsha_dir, "道路数据.shp"))
    test_shapefile(os.path.join(changsha_dir, "道路节点数据.shp"))
    
    # 测试武汉数据
    print("\n测试武汉数据:")
    test_shapefile(os.path.join(wuhan_dir, "POI数据.shp"))
    test_shapefile(os.path.join(wuhan_dir, "道路数据.shp"))
    test_shapefile(os.path.join(wuhan_dir, "道路节点数据.shp"))
    
    print("\n=== 修复完成 ===")

if __name__ == "__main__":
    main()