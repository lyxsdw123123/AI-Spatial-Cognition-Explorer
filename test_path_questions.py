#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from evaluation.evaluation_questions import EvaluationQuestions
from data_service.local_data_service import LocalDataService
import traceback

def test_local_data_service():
    """测试LocalDataService道路节点加载"""
    try:
        print('🧪 测试LocalDataService道路节点加载...')
        
        # 直接测试LocalDataService
        lds = LocalDataService()
        print(f'初始化后 - is_data_loaded: {lds.is_data_loaded()}')
        
        lds.load_road_data()
        print(f'加载道路数据后 - is_data_loaded: {lds.is_data_loaded()}')
        
        result = lds.load_road_nodes_data()
        print(f'加载道路节点数据结果: {result}')
        print(f'hasattr road_nodes_gdf: {hasattr(lds, "road_nodes_gdf")}')
        if hasattr(lds, "road_nodes_gdf"):
            print(f'road_nodes_gdf is None: {lds.road_nodes_gdf is None}')
            if lds.road_nodes_gdf is not None:
                print(f'道路节点数据长度: {len(lds.road_nodes_gdf)}')
                print(f'道路节点数据列: {list(lds.road_nodes_gdf.columns)}')
        
        return lds
        
    except Exception as e:
        print(f'❌ 测试失败: {str(e)}')
        traceback.print_exc()
        return None

def test_path_questions():
    """测试路径规划问题生成"""
    try:
        print('\n🧪 测试修改后的路径规划问题生成...')
        
        # 创建评估问题生成器
        eq = EvaluationQuestions()
        
        # 获取所有问题
        questions = eq.get_all_questions()
        
        print(f'✅ 成功生成 {len(questions)} 个问题')
        
        # 查看路径规划问题（问题15-18）
        path_questions = [q for q in questions if q.category == '路径规划']
        print(f'📍 路径规划问题数量: {len(path_questions)}')
        
        for i, q in enumerate(path_questions[:2], 1):  # 只显示前2个问题
            print(f'\n问题 {q.id}:')
            print(f'题目: {q.question}')
            print(f'选项:')
            for j, option in enumerate(q.options, 1):
                print(f'  {chr(64+j)}. {option}')
            print(f'正确答案: {q.correct_answer}')
            print(f'解释: {q.explanation}')
            print('-' * 50)
            
    except Exception as e:
        print(f'❌ 测试失败: {str(e)}')
        traceback.print_exc()

if __name__ == "__main__":
    # 先测试LocalDataService
    lds = test_local_data_service()
    
    # 再测试路径规划问题生成
    test_path_questions()