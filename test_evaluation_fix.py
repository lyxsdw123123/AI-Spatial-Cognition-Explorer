#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试修复后的AI评估系统
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_agent.evaluation_agent import EvaluationAgent
from evaluation.evaluation_questions import EvaluationQuestions

async def test_evaluation_fix():
    """测试修复后的评估系统"""
    print("🧪 测试修复后的AI评估系统...")
    
    try:
        # 初始化评估问题生成器
        question_generator = EvaluationQuestions()
        
        # 生成测试问题（只生成路径规划问题）
        questions = question_generator.get_all_questions()
        
        # 筛选出路径规划问题
        path_questions = [q for q in questions if q.category == "路径规划"]
        
        if not path_questions:
            print("❌ 没有找到路径规划问题")
            return False
        
        print(f"📋 找到 {len(path_questions)} 个路径规划问题")
        
        # 模拟探索数据
        mock_exploration_data = {
            'ai_location': [39.9042, 116.4074],  # 天安门广场
            'exploration_path': [
                [39.9042, 116.4074],  # 天安门广场
                [39.9097, 116.4109],  # 王府井
                [39.9186, 116.3969],  # 故宫
            ],
            'visited_pois': [
                {
                    'name': '天安门东(地铁站)',
                    'type': '地铁站',
                    'location': {'lat': 39.9042, 'lng': 116.4074}
                },
                {
                    'name': '新怡家园',
                    'type': '住宅区',
                    'location': {'lat': 39.9097, 'lng': 116.4109}
                },
                {
                    'name': '霞公府',
                    'type': '商业建筑',
                    'location': {'lat': 39.9186, 'lng': 116.3969}
                },
                {
                    'name': '北京东方广场',
                    'type': '商业建筑',
                    'location': {'lat': 39.9097, 'lng': 116.4109}
                },
                {
                    'name': '长安大厦(东长安街)',
                    'type': '商业建筑',
                    'location': {'lat': 39.9042, 'lng': 116.4074}
                }
            ],
            'exploration_report': {
                'total_distance': 2500.0,
                'exploration_time': 300.0,
                'interesting_pois': [
                    {
                        'poi': {'name': '天安门东(地铁站)', 'type': '地铁站'},
                        'interest_level': 8
                    },
                    {
                        'poi': {'name': '北京东方广场', 'type': '商业建筑'},
                        'interest_level': 7
                    }
                ]
            }
        }
        
        # 初始化评估代理
        evaluation_agent = EvaluationAgent()
        
        # 转换问题格式
        formatted_questions = []
        for q in path_questions:
            formatted_questions.append({
                'question': q.question,
                'category': q.category,
                'options': q.options,
                'correct_answer': q.correct_answer,
                'explanation': q.explanation
            })
        
        # 初始化评估
        await evaluation_agent.initialize(formatted_questions, mock_exploration_data)
        
        print("🚀 开始评估...")
        
        # 开始评估
        await evaluation_agent.start_evaluation()
        
        # 获取结果
        result = evaluation_agent.get_result()
        
        if result:
            print(f"\n📊 评估结果:")
            print(f"总分: {result['total_score']}/{result['total_questions']}")
            print(f"准确率: {result['accuracy']:.1f}%")
            
            print(f"\n📝 详细答案:")
            for i, answer in enumerate(result['answers']):
                status = "✅" if answer['is_correct'] else "❌"
                print(f"{i+1}. {status} AI答案: {answer['ai_answer']}, 正确答案: {answer['correct_answer']}")
                print(f"   问题: {answer['question'][:50]}...")
                if not answer['is_correct']:
                    print(f"   解释: {answer['explanation']}")
                print()
            
            # 检查是否还是全选A
            ai_answers = [answer['ai_answer'] for answer in result['answers']]
            if all(answer == 'A' for answer in ai_answers):
                print("⚠️  警告: AI仍然全选A，修复可能不完全有效")
                return False
            else:
                print("✅ 修复成功: AI不再全选A")
                return True
        else:
            print("❌ 评估失败，没有获得结果")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函数"""
    success = await test_evaluation_fix()
    
    if success:
        print("\n🎉 测试成功！AI评估系统修复完成")
    else:
        print("\n💥 测试失败，需要进一步调试")

if __name__ == "__main__":
    asyncio.run(main())