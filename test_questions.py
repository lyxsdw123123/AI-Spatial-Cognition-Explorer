# 测试生成的评估问题
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from evaluation.evaluation_questions import EvaluationQuestions

def main():
    # 创建评估问题实例
    eq = EvaluationQuestions()
    
    # 获取所有问题
    questions = eq.get_all_questions()
    
    print(f"总共生成了 {len(questions)} 个问题")
    print("\n问题分类统计:")
    summary = eq.get_questions_summary()
    for category, count in summary.items():
        print(f"  {category}: {count}题")
    
    print("\n详细问题列表:")
    print("=" * 80)
    
    for i, question in enumerate(questions, 1):
        print(f"\n问题 {question.id} ({question.category})")
        print(f"题目: {question.question}")
        print("选项:")
        for j, option in enumerate(question.options):
            label = chr(65 + j)  # A, B, C, D
            print(f"  {label}. {option}")
        print(f"正确答案: {question.correct_answer}")
        print(f"解释: {question.explanation}")
        print(f"难度: {question.difficulty}")
        print("-" * 60)

if __name__ == "__main__":
    main()