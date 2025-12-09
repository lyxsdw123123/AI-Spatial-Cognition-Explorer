import os
import sys

# 将项目根目录加入路径，便于导入
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
sys.path.append(PROJECT_ROOT)

from ai_agent.evaluation_agent import EvaluationAgent


def build_mock_exploration_data():
    """构造模拟的探索数据，包含AI位置、探索路径、已访问POI、道路记忆和探索报告"""
    exploration_data = {
        # AI当前位置（天安门附近）
        "ai_location": [39.9087, 116.3975],
        # 探索路径：若干道路节点（坐标）
        "exploration_path": [
            [39.9087, 116.3975],
            [39.9096, 116.3970],
            [39.9105, 116.3960],
            [39.9112, 116.3950],
            [39.9118, 116.3940],
            [39.9125, 116.3930],
        ],
        # 已访问POI：包含名称、类型、ID与坐标
        "visited_pois": [
            {"id": "poi_1", "name": "天安门广场", "type": "景点", "location": [39.9087, 116.3975]},
            {"id": "poi_2", "name": "中国国家博物馆", "type": "博物馆", "location": [39.9040, 116.4015]},
            {"id": "poi_3", "name": "故宫午门", "type": "古迹", "location": [39.9163, 116.3970]},
            {"id": "poi_4", "name": "人民大会堂", "type": "政府建筑", "location": [39.9080, 116.3965]},
        ],
        # 道路记忆统计
        "road_memory": {
            "node_layer": {
                "total_paths": 3,
                "total_nodes": 48,
                "total_distance": 2650.7,
                "average_path_length": 883.6,
            },
            "road_layer": {
                "total_road_segments": 12,
                "type_distribution": {"主干道": 7, "支路": 5},
                "average_segment_length": 220.3,
            },
        },
        # 探索报告（保留客观统计）
        "exploration_report": {
            "total_distance": 1520.0,
            "exploration_time": 620.0,
            # 可选：如果提供interesting_pois，连接关系按顺序推断
            # "interesting_pois": [
            #     {"poi": {"id": "poi_1", "name": "天安门广场", "type": "景点", "location": [39.9087, 116.3975]}},
            #     {"poi": {"id": "poi_4", "name": "人民大会堂", "type": "政府建筑", "location": [39.9080, 116.3965]}},
            #     {"poi": {"id": "poi_2", "name": "中国国家博物馆", "type": "博物馆", "location": [39.9040, 116.4015]}},
            #     {"poi": {"id": "poi_3", "name": "故宫午门", "type": "古迹", "location": [39.9163, 116.3970]}},
            # ]
        },
        # 新增：提供道路节点数据以便上下文匹配名称
        "road_nodes_data": [
            {"id": "node_1", "name": "东长安街-节点1", "coordinates": (116.3975, 39.9087)},
            {"id": "node_2", "name": "东长安街-节点2", "coordinates": (116.3970, 39.9096)},
            {"id": "node_3", "name": "东长安街-节点3", "coordinates": (116.3960, 39.9105)},
            {"id": "node_4", "name": "东长安街-节点4", "coordinates": (116.3950, 39.9112)},
            {"id": "node_5", "name": "东长安街-节点5", "coordinates": (116.3940, 39.9118)},
            {"id": "node_6", "name": "东长安街-节点6", "coordinates": (116.3930, 39.9125)},
        ],
    }
    return exploration_data


def main():
    agent = EvaluationAgent()
    exploration_data = build_mock_exploration_data()

    # 初始化评估代理（问题留空，仅构建上下文）
    import asyncio
    asyncio.run(agent.initialize([], exploration_data))

    # 构建并打印探索上下文
    context_text = agent._build_exploration_context()
    print("==== 生成的探索上下文 ====")
    print(context_text)

    # 简单断言：检查包含坐标、节点与连接关键字
    assert "已访问POI坐标" in context_text or "POI标识示例" in context_text, "未包含POI坐标信息"
    assert "已探索道路节点坐标" in context_text, "未包含道路节点坐标"
    assert "POI连接关系" in context_text, "未包含POI连接关系"


if __name__ == "__main__":
    main()