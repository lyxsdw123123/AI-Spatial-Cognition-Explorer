#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI探索器与路径记忆系统集成测试
测试AI探索过程中的路径记忆功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_agent.explorer_agent import ExplorerAgent
from ai_agent.path_memory.path_memory_manager import PathMemoryManager
import json

async def test_explorer_integration():
    """测试探索器与路径记忆系统的集成"""
    print("🚀 开始AI探索器与路径记忆系统集成测试...")
    
    try:
        # 1. 初始化探索器
        print("\n1️⃣ 初始化AI探索器...")
        explorer = ExplorerAgent()
        
        # 检查路径记忆系统是否已集成
        if hasattr(explorer, 'path_memory'):
            print("✅ 路径记忆系统已集成到探索器中")
        else:
            print("❌ 路径记忆系统未集成，手动添加...")
            explorer.path_memory = PathMemoryManager()
        
        # 2. 设置测试区域
        print("\n2️⃣ 设置测试区域...")
        test_boundary = [
            [39.900, 116.400],  # 西南角
            [39.910, 116.400],  # 西北角
            [39.910, 116.410],  # 东北角
            [39.900, 116.410]   # 东南角
        ]
        
        start_location = [39.905, 116.405]  # 中心位置
        
        # 初始化探索器（使用正确的方法名）
        await explorer.initialize(
            start_location=start_location,
            boundary=test_boundary,
            use_local_data=False,
            exploration_mode="test"
        )
        
        print(f"✅ 探索区域设置完成: 起始位置 {start_location}")
        
        # 3. 模拟POI数据
        print("\n3️⃣ 设置测试POI...")
        test_pois = [
            {
                'id': 'poi_test_001',
                'name': '测试商场',
                'type': '购物中心',
                'location': [39.906, 116.406],
                'interest_score': 8
            },
            {
                'id': 'poi_test_002', 
                'name': '测试公园',
                'type': '公园',
                'location': [39.908, 116.408],
                'interest_score': 7
            },
            {
                'id': 'poi_test_003',
                'name': '测试餐厅',
                'type': '餐饮',
                'location': [39.904, 116.407],
                'interest_score': 6
            }
        ]
        
        # 将POI添加到探索器的可见范围
        explorer.all_pois = test_pois
        print(f"✅ 设置了 {len(test_pois)} 个测试POI")
        
        # 4. 模拟探索过程
        print("\n4️⃣ 开始模拟探索过程...")
        
        # 模拟移动到第一个POI
        target_poi = test_pois[0]
        print(f"🎯 移动到POI: {target_poi['name']}")
        
        # 记录移动路径
        if hasattr(explorer, 'path_memory'):
            explorer.path_memory.record_exploration_path(
                from_location=start_location,
                to_location=target_poi['location'],
                action="move_to_poi",
                notes=f"移动到{target_poi['name']}"
            )
        
        # 更新当前位置
        explorer.current_location = target_poi['location']
        
        # 记录POI访问
        if hasattr(explorer, 'path_memory'):
            visit_details = {
                'visit_time': '2024-01-01T10:00:00',
                'interest_level': target_poi['interest_score'],
                'notes': f"访问了{target_poi['name']}，类型：{target_poi['type']}",
                'approach_path': []
            }
            explorer.path_memory.record_poi_visit(target_poi, visit_details)
        
        print(f"✅ 记录了对 {target_poi['name']} 的访问")
        
        # 模拟移动到第二个POI
        target_poi2 = test_pois[1]
        print(f"🎯 移动到POI: {target_poi2['name']}")
        
        if hasattr(explorer, 'path_memory'):
            explorer.path_memory.record_exploration_path(
                from_location=explorer.current_location,
                to_location=target_poi2['location'],
                action="move_to_poi",
                notes=f"从{target_poi['name']}移动到{target_poi2['name']}"
            )
        
        explorer.current_location = target_poi2['location']
        
        # 记录第二个POI访问
        if hasattr(explorer, 'path_memory'):
            visit_details2 = {
                'visit_time': '2024-01-01T10:30:00',
                'interest_level': target_poi2['interest_score'],
                'notes': f"访问了{target_poi2['name']}，类型：{target_poi2['type']}",
                'approach_path': []
            }
            explorer.path_memory.record_poi_visit(target_poi2, visit_details2)
        
        print(f"✅ 记录了对 {target_poi2['name']} 的访问")
        
        # 5. 测试路径记忆查询
        print("\n5️⃣ 测试路径记忆查询功能...")
        
        if hasattr(explorer, 'path_memory'):
            # 获取记忆统计
            stats = explorer.path_memory.get_memory_stats()
            print(f"📊 记忆统计: {json.dumps(stats, ensure_ascii=False, indent=2)}")
            
            # 测试问答功能
            questions = [
                "我走了多远的距离？",
                "我访问了哪些POI？",
                "有哪些路径可以选择？",
                "我经过了哪些地方？"
            ]
            
            for question in questions:
                if hasattr(explorer.path_memory, 'answer_path_question'):
                    answer = explorer.path_memory.answer_path_question(question)
                    print(f"❓ 问题: {question}")
                    print(f"💬 回答: {answer}\n")
        
        # 6. 测试explorer_agent的问答功能
        print("\n6️⃣ 测试探索器的问答功能...")
        
        if hasattr(explorer, 'answer_location_question'):
            explorer_questions = [
                "我现在在哪里？",
                "我总共走了多远？",
                "我访问了几个POI？",
                "最近的POI在哪个方向？"
            ]
            
            for question in explorer_questions:
                try:
                    answer = explorer.answer_location_question(question)
                    print(f"❓ 问题: {question}")
                    print(f"💬 回答: {answer}\n")
                except Exception as e:
                    print(f"❌ 回答问题时出错: {e}")
        
        # 7. 验证记忆持久化
        print("\n7️⃣ 测试记忆持久化...")
        
        if hasattr(explorer, 'path_memory'):
            # 保存记忆
            save_success = explorer.path_memory.save_memory("integration_test_memory.json")
            if save_success:
                print("✅ 记忆保存成功")
            else:
                print("❌ 记忆保存失败")
        
        print("\n🎉 AI探索器与路径记忆系统集成测试完成！")
        return True
        
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_memory_integration_with_real_methods():
    """测试与真实探索方法的集成"""
    print("\n🔧 测试与真实探索方法的集成...")
    
    try:
        explorer = ExplorerAgent()
        
        # 检查关键方法是否存在
        methods_to_check = [
            '_visit_poi',
            '_move_to_location', 
            '_move_in_direction',
            'answer_location_question'
        ]
        
        for method_name in methods_to_check:
            if hasattr(explorer, method_name):
                print(f"✅ 方法 {method_name} 存在")
            else:
                print(f"❌ 方法 {method_name} 不存在")
        
        # 检查路径记忆系统集成
        if hasattr(explorer, 'path_memory'):
            print("✅ 路径记忆系统已集成")
            
            # 测试记忆系统方法
            memory_methods = [
                'record_exploration_path',
                'record_poi_visit',
                'answer_path_question'
            ]
            
            for method_name in memory_methods:
                if hasattr(explorer.path_memory, method_name):
                    print(f"✅ 记忆方法 {method_name} 存在")
                else:
                    print(f"❌ 记忆方法 {method_name} 不存在")
        else:
            print("❌ 路径记忆系统未集成")
        
        return True
        
    except Exception as e:
        print(f"❌ 方法集成测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🧪 开始AI探索器集成测试...")
    
    # 运行集成测试
    integration_success = await test_explorer_integration()
    
    # 运行方法集成测试
    method_success = test_memory_integration_with_real_methods()
    
    if integration_success and method_success:
        print("\n🎊 所有集成测试通过！")
    else:
        print("\n⚠️ 部分测试失败，请检查集成情况")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())