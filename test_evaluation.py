#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试动态评估问题生成功能
"""

from evaluation.evaluation_questions import EvaluationQuestions

def test_dynamic_questions():
    """测试动态问题生成"""
    print("🧪 动态问题生成测试开始...")
    
    try:
        # 创建评估问题实例
        eq = EvaluationQuestions()
        
        # 获取所有问题
        questions = eq.get_all_questions()
        
        print(f"✅ 成功生成了 {len(questions)} 个问题")
        
        # 显示前3个问题的详细信息
        for i, q in enumerate(questions[:3]):
            print(f"\n📝 问题 {i+1}:")
            print(f"   ID: {q.id}")
            print(f"   类别: {q.category}")
            print(f"   问题: {q.question}")
            print(f"   选项: {q.options}")
            print(f"   正确答案: {q.correct_answer}")
            print(f"   难度: {q.difficulty}")
            print(f"   解释: {q.explanation}")
            print("-" * 50)
        
        # 统计各类别问题数量
        summary = eq.get_questions_summary()
        print(f"\n📊 问题分类统计:")
        for category, count in summary.items():
            print(f"   {category}: {count} 题")
        
        print("\n🎉 测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dynamic_questions()