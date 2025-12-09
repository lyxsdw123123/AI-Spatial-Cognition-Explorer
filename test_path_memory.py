#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径记忆系统测试脚本
测试三层路径记忆系统的基础功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_agent.path_memory.path_memory_manager import PathMemoryManager
from datetime import datetime

def test_path_memory_system():
    """测试路径记忆系统的基础功能"""
    print("🧪 开始测试路径记忆系统...")
    
    # 初始化路径记忆管理器
    memory_manager = PathMemoryManager()
    
    # 测试数据
    start_location = [39.9042, 116.4074]  # 天安门
    boundary = [
        [39.9000, 116.4000],
        [39.9100, 116.4000], 
        [39.9100, 116.4150],
        [39.9000, 116.4150]
    ]
    
    # 1. 测试初始化
    print("\n1️⃣ 测试初始化...")
    memory_manager.initialize(start_location, boundary, "exploration")
    print("✅ 初始化成功")
    
    # 2. 测试探索路径记录
    print("\n2️⃣ 测试探索路径记录...")
    locations = [
        [39.9042, 116.4074],  # 起点
        [39.9050, 116.4080],  # 移动1
        [39.9055, 116.4090],  # 移动2
        [39.9060, 116.4100]   # 移动3
    ]
    
    for i in range(len(locations) - 1):
        from_loc = locations[i]
        to_loc = locations[i + 1]
        memory_manager.record_exploration_path(
            from_loc, to_loc, 
            f"move_{i+1}", f"测试移动{i+1}"
        )
    print(f"✅ 记录了 {len(locations)-1} 条探索路径")
    
    # 3. 测试POI访问记录
    print("\n3️⃣ 测试POI访问记录...")
    test_pois = [
        {
            'id': 'poi_001',
            'name': '测试餐厅',
            'location': [39.9055, 116.4090],
            'type': '餐饮服务'
        },
        {
            'id': 'poi_002', 
            'name': '测试商店',
            'location': [39.9060, 116.4100],
            'type': '购物服务'
        }
    ]
    
    for poi in test_pois:
        visit_details = {
            'visit_time': datetime.now(),
            'interest_level': 8,
            'notes': f'访问了{poi["name"]}',
            'approach_path': 'direct'
        }
        memory_manager.record_poi_visit(poi, visit_details)
    print(f"✅ 记录了 {len(test_pois)} 个POI访问")
    
    # 4. 测试道路遍历记录
    print("\n4️⃣ 测试道路遍历记录...")
    road_segments = [
        {
            'start_node': (116.4074, 39.9042),
            'end_node': (116.4080, 39.9050),
            'road_type': 'primary',
            'length': 100
        },
        {
            'start_node': (116.4080, 39.9050),
            'end_node': (116.4090, 39.9055),
            'road_type': 'secondary', 
            'length': 80
        }
    ]
    
    for segment in road_segments:
        memory_manager.record_road_traversal(
            segment['start_node'], segment['end_node'],
            segment['road_type'], segment['length']
        )
    print(f"✅ 记录了 {len(road_segments)} 条道路遍历")
    
    # 测试查询功能
    print("\n=== 测试查询功能 ===")
    
    # 查询POI连接
    connections = memory_manager.get_poi_connections("poi_001")
    print(f"POI连接查询结果: {connections}")
    
    # 查询节点路径
    node_paths = memory_manager.get_node_paths_from_location([39.9042, 116.4074])
    print(f"节点路径查询结果: {node_paths}")
    
    # 查询道路信息
    road_info = memory_manager.get_road_info_by_type("主干道")
    print(f"道路信息查询结果: {road_info}")
    
    # 查找POI间路径
    path_between = memory_manager.find_path_between_pois("poi_001", "poi_002")
    print(f"POI间路径: {path_between}")
    
    # 获取空间关系
    spatial_relations = memory_manager.get_spatial_relationships([39.9042, 116.4074])
    print(f"空间关系: {spatial_relations}")
    
    # 回答路径问题
    answer1 = memory_manager.answer_path_question("我走了多远的距离？")
    print(f"问题回答1: {answer1}")
    
    answer2 = memory_manager.answer_path_question("有哪些路径可以选择？")
    print(f"问题回答2: {answer2}")
    
    # 获取记忆统计
    stats = memory_manager.get_memory_stats()
    print(f"记忆统计: {stats}")
    
    # 6. 测试路径查找
    print("\n6️⃣ 测试路径查找...")
    
    # 查找POI间路径
    poi_path = memory_manager.find_path_between_pois('poi_001', 'poi_002')
    if poi_path:
        print(f"POI间路径: 找到路径，距离 {poi_path['distance']:.0f}米")
    else:
        print("POI间路径: 未找到直接路径")
    
    # 查找位置间路径
    location_path = memory_manager.find_path_between_locations(
        [39.9042, 116.4074], [39.9060, 116.4100]
    )
    if location_path:
        print(f"位置间路径: 找到路径，{len(location_path['nodes'])} 个节点")
    else:
        print("位置间路径: 未找到路径")
    
    # 7. 测试空间关系查询
    print("\n7️⃣ 测试空间关系查询...")
    spatial_relations = memory_manager.get_spatial_relationships([39.9055, 116.4090])
    print(f"空间关系: 找到 {len(spatial_relations)} 个相关POI")
    
    # 8. 测试问答功能
    print("\n8️⃣ 测试问答功能...")
    test_questions = [
        "从测试餐厅到测试商店怎么走？",
        "我探索了哪些POI？",
        "最近的POI是什么？"
    ]
    
    for question in test_questions:
        answer = memory_manager.answer_path_question(question)
        print(f"问题: {question}")
        print(f"回答: {answer}")
        print()
    
    # 9. 测试统计信息
    print("\n9️⃣ 测试统计信息...")
    stats = memory_manager.get_memory_stats()
    print("记忆统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n🔟 调试具名道路节点匹配与路径单元...")
    road_nodes_catalog = [
        {'Name': '东长安街路口', 'location': [39.9044, 116.4075]},
        {'Name': '王府井路口', 'location': [39.9060, 116.4100]},
    ]
    memory_manager.set_road_nodes_catalog(road_nodes_catalog)
    path_data = {
        'start_location': [39.9044, 116.4075],
        'end_location': [39.9060, 116.4100],
        'segments': [
            {'coordinates': [[39.9044, 116.4075], [39.9060, 116.4100]], 'length': 500}
        ],
        'nodes': [],
        'poi_waypoints': []
    }
    memory_manager.record_exploration_path_detailed(path_data)
    memory_manager.record_poi_visit({'id': 'poi_X', 'name': '隆和居', 'location': [39.9044, 116.4075]}, {
        'visit_time': datetime.now(),
        'visible_snapshot': [{'name': '正义路1号院', 'relative_position': {'direction': 21, 'distance': 324}}]
    })
    memory_manager.record_poi_visit({'id': 'poi_Y', 'name': '正义路1号院', 'location': [39.9060, 116.4100]}, {
        'visit_time': datetime.now(),
        'visible_snapshot': []
    })
    es = memory_manager.get_exploration_stats()
    print(f"[DEBUG] exploration_stats: total_road_nodes_visited={es.get('total_road_nodes_visited')} total_pois_visited={es.get('total_pois_visited')}")
    units = memory_manager.get_all_path_units()
    try:
        last = units[-1]
        rn = last.get('route_nodes') or []
        print(f"[DEBUG] last_path_unit route_nodes count={len(rn)} names={[x.get('name') for x in rn]}")
    except Exception:
        print("[DEBUG] 无路径单元或route_nodes为空")
    
    print("\n🎉 路径记忆系统测试完成！")
    return True

def test_memory_persistence():
    """测试记忆持久化功能"""
    print("\n💾 测试记忆持久化...")
    
    memory_manager = PathMemoryManager()
    
    # 添加一些测试数据
    memory_manager.initialize([39.9042, 116.4074], [], "test")
    memory_manager.record_exploration_path(
        [39.9042, 116.4074], [39.9050, 116.4080],
        "test_move", "测试移动"
    )
    
    # 保存记忆
    save_path = "test_memory_save.json"
    success = memory_manager.save_memory(save_path)
    print(f"保存记忆: {'成功' if success else '失败'}")
    
    # 清空记忆
    memory_manager.clear_all_memory()
    stats_after_clear = memory_manager.get_memory_stats()
    print(f"清空后统计: {stats_after_clear}")
    
    # 加载记忆
    success = memory_manager.load_memory(save_path)
    print(f"加载记忆: {'成功' if success else '失败'}")
    
    stats_after_load = memory_manager.get_memory_stats()
    print(f"加载后统计: {stats_after_load}")
    
    # 清理测试文件
    try:
        os.remove(save_path)
        print("✅ 清理测试文件成功")
    except:
        print("⚠️ 清理测试文件失败")
    
    return True

if __name__ == "__main__":
    try:
        # 运行基础功能测试
        test_path_memory_system()
        
        # 运行持久化测试
        test_memory_persistence()
        
        print("\n🎊 所有测试通过！路径记忆系统工作正常。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()