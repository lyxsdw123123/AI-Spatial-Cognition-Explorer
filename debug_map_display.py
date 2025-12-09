#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试地图显示问题
"""

from frontend.local_data_loader import load_local_shapefile_data
import json

def debug_map_display():
    print("=== 调试长沙地图显示问题 ===")
    
    # 加载长沙数据
    changsha_result = load_local_shapefile_data('长沙五一广场')
    print(f"长沙POI数量: {len(changsha_result['pois'])}")
    print(f"长沙道路数量: {len(changsha_result['roads'])}")
    
    # 检查POI数据格式
    if changsha_result['pois']:
        print("\n长沙POI数据示例:")
        poi = changsha_result['pois'][0]
        print(f"  POI结构: {poi}")
        print(f"  位置格式: {poi['location']}")
        print(f"  位置类型: {type(poi['location'])}")
    
    # 检查道路数据格式
    if changsha_result['roads']:
        print("\n长沙道路数据示例:")
        road = changsha_result['roads'][0]
        print(f"  道路名称: {road['name']}")
        print(f"  坐标点数: {len(road['coordinates'])}")
        print(f"  第一个坐标: {road['coordinates'][0]}")
        print(f"  坐标格式: {type(road['coordinates'][0])}")
    
    print("\n=== 调试武汉地图显示问题 ===")
    
    # 加载武汉数据
    wuhan_result = load_local_shapefile_data('武汉黄鹤楼')
    print(f"武汉POI数量: {len(wuhan_result['pois'])}")
    print(f"武汉道路数量: {len(wuhan_result['roads'])}")
    
    # 检查POI数据格式
    if wuhan_result['pois']:
        print("\n武汉POI数据示例:")
        poi = wuhan_result['pois'][0]
        print(f"  POI结构: {poi}")
        print(f"  位置格式: {poi['location']}")
        print(f"  位置类型: {type(poi['location'])}")
    
    # 检查道路数据格式
    if wuhan_result['roads']:
        print("\n武汉道路数据示例:")
        road = wuhan_result['roads'][0]
        print(f"  道路名称: {road['name']}")
        print(f"  坐标点数: {len(road['coordinates'])}")
        print(f"  第一个坐标: {road['coordinates'][0]}")
        print(f"  坐标格式: {type(road['coordinates'][0])}")
        
        # 检查坐标范围
        if road['coordinates']:
            lats = [coord[0] for coord in road['coordinates']]
            lngs = [coord[1] for coord in road['coordinates']]
            print(f"  纬度范围: {min(lats):.6f} ~ {max(lats):.6f}")
            print(f"  经度范围: {min(lngs):.6f} ~ {max(lngs):.6f}")
    
    # 比较北京数据作为参考
    print("\n=== 参考：北京数据格式 ===")
    beijing_result = load_local_shapefile_data('北京天安门')
    
    if beijing_result['pois']:
        print("\n北京POI数据示例:")
        poi = beijing_result['pois'][0]
        print(f"  POI结构: {poi}")
        print(f"  位置格式: {poi['location']}")
    
    if beijing_result['roads']:
        print("\n北京道路数据示例:")
        road = beijing_result['roads'][0]
        print(f"  道路名称: {road['name']}")
        print(f"  坐标点数: {len(road['coordinates'])}")
        print(f"  第一个坐标: {road['coordinates'][0]}")
        
        # 检查坐标范围
        if road['coordinates']:
            lats = [coord[0] for coord in road['coordinates']]
            lngs = [coord[1] for coord in road['coordinates']]
            print(f"  纬度范围: {min(lats):.6f} ~ {max(lats):.6f}")
            print(f"  经度范围: {min(lngs):.6f} ~ {max(lngs):.6f}")

if __name__ == "__main__":
    debug_map_display()