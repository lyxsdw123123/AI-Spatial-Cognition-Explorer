
import os
import json
import asyncio
import sys
import csv
from datetime import datetime
import aiohttp

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

# from backend.question_generator import EvaluationQuestions # Avoid local import to prevent missing dependency errors

# 配置输入文件夹路径（用户可根据需要修改此处）
# 选项: "修改三记忆报告有原始记忆" 或 "修改三记忆报告无原始记忆"
INPUT_DIR = "三提问方式报告无原始记忆1"
OUTPUT_REPORT_DIR = "三提问方式报告无原始记忆结果报告1"
OUTPUT_CSV_FILE = "三提问方式报告无原始记忆结果汇总5.csv"
BACKEND_API_URL = "http://127.0.0.1:8000/evaluation"

async def evaluate_file(file_path, csv_writer, csvfile, session):
    print(f"正在处理文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"读取文件失败 {file_path}: {e}")
        return

    # 1. 截取 context_text
    context_text = data.get("context_text", "")
    if not context_text:
        print(f"文件 {file_path} 中未找到 context_text，跳过。")
        return

    # 2. 获取区域名称以生成题目
    region = data.get("region", "")
    if not region:
        # 尝试从文件名推断，例如 "上海外滩_..."
        filename = os.path.basename(file_path)
        if "_" in filename:
            region = filename.split("_")[0]
        else:
            print(f"无法确定区域名称，跳过文件: {file_path}")
            return

    print(f"识别区域: {region}")

    # 3. 生成题目 (调用后端API)
    questions = []
    try:
        print("正在请求生成题目...")
        async with session.post(f"{BACKEND_API_URL}/questions", json={"region_name": region}) as resp:
            if resp.status != 200:
                print(f"生成题目失败: {resp.status} - {await resp.text()}")
                return
            q_data = await resp.json()
            if not q_data.get("success"):
                print(f"生成题目API返回错误: {q_data}")
                return
            questions = q_data.get("data", {}).get("questions", [])
            if not questions:
                print("未获取到题目数据")
                return
    except Exception as e:
        print(f"生成题目请求异常: {e}")
        return

    # 4. 调用后端API进行评估
    context_mode = data.get("memory_mode", "text") 
    model = data.get("model", "qwen")
    
    # 构造请求 payload
    payload = {
        "questions": questions,
        "exploration_data": {
            "ai_location": [0.0, 0.0], # 占位符
            "exploration_path": [],    # 占位符
            "visited_pois": [],        # 占位符
            "context_text": context_text,
            "context_mode": context_mode,
            "prompt_rules": ""
        },
        "model_provider": model,
        "strategies": ["ToT"]
    }

    processed_strategies = set()
    final_result = {}

    try:
        print("发送评估请求到后端...")
        async with session.post(f"{BACKEND_API_URL}/start", json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"启动评估失败: {resp.status} - {text}")
                return
            start_data = await resp.json()
            if not start_data.get("success"):
                print(f"启动评估未成功: {start_data}")
                return
            
            print("评估已启动，正在等待完成...")

        # 5. 轮询状态和结果
        while True:
            await asyncio.sleep(2) # 每2秒检查一次
            
            # 获取状态
            status = "unknown"
            async with session.get(f"{BACKEND_API_URL}/status") as resp:
                if resp.status == 200:
                    status_data = await resp.json()
                    status = status_data.get("status")
                else:
                    print(f"获取状态失败: {resp.status}")
                    break

            # 增量获取结果
            async with session.get(f"{BACKEND_API_URL}/result") as resp:
                if resp.status == 200:
                    result_data = await resp.json()
                    if result_data.get("success"):
                        current_results = result_data.get("data", {})
                        final_result = current_results # Update final result holder
                        
                        # 检查新完成的策略
                        for strategy, strat_result in current_results.items():
                             if strategy in ["context_text", "context_mode"]: continue
                             if strategy not in processed_strategies and isinstance(strat_result, dict):
                                 # 发现新结果
                                 processed_strategies.add(strategy)
                                 print(f"策略 {strategy} 已完成，准确率: {strat_result.get('accuracy', 0):.2f}%")
                                 
                                 # 1. 立即写入 CSV
                                 if csv_writer:
                                     try:
                                         # Extract type scores
                                         type_scores = strat_result.get("type_scores", {})
                                         
                                         row_data = {
                                             "Region": region,
                                             "Model": model,
                                             "Memory Mode": context_mode,
                                             "Strategy": strategy,
                                             "Total Score": strat_result.get("total_score", 0),
                                             "Accuracy": f"{strat_result.get('accuracy', 0):.2f}%",
                                             "Completed At": strat_result.get("completed_at", ""),
                                         }
                                         
                                         # Add type specific scores
                                         target_types = ["定位与定向", "空间距离估算", "邻近关系判断", "POI密度识别", "路径规划"]
                                         for t_type in target_types:
                                             t_data = type_scores.get(t_type, {})
                                             t_acc = t_data.get("percentage", 0)
                                             row_data[f"Type_{t_type}"] = f"{t_acc:.2f}%"

                                         csv_writer.writerow(row_data)
                                         csvfile.flush() # 立即刷新到磁盘
                                     except Exception as e:
                                         print(f"写入CSV失败: {e}")

                                 # 2. 更新 JSON 报告
                                 report = {
                                    "region": region,
                                    "source_file": os.path.basename(file_path),
                                    "evaluation_time": datetime.now().isoformat(),
                                    "context_text": context_text,
                                    "evaluation_result": current_results
                                 }
                                 
                                 if not os.path.exists(OUTPUT_REPORT_DIR):
                                     os.makedirs(OUTPUT_REPORT_DIR)
                                 output_filename = f"评估报告_{os.path.basename(file_path)}"
                                 if not output_filename.endswith(".json"):
                                     output_filename += ".json"
                                 output_path = os.path.join(OUTPUT_REPORT_DIR, output_filename)
                                 
                                 try:
                                     with open(output_path, 'w', encoding='utf-8') as f:
                                         json.dump(report, f, ensure_ascii=False, indent=2)
                                     # print(f"报告已更新: {output_path}")
                                 except Exception as e:
                                     print(f"更新报告失败: {e}")

            if status == "completed":
                print("评估全部完成！")
                break
            elif status == "failed":
                print(f"评估失败")
                break
            elif status == "idle":
                print("评估状态异常(idle)，停止轮询。")
                break

    except aiohttp.ClientConnectorError:
        print("无法连接到后端服务器，请确保后端服务 (http://127.0.0.1:8000) 已启动。")
        return
    except Exception as e:
        print(f"API调用过程出错: {e}")
        return

async def main():
    if not os.path.exists(INPUT_DIR):
        print(f"输入目录不存在: {INPUT_DIR}")
        return 
    
    # 获取目录下所有 txt/json 文件
    files = []
    if os.path.exists(INPUT_DIR):
        files = [os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR) if f.endswith('.txt') or f.endswith('.json')]
    
    if not files:
        print("未找到任何报告文件。")
        return

    # 初始化 CSV
    headers = [
        "Region", "Model", "Memory Mode", "Strategy", "Total Score", "Accuracy", "Completed At",
        "Type_定位与定向", "Type_空间距离估算", "Type_邻近关系判断", "Type_POI密度识别", "Type_路径规划"
    ]
    
    async with aiohttp.ClientSession() as session:
        # 使用 'utf-8-sig' 以便 Excel 正确打开
        with open(OUTPUT_CSV_FILE, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            csvfile.flush()
    
            for file_path in files:
                await evaluate_file(file_path, writer, csvfile, session)

if __name__ == "__main__":
    asyncio.run(main())
