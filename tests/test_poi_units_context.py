import os
import sys

# 将项目根目录加入路径，便于导入
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
sys.path.append(PROJECT_ROOT)

from ai_agent.evaluation_agent import EvaluationAgent


def test_poi_units_full_route_context():
    """验证评估端基于POI点单元与完整行驶路径的上下文生成（无经纬度/兴趣度）。"""
    agent = EvaluationAgent()

    new_exploration_data = {
        'poi_units': [
            {
                'poi': {'name': '天安门广场'},
                'visible_pois': [
                    {'name': '人民大会堂', 'direction_deg': 260, 'distance_m': 120},
                    {'name': '国家博物馆', 'direction_deg': 100, 'distance_m': 350},
                ],
            },
            {
                'poi': {'name': '故宫午门'},
                'visible_pois': [
                    {'name': '角楼', 'direction_deg': 30, 'distance_m': 200},
                ],
            },
        ],
        'full_route': {
            'start_name': '天安门广场',
            'segments': [
                {'to_name': '人民大会堂', 'direction_deg': 260, 'distance_m': 120},
                {'to_name': '国家博物馆', 'direction_deg': 100, 'distance_m': 350},
                {'to_name': '故宫午门', 'direction_deg': 20, 'distance_m': 600},
            ],
        },
        'exploration_summary': {
            'total_pois_visited': 3,
            'total_road_nodes_visited': 5,
            'total_distance_meters': 1200,
            'total_time_seconds': 600,
        },
    }

    import asyncio
    asyncio.run(agent.initialize([], {'new_exploration_data': new_exploration_data}))

    context_text = agent._build_exploration_context()

    # 断言关键结构与内容存在
    assert 'POI点单元记录（按时间顺序）' in context_text
    assert '完整行驶路径（仅方向与距离）' in context_text
    assert '天安门广场' in context_text
    assert '故宫午门' in context_text