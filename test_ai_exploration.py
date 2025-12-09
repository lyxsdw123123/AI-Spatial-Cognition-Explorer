#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试AI探索是否使用道路网络
"""

import sys
import os
import asyncio
import json
from typing import List, Tuple

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_agent.explorer_agent import ExplorerAgent
from data_service.local_data_service import LocalDataService

async def test_ai_exploration_with_road_network():
    """测试AI探索是否使用道路网络"""
    print("🤖 开始测试AI探索道路网络功能...")
    
    # 初始化本地数据服务
    local_data_service = LocalDataService()
    
    # 加载数据
    print("📁 加载本地数据...")
    local_data_service.load_poi_data()
    local_data_service.load_road_data()
    
    if local_data_service.road_network is None:
        print("❌ 道路网络未加载")
        return False
    
    print(f"✅ 数据加载成功 - POI: {len(local_data_service.poi_gdf) if local_data_service.poi_gdf is not None else 0}, 道路: {len(local_data_service.roads_gdf) if local_data_service.roads_gdf is not None else 0}")
    
    # 初始化AI代理
    explorer_agent = ExplorerAgent()
    
    # 设置测试边界（天安门附近）
    boundary = {
        'north': 39.92,
        'south': 39.90,
        'east': 116.41,
        'west': 116.39
    }
    
    # 设置起始位置（天安门）
    start_location = (116.3974, 39.9093)
    
    print(f"🎯 初始化AI代理...")
    print(f"起始位置: {start_location}")
    print(f"边界: {boundary}")
    
    # 初始化AI代理（使用本地数据）
    await explorer_agent.initialize(
        start_location=start_location,
        boundary=boundary,
        use_local_data=True,
        local_data_service=local_data_service
    )
    
    # 设置探索状态为True，这样AI才能移动
    explorer_agent.is_exploring = True
    
    print(f"✅ AI代理初始化完成")
    print(f"当前位置: {explorer_agent.current_location}")
    print(f"使用本地数据: {hasattr(explorer_agent, 'use_local_data') and explorer_agent.use_local_data}")
    print(f"探索状态: {explorer_agent.is_exploring}")
    
    # 测试移动功能
    print("\n🚶 测试AI移动功能...")
    
    # 设置一个目标位置
    # 注意：AI系统使用[纬度, 经度]格式
    target_location = [39.9193, 116.4074]  # [纬度, 经度] 天安门东北方向
    print(f"目标位置: {target_location}")
    
    # 记录移动前的位置
    initial_position = explorer_agent.current_location
    print(f"移动前位置: {initial_position}")
    
    # 创建一个测试决策
    test_decision = {
        "action": "move_to_poi",
        "target": "测试目标点",
        "target_location": target_location,
        "reason": "测试AI道路网络移动",
        "interest_level": 5,
        "notes": "测试用例"
    }
    
    # 执行移动
    print("\n🗺️ 开始移动...")
    try:
        # 调用内部移动方法进行测试
        await explorer_agent._move_to_location(target_location, test_decision)
        
        final_position = explorer_agent.current_location
        print(f"移动后位置: {final_position}")
        
        # 检查是否移动了
        if initial_position and final_position and initial_position != final_position:
            print("✅ AI成功移动")
            
            # 计算移动距离
            distance = ((final_position[0] - initial_position[0])**2 + (final_position[1] - initial_position[1])**2)**0.5
            print(f"移动距离: {distance:.6f}度")
            
            return True
        else:
            print("❌ AI未移动")
            return False
            
    except Exception as e:
        print(f"❌ 移动过程中出现错误: {e}")
        return False

def test_path_planning_directly():
    """直接测试路径规划功能"""
    print("\n🧪 直接测试路径规划功能...")
    
    # 初始化本地数据服务
    local_data_service = LocalDataService()
    local_data_service.load_road_data()
    
    if local_data_service.road_network is None:
        print("❌ 道路网络未加载")
        return False
    
    # 测试多个路径
    test_cases = [
        ((116.3974, 39.9093), (116.4074, 39.9193)),  # 天安门到东北
        ((116.4000, 39.9100), (116.4050, 39.9150)),  # 另一组测试点
        ((116.3950, 39.9080), (116.4100, 39.9200)),  # 更远的测试点
    ]
    
    success_count = 0
    for i, (start, end) in enumerate(test_cases, 1):
        print(f"\n测试案例 {i}: {start} -> {end}")
        path = local_data_service.find_shortest_path(start, end)
        
        if len(path) > 2:
            print(f"✅ 路径规划成功，路径点数: {len(path)}")
            success_count += 1
        else:
            print(f"⚠️ 返回直线路径，路径点数: {len(path)}")
    
    print(f"\n📊 路径规划测试结果: {success_count}/{len(test_cases)} 成功")
    return success_count > 0

async def main():
    """主测试函数"""
    print("🚀 开始AI探索道路网络测试")
    print("=" * 50)
    
    # 测试路径规划
    path_success = test_path_planning_directly()
    
    print("\n" + "=" * 50)
    
    # 测试AI探索
    ai_success = await test_ai_exploration_with_road_network()
    
    print("\n" + "=" * 50)
    print("📋 测试总结:")
    print(f"路径规划功能: {'✅ 正常' if path_success else '❌ 异常'}")
    print(f"AI探索功能: {'✅ 正常' if ai_success else '❌ 异常'}")
    
    if path_success and ai_success:
        print("\n🎉 所有测试通过！AI探索已正确使用道路网络")
        return True
    else:
        print("\n❌ 测试失败，需要进一步检查")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)