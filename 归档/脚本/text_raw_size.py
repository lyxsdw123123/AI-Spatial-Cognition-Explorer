import json
import csv
import os

def batch_process_txt_reports(folder_path, output_csv_name):
    """
    批量处理扩展名为.txt但内容为JSON的报告文件，统计字段大小并汇总。
    """
    summary_data = []
    
    if not os.path.exists(folder_path):
        print(f"错误：找不到文件夹 '{folder_path}'")
        return

    # 获取文件夹内所有 .txt 文件
    file_list = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
    print(f"发现 {len(file_list)} 个待处理的 TXT 报告文件...")

    for file_name in file_list:
        file_path = os.path.join(folder_path, file_name)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_content = f.read()
                # 尝试解析 JSON
                data = json.loads(raw_content)
                
                # 提取关键字段
                region = data.get("region", "未知区域")
                # 如果内部没有 source_file 字段，则使用当前文件名
                source_file = data.get("source_file", file_name)
                
                # 获取 context_text
                context_val = data.get("context_text", "")
                
                # 确保处理可能存在的非字符串情况
                if isinstance(context_val, list):
                    target_text = str(context_val[0])
                else:
                    target_text = str(context_val)
                
                # 精确计算字节大小 (UTF-8)
                byte_size = len(target_text.encode('utf-8'))
                
                summary_data.append({
                    "区域": region,
                    "原始文件名": source_file,
                    "context_text字段字节大小": byte_size
                })
                
        except json.JSONDecodeError:
            print(f"跳过文件 {file_name}：内容不是有效的 JSON 格式。")
        except Exception as e:
            print(f"处理文件 {file_name} 时出错: {e}")

    # 导出 CSV
    headers = ["区域", "原始文件名", "context_text字段字节大小"]
    try:
        with open(output_csv_name, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(summary_data)
        print(f"\n统计完成！报告已保存为: {os.path.abspath(output_csv_name)}")
    except Exception as e:
        print(f"保存 CSV 失败: {e}")

if __name__ == "__main__":
    # 配置信息
    TARGET_FOLDER = "探索策略+最近报告"  # 您的文件夹名称
    OUTPUT_FILE = "raw_统计汇总.csv" # 可以在此修改文件名
    
    batch_process_txt_reports(TARGET_FOLDER, OUTPUT_FILE)