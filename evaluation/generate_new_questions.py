#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from evaluation_questions import EvaluationQuestions
import json

def main():
    # 创建评估问题实例
    eq = EvaluationQuestions()
    
    # 获取所有问题
    all_questions = eq.get_all_questions()
    
    # 筛选路径规划问题（15-18题）
    path_questions = [q for q in all_questions if q.id >= 15 and q.id <= 18]
    
    for question in path_questions:
        print(f'### 问题{question.id}')
        print(f'**题目**: {question.question}')
        print()
        print('**选项**:')
        for i, option in enumerate(question.options):
            label = chr(65 + i)  # A, B, C, D
            print(f'- {label}. {option}')
        print()
        print(f'**正确答案**: {question.correct_answer}')
        print(f'**解释**: {question.explanation}')
        print(f'**难度**: {question.difficulty}')
        print()
        print('---')
        print()

if __name__ == "__main__":
    main()