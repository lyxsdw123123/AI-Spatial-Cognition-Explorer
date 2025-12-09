#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from evaluation.evaluation_questions import EvaluationQuestions
import json

def save_path_questions():
    """获取并保存路径规划问题"""
    # 创建评估问题生成器
    eq = EvaluationQuestions()
    
    # 获取所有问题
    questions = eq.get_all_questions()
    
    # 筛选路径规划问题
    path_questions = [q for q in questions if q.category == '路径规划']
    
    print(f'路径规划问题数量: {len(path_questions)}')
    
    # 保存到文件
    with open('path_questions_output.txt', 'w', encoding='utf-8') as f:
        f.write(f'路径规划问题数量: {len(path_questions)}\n')
        f.write('=' * 80 + '\n')
        
        for i, q in enumerate(path_questions, 1):
            f.write(f'问题 {q.id}:\n')
            f.write(f'题目: {q.question}\n')
            f.write(f'选项:\n')
            for j, option in enumerate(q.options, 1):
                f.write(f'  {chr(64+j)}. {option}\n')
            f.write(f'正确答案: {q.correct_answer}\n')
            f.write(f'解释: {q.explanation}\n')
            f.write(f'难度: {q.difficulty}\n')
            f.write(f'类别: {q.category}\n')
            f.write('=' * 80 + '\n')
    
    print('路径规划问题已保存到 path_questions_output.txt')

if __name__ == "__main__":
    save_path_questions()