import json
import csv
import os

def batch_process_json_files(folder_path, output_csv_name):
    """
    批量统计文件夹下JSON文件的context_text字段字节大小并导出CSV
    """
    # 结果存储列表
    summary_data = []
    
    # 检查文件夹是否存在
    if not os.path.exists(folder_path):
        print(f"错误：找不到文件夹 '{folder_path}'，请检查路径是否正确。")
        return

    # 遍历文件夹中的所有文件
    file_list = [f for f in os.listdir(folder_path) if f.endswith('.json')]
    print(f"开始处理，共发现 {len(file_list)} 个 JSON 文件...")

    for file_name in file_list:
        file_path = os.path.join(folder_path, file_name)
        
        try:
            # 使用 utf-8 编码读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
                
                # 提取字段，如果缺失则赋予默认值
                region = content.get("region", "未知区域")
                source_file = content.get("source_file", file_name)
                
                # 处理 context_text 字段
                # 即使JSON里写了两次，json.load 也会将其解析为单一键值对
                context_val = content.get("context_text", "")
                
                # 如果 context_text 意外地变成了列表（某些非标解析情况），取第一个
                if isinstance(context_val, list):
                    target_text = str(context_val[0])
                else:
                    target_text = str(context_val)
                
                # 计算字节大小 (UTF-8 编码)
                byte_size = len(target_text.encode('utf-8'))
                
                summary_data.append({
                    "区域": region,
                    "原始文件名": source_file,
                    "context_text字段字节大小": byte_size
                })
                
        except Exception as e:
            print(f"处理文件 {file_name} 时发生错误: {e}")

    # 将结果写入 CSV
    headers = ["区域", "原始文件名", "context_text字段字节大小"]
    try:
        # utf-8-sig 可以确保 Excel 打开中文不乱码
        with open(output_csv_name, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(summary_data)
        print(f"\n处理完成！汇总报告已生成：{os.path.abspath(output_csv_name)}")
    except Exception as e:
        print(f"写入 CSV 失败: {e}")

if __name__ == "__main__":
    # ================= 配置区域 =================
    # 1. 存放 JSON 文件的文件夹路径（请确保路径正确）
    input_folder = "修改三记忆报告无原始记忆评估结果报告" 
    
    # 2. 想要生成的 CSV 文件名
    csv_name = "context_text_无原始记忆统计汇总表.csv"
    # ===========================================

    batch_process_json_files(input_folder, csv_name)