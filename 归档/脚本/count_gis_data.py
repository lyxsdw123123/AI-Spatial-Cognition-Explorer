import os
import geopandas as gpd
import pandas as pd

def count_gis_data(data_root):
    # 用于存放最终结果的列表
    summary_data = []

    # 获取 data 文件夹下所有的子文件夹名称
    subfolders = [f for f in os.listdir(data_root) if os.path.isdir(os.path.join(data_root, f))]

    for folder in subfolders:
        folder_path = os.path.join(data_root, folder)
        
        # 初始化统计数值
        stats = {
            "区域名称": folder,
            "POI数据": 0,
            "道路节点数据": 0,
            "道路数据": 0
        }

        # 定义文件名与统计项的映射关系
        target_files = {
            "POI数据.shp": "POI数据",
            "道路节点数据.shp": "道路节点数据",
            "道路数据.shp": "道路数据"
        }

        # 遍历该子文件夹下的目标文件
        for filename, column_name in target_files.items():
            file_path = os.path.join(folder_path, filename)
            
            if os.path.exists(file_path):
                try:
                    # 读取 shp 文件并获取行数
                    gdf = gpd.read_file(file_path)
                    stats[column_name] = len(gdf)
                except Exception as e:
                    print(f"读取 {file_path} 时出错: {e}")
            else:
                print(f"警告: 在 {folder} 中未找到 {filename}")

        summary_data.append(stats)

    # 转换为 DataFrame
    df = pd.DataFrame(summary_data)
    
    # 导出为 CSV
    output_file = "统计结果.csv"
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n统计完成！共处理 {len(subfolders)} 个文件夹。")
    print(f"结果已保存至: {os.path.abspath(output_file)}")

# 执行脚本（确保脚本和 data 文件夹在同一目录下）
if __name__ == "__main__":
    count_gis_data('./data')