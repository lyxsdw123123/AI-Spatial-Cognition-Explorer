# -*- coding: utf-8 -*-
import os
import json
import glob
import sys
from pathlib import Path

ROOT = r"d:\a_project_study\AI_exploer_aoto_onlybeijing\AI_exploer_aotoV10\AI_exploer_aoto"


def find_latest_memory():
    mm_dir = os.path.join(ROOT, "data", "mental_maps")
    files = glob.glob(os.path.join(mm_dir, "path_memory_*.json"))
    if not files:
        return None
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0]


def load_local_road_nodes():
    """尝试加载本地道路节点数据，返回列表格式的节点字典"""
    try:
        sys.path.append(ROOT)
        from data_service.local_data_service import LocalDataService
        lds = LocalDataService()
        # 道路数据非必需，仅加载节点
        ok = lds.load_road_nodes_data()
        if not ok:
            return []
        nodes = lds.get_road_nodes_data()
        # 统一结构，确保有 id、name、coordinates、location
        normalized = []
        for nd in nodes:
            name = nd.get('name')
            loc = nd.get('location')
            coords = nd.get('coordinates')
            if isinstance(loc, dict) and 'lat' in loc and 'lng' in loc:
                latlng = [float(loc['lat']), float(loc['lng'])]
            elif isinstance(coords, (list, tuple)) and len(coords) >= 2:
                latlng = [float(coords[1]), float(coords[0])] if abs(coords[0]) > 90 else [float(coords[0]), float(coords[1])]
            else:
                latlng = None
            normalized.append({
                'id': nd.get('id'),
                'name': name,
                'coordinates': coords,
                'location': latlng
            })
        return normalized
    except Exception as e:
        print(f"⚠️ 加载道路节点数据失败: {e}")
        return []


def build_exploration_data(memory):
    exploration_data = {}

    # 节点序列用于生成探索路径与当前位置
    ns = memory.get('node_sequences', {})
    coords_longest = []
    ai_loc = None
    if isinstance(ns, dict) and ns:
        seqs = list(ns.values())
        seqs.sort(key=lambda x: x.get('node_count', len(x.get('coordinates', []))), reverse=True)
        chosen = seqs[0]
        coords = chosen.get('coordinates', [])
        # 坐标格式统一为 [纬度, 经度]
        coords_longest = [
            [float(c[0]), float(c[1])] for c in coords
            if isinstance(c, (list, tuple)) and len(c) >= 2
        ]
        ai_loc = chosen.get('end_location') or (coords_longest[-1] if coords_longest else None)

    exploration_data['ai_location'] = ai_loc
    exploration_data['exploration_path'] = coords_longest

    # 已访问POI，从poi_connections聚合
    visited = []
    pc = memory.get('poi_connections', {})
    seen = set()
    for key, conn in pc.items():
        for side in ('start_poi', 'end_poi'):
            p = conn.get(side)
            if isinstance(p, dict):
                pid = p.get('id') or p.get('name')
                if pid and pid not in seen:
                    seen.add(pid)
                    loc = p.get('location')
                    if isinstance(loc, dict) and 'lat' in loc and 'lng' in loc:
                        location = [float(loc['lat']), float(loc['lng'])]
                    elif isinstance(loc, (list, tuple)) and len(loc) >= 2:
                        location = [float(loc[0]), float(loc[1])]
                    else:
                        location = None
                    visited.append({
                        'id': p.get('id'),
                        'name': p.get('name', '未知'),
                        'type': p.get('type', '未知'),
                        'location': location
                    })
    exploration_data['visited_pois'] = visited

    # 探索报告，保留总距离（如可用）
    stats = memory.get('metadata', {}).get('stats', {})
    total_distance = None
    try:
        total_distance = float(stats.get('node_layer', {}).get('total_distance'))
    except Exception:
        pass
    exploration_data['exploration_report'] = {'total_distance': total_distance}

    # 道路记忆，直接嵌入
    exploration_data['road_memory'] = {
        'poi_connections': pc,
        'road_segments': memory.get('road_segments', {}),
        'node_sequences': ns
    }

    # 道路节点数据（含名称），用于名称匹配
    exploration_data['road_nodes_data'] = load_local_road_nodes()

    return exploration_data


def main():
    latest = find_latest_memory()
    if not latest:
        print("未找到记忆数据文件")
        return
    print(f"使用记忆文件: {latest}")
    with open(latest, 'r', encoding='utf-8') as f:
        memory = json.load(f)

    # 用评估代理构建探索上下文
    sys.path.append(ROOT)
    from ai_agent.evaluation_agent import EvaluationAgent
    import asyncio
    agent = EvaluationAgent()
    exploration_data = build_exploration_data(memory)
    asyncio.run(agent.initialize([], exploration_data))
    context = agent._build_exploration_context()

    print("==== 当前探索上下文 ====")
    print(context)


if __name__ == "__main__":
    main()