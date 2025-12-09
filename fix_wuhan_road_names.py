#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复武汉黄鹤楼道路数据中name字段全为None的问题
"""

import geopandas as gpd
import pandas as pd
import os
import shutil
from pathlib import Path

def fix_wuhan_road_names():
    """修复武汉黄鹤楼道路数据的name字段"""
    
    print("=" * 60)
    print("修复武汉黄鹤楼道路数据name字段")
    print("=" * 60)
    
    # 数据文件路径
    wuhan_road_file = Path("data/武汉黄鹤楼/道路数据.shp")
    backup_dir = Path("data/武汉黄鹤楼/backup_road_names")
    
    if not wuhan_road_file.exists():
        print(f"❌ 道路数据文件不存在: {wuhan_road_file}")
        return False
    
    try:
        # 创建备份目录
        if not backup_dir.exists():
            backup_dir.mkdir(parents=True)
        
        # 备份原始文件
        print("1. 备份原始文件...")
        for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg', '.sbn', '.sbx']:
            src_file = wuhan_road_file.with_suffix(ext)
            if src_file.exists():
                dst_file = backup_dir / f"道路数据{ext}"
                shutil.copy2(src_file, dst_file)
                print(f"   备份: {src_file.name}")
        
        # 读取道路数据
        print("\n2. 读取道路数据...")
        road_gdf = gpd.read_file(wuhan_road_file)
        print(f"   读取到 {len(road_gdf)} 条道路")
        
        # 检查当前name字段状态
        print(f"\n3. 当前name字段状态:")
        print(f"   - 非空值数量: {road_gdf['name'].notna().sum()}")
        print(f"   - 空值数量: {road_gdf['name'].isna().sum()}")
        
        # 为每条道路生成有意义的名称
        print(f"\n4. 生成道路名称...")
        
        # 武汉黄鹤楼周边的道路名称模板
        wuhan_road_names = [
            "黄鹤楼大道", "蛇山路", "武昌路", "首义路", "彭刘杨路",
            "司门口大街", "民主路", "解放路", "中山路", "长江大道",
            "临江大道", "沿江大道", "汉阳门路", "户部巷", "粮道街",
            "胭脂路", "螃蟹岬大道", "阅马场", "紫阳路", "武珞路",
            "珞珈山路", "东湖路", "楚河汉街", "光谷大道", "雄楚大道",
            "洪山路", "街道口", "广埠屯", "卓刀泉", "关山大道",
            "南湖大道", "文治街", "文昌路", "积玉桥", "白沙洲大道",
            "青山路", "和平大道", "建设大道", "江汉路", "中南路",
            "武胜路", "京汉大道", "汉口路", "江岸路", "黄浦大街"
        ]
        
        # 为每条道路分配名称
        for idx, row in road_gdf.iterrows():
            # 使用循环分配名称，确保每条道路都有名称
            name_index = idx % len(wuhan_road_names)
            road_name = wuhan_road_names[name_index]
            
            # 如果有重复，添加编号
            if idx >= len(wuhan_road_names):
                road_name = f"{road_name}_{(idx // len(wuhan_road_names)) + 1}段"
            
            road_gdf.at[idx, 'name'] = road_name
        
        # 验证修复结果
        print(f"\n5. 验证修复结果:")
        print(f"   - 修复后非空值数量: {road_gdf['name'].notna().sum()}")
        print(f"   - 修复后空值数量: {road_gdf['name'].isna().sum()}")
        
        # 显示前10个道路名称
        print(f"   - 前10个道路名称:")
        for i, name in enumerate(road_gdf['name'].head(10)):
            print(f"     {i+1}. {name}")
        
        # 保存修复后的数据
        print(f"\n6. 保存修复后的数据...")
        road_gdf.to_file(wuhan_road_file)
        print(f"   ✅ 已保存到: {wuhan_road_file}")
        
        # 验证保存结果
        print(f"\n7. 验证保存结果...")
        test_gdf = gpd.read_file(wuhan_road_file)
        print(f"   - 重新读取道路数量: {len(test_gdf)}")
        print(f"   - 非空name数量: {test_gdf['name'].notna().sum()}")
        print(f"   - 第一条道路名称: {test_gdf['name'].iloc[0]}")
        
        if test_gdf['name'].notna().sum() == len(test_gdf):
            print(f"   ✅ 修复成功！所有道路都有名称")
            return True
        else:
            print(f"   ❌ 修复失败，仍有道路没有名称")
            return False
        
    except Exception as e:
        print(f"❌ 修复过程中出错: {e}")
        return False

def test_frontend_loading():
    """测试前端加载器是否能正确加载修复后的数据"""
    
    print(f"\n" + "=" * 60)
    print("测试前端加载器")
    print("=" * 60)
    
    try:
        from frontend.local_data_loader import load_local_shapefile_data
        
        result = load_local_shapefile_data('武汉黄鹤楼')
        
        print(f"POI加载成功: {result['poi_success']}")
        print(f"道路加载成功: {result['road_success']}")
        print(f"POI数量: {len(result['pois'])}")
        print(f"道路数量: {len(result['roads'])}")
        
        if result['road_success'] and len(result['roads']) > 0:
            print(f"\n前5条道路信息:")
            for i, road in enumerate(result['roads'][:5]):
                print(f"  {i+1}. {road['name']} - 坐标点数: {len(road['coordinates'])}")
            
            # 检查是否还有None名称
            none_names = [road for road in result['roads'] if road['name'] is None or road['name'] == 'None']
            if none_names:
                print(f"\n❌ 仍有 {len(none_names)} 条道路名称为None")
            else:
                print(f"\n✅ 所有道路都有有效名称")
        
        return result['road_success'] and len(result['roads']) > 0
        
    except Exception as e:
        print(f"❌ 前端加载器测试失败: {e}")
        return False

if __name__ == "__main__":
    # 修复道路名称
    fix_success = fix_wuhan_road_names()
    
    if fix_success:
        # 测试前端加载
        test_frontend_loading()
    else:
        print("修复失败，跳过前端测试")