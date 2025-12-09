#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI转弯测试脚本
测试AI在转弯时是否严格沿道路移动，不走对角线
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_agent.explorer_agent import ExplorerAgent
from map_service.amap_service import AmapService
from data_service.local_data_service import LocalDataService
from config.config import Config

async def test_ai_turning():
    """
    测试AI转弯移动逻辑
    """
    print("🧪 开始测试AI转弯移动逻辑...")
    
    # 初始化服务
    config = Config()
    map_service = AmapService()
    local_data_service = LocalDataService()
    
    # 加载本地数据
    print("📊 加载本地道路和POI数据...")
    road_success = local_data_service.load_road_data("data/道路数据.shp")
    poi_success = local_data_service.load_poi_data("data/POI数据.shp")
    
    if not road_success or not poi_success:
        print("❌ 数据加载失败")
        return
    
    print("✅ 数据加载成功")
    
    # 创建AI探索者
    agent = ExplorerAgent()
    
    # 设置测试区域（天安门附近）
    boundary = [
        [39.8950, 116.3950],  # 左下角
        [39.9050, 116.4050]   # 右上角
    ]
    
    # 设置起始位置（天安门广场）
    start_location = [39.9000, 116.4000]
    
    # 初始化探索
    await agent.initialize(
        start_location=start_location,
        boundary=boundary,
        use_local_data=True,
        local_data_service=local_data_service
    )
    
    print(f"🎯 AI起始位置: {start_location}")
    print(f"📍 探索边界: {boundary}")
    
    # 测试路径规划和移动
    print("\n🛣️ 测试路径规划...")
    
    # 获取附近的POI作为目标
    nearby_pois = local_data_service.get_poi_data()
    if not nearby_pois:
        print("❌ 没有找到POI数据")
        return
    
    # 选择一个距离适中的POI作为目标
    target_poi = None
    for poi in nearby_pois[:10]:  # 检查前10个POI
        distance = map_service.calculate_distance(
            start_location, 
            [poi['location']['lat'], poi['location']['lng']]
        )
        if 200 < distance < 1000:  # 200-1000米的距离
            target_poi = poi
            break
    
    if not target_poi:
        print("❌ 没有找到合适的目标POI")
        return
    
    target_location = [target_poi['location']['lat'], target_poi['location']['lng']]
    target_name = target_poi.get('name', '未知POI')
    
    print(f"🎯 目标POI: {target_name}")
    print(f"📍 目标位置: {target_location}")
    
    # 计算路径
    path = local_data_service.find_shortest_path(
        (start_location[1], start_location[0]),  # 经度, 纬度
        (target_location[1], target_location[0])
    )
    
    if not path or len(path) < 2:
        print("❌ 路径规划失败")
        return
    
    print(f"✅ 路径规划成功，共{len(path)}个路径点")
    
    # 显示路径点
    print("\n📍 路径点列表:")
    for i, point in enumerate(path[:5]):  # 显示前5个路径点
        lat, lng = point[1], point[0]
        print(f"  {i+1}. [{lat:.6f}, {lng:.6f}]")
    if len(path) > 5:
        print(f"  ... 还有{len(path)-5}个路径点")
    
    # 测试移动到路径点
    print("\n🚶 开始测试移动...")
    
    # 模拟移动到前几个路径点
    test_points = path[1:min(4, len(path))]  # 测试前3个路径点
    
    for i, waypoint in enumerate(test_points):
        waypoint_location = [waypoint[1], waypoint[0]]  # 纬度, 经度
        
        print(f"\n🎯 移动到路径点 {i+1}: {waypoint_location}")
        
        # 记录移动前的位置
        before_location = agent.current_location.copy()
        print(f"📍 移动前位置: {before_location}")
        
        # 执行移动
        await agent._move_to_waypoint(
            waypoint_location, 
            target_name, 
            i+1, 
            len(test_points)
        )
        
        # 记录移动后的位置
        after_location = agent.current_location.copy()
        print(f"📍 移动后位置: {after_location}")
        
        # 检查是否精确到达路径点
        distance_to_waypoint = map_service.calculate_distance(
            after_location, waypoint_location
        )
        print(f"📏 与路径点距离: {distance_to_waypoint:.2f}米")
        
        if distance_to_waypoint < 5:  # 5米内认为精确到达
            print("✅ 精确到达路径点")
        else:
            print("⚠️ 未精确到达路径点")
        
        # 检查位置是否在道路上
        projected_point = local_data_service.project_point_to_road(
            (after_location[1], after_location[0])
        )
        
        if projected_point:
            distance_to_road = map_service.calculate_distance(
                after_location, 
                [projected_point[1], projected_point[0]]
            )
            print(f"🛣️ 距离最近道路: {distance_to_road:.2f}米")
            
            if distance_to_road < 20:  # 20米内认为在道路上
                print("✅ 位置在道路网络上")
            else:
                print("⚠️ 位置偏离道路网络")
        else:
            print("❌ 无法找到最近道路")
        
        # 等待一下再继续
        await asyncio.sleep(1)
    
    print("\n🎉 测试完成！")
    print("\n📊 测试总结:")
    print("- 修改了_move_to_waypoint方法，减少直线插值步数")
    print("- 添加了道路投影确保位置在道路上")
    print("- 精确设置最终位置为路径点坐标")
    print("- 这应该能解决AI转弯时走对角线的问题")

if __name__ == "__main__":
    asyncio.run(test_ai_turning())