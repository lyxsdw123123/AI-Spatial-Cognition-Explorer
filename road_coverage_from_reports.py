import argparse
import csv
import json
import re
import unicodedata
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import networkx as nx

from backend.data_service.local_data_service import LocalDataService


def normalize_name(text: str) -> str:
    s = unicodedata.normalize("NFKC", text)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.strip().lower()
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    s = re.sub(r"[\s\-_]+", " ", s)
    s = re.sub(r"[^\w\s\u4e00-\u9fff]", "", s)
    return s.strip()


def iter_context_text_values(obj: Any) -> Iterator[str]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "context_text" and isinstance(v, str):
                yield v
            yield from iter_context_text_values(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_context_text_values(item)


def load_json(file_path: Path) -> Optional[dict]:
    try:
        raw = file_path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return None

    try:
        data = json.loads(raw)
    except Exception:
        return {"context_text": raw}
    return data if isinstance(data, dict) else {"context_text": raw}


def extract_route_points_from_report(data: dict) -> List[Tuple[float, float]]:
    report = data.get("exploration_report")
    if not isinstance(report, dict):
        return []
    path = report.get("exploration_path")
    if not isinstance(path, list):
        return []

    points: List[Tuple[float, float]] = []
    for item in path:
        if not isinstance(item, dict):
            continue
        loc = item.get("location")
        if (
            isinstance(loc, list)
            and len(loc) == 2
            and isinstance(loc[0], (int, float))
            and isinstance(loc[1], (int, float))
        ):
            lat = float(loc[0])
            lon = float(loc[1])
            points.append((lon, lat))
    return points


def extract_poi_sequence_from_report(data: dict) -> List[str]:
    report = data.get("exploration_report")
    if not isinstance(report, dict):
        return []
    path = report.get("exploration_path")
    if not isinstance(path, list):
        return []

    seq: List[str] = []
    last: Optional[str] = None
    for item in path:
        if not isinstance(item, dict):
            continue
        decision = item.get("decision")
        if not isinstance(decision, dict):
            continue
        target = decision.get("target")
        if not isinstance(target, str):
            continue
        name = target.strip()
        if not name:
            continue
        if last is None or name != last:
            seq.append(name)
            last = name
    return seq


def pick_context_text(data: dict, context_index: int) -> str:
    values = list(iter_context_text_values(data))
    if not values:
        return ""
    if context_index < 0:
        context_index = 0
    if context_index >= len(values):
        context_index = 0
    return values[context_index]


def infer_region(data: dict, file_name: str) -> str:
    region = data.get("region")
    if isinstance(region, str) and region.strip():
        return region.strip()

    m = re.match(r"^评估报告_(.+?)_", file_name)
    if m:
        return m.group(1).strip()

    if "_" in file_name:
        head = file_name.split("_", 1)[0].strip()
        if head:
            return head

    return ""


def extract_start_location(context_text: str) -> Optional[Tuple[float, float]]:
    m = re.search(
        r"Current Location:\s*\[\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\]", context_text
    )
    if not m:
        return None
    lat = float(m.group(1))
    lon = float(m.group(2))
    return (lon, lat)


def extract_poi_sequence(context_text: str) -> List[str]:
    if "NODE[" in context_text and "EDGE[" in context_text:
        node_to_poi_name: Dict[int, str] = {}
        for m in re.finditer(r"NODE\[(\d+),\s*POI,\s*name=([^\],\n]+)", context_text):
            try:
                node_id = int(m.group(1))
            except Exception:
                continue
            name = m.group(2).strip()
            if name:
                node_to_poi_name[node_id] = name

        seq_from_edges: List[str] = []
        for m in re.finditer(r"EDGE\[(\d+),(\d+),", context_text):
            try:
                to_id = int(m.group(2))
            except Exception:
                continue
            name = node_to_poi_name.get(to_id)
            if name:
                seq_from_edges.append(name)

        if seq_from_edges:
            dedup: List[str] = []
            last: Optional[str] = None
            for n in seq_from_edges:
                if last is None or n != last:
                    dedup.append(n)
                    last = n
            return dedup

    if "NODE[" in context_text and "ROAD[" in context_text and "EDGE[" not in context_text:
        seq_from_nodes: List[str] = []
        for m in re.finditer(r"NODE\[\d+,\s*POI,\s*name=([^\],\n，]+)", context_text):
            name = m.group(1).strip()
            if name:
                seq_from_nodes.append(name)
        if seq_from_nodes:
            dedup: List[str] = []
            last: Optional[str] = None
            for n in seq_from_nodes:
                if last is None or n != last:
                    dedup.append(n)
                    last = n
            return dedup

    patterns = [
        r"(?m)^\s*\d+\)\s*POI[:：]\s*(.+?)\s*$",
        r"(?m)^\s*POI[:：]\s*(.+?)\s*$",
        r"move_to_poi`?\s+with\s+`?\{[^}]*?['\"]poi_name['\"]\s*:\s*['\"]([^'\"]+)['\"][^}]*\}`?",
        r"move_to_poi\([^)]*?poi_name\s*=\s*['\"]([^'\"]+)['\"][^)]*\)",
        r"Successfully moved to and visited\s+(.+?)(?:\.\s|\.?$|\n)",
    ]

    hits: List[Tuple[int, str]] = []
    for pat in patterns:
        for m in re.finditer(pat, context_text):
            name = m.group(1).strip()
            if name:
                hits.append((m.start(), name))

    hits.sort(key=lambda x: x[0])

    seq: List[str] = []
    last: Optional[str] = None
    for _, name in hits:
        if last is None or name != last:
            seq.append(name)
            last = name
    return seq


def build_poi_index(
    service: LocalDataService,
) -> Tuple[Dict[str, Tuple[str, Tuple[float, float]]], List[str]]:
    index: Dict[str, Tuple[str, Tuple[float, float]]] = {}
    names: List[str] = []
    gdf = getattr(service, "poi_gdf", None)
    if gdf is None:
        return index, names

    for _, row in gdf.iterrows():
        name = row.get("name")
        geom = getattr(row, "geometry", None)
        if not isinstance(name, str) or not name.strip() or geom is None:
            continue
        canonical = name.strip()
        coord = (float(geom.x), float(geom.y))
        names.append(canonical)

        k1 = canonical
        k2 = canonical.lower()
        k3 = normalize_name(canonical)
        for k in (k1, k2, k3):
            if k and k not in index:
                index[k] = (canonical, coord)

    return index, sorted(set(names))


def resolve_poi_name(
    name: str,
    index: Dict[str, Tuple[str, Tuple[float, float]]],
    index_keys: List[str],
    cutoff: float,
) -> Optional[Tuple[str, Tuple[float, float]]]:
    if not name:
        return None
    direct = index.get(name) or index.get(name.lower())
    if direct is not None:
        return direct

    norm = normalize_name(name)
    direct = index.get(norm)
    if direct is not None:
        return direct

    matches = get_close_matches(norm, index_keys, n=1, cutoff=cutoff)
    if not matches:
        return None
    return index.get(matches[0])


def edge_key(u: int, v: int) -> Tuple[int, int]:
    return (u, v) if u <= v else (v, u)


def total_graph_length_m(G: nx.Graph) -> float:
    total = 0.0
    for _, _, data in G.edges(data=True):
        w = data.get("weight")
        if isinstance(w, (int, float)):
            total += float(w)
    return total


def shortest_path_edges(
    service: LocalDataService, start_pt: Tuple[float, float], end_pt: Tuple[float, float]
) -> List[Tuple[int, int]]:
    G = getattr(service, "road_network", None)
    if G is None or not getattr(service, "road_nodes", None):
        return []

    start_node = service._find_nearest_road_node(start_pt)
    end_node = service._find_nearest_road_node(end_pt)
    if start_node is None or end_node is None:
        return []

    path_nodes = nx.shortest_path(G, start_node, end_node, weight="weight")
    edges: List[Tuple[int, int]] = []
    for i in range(len(path_nodes) - 1):
        edges.append(edge_key(path_nodes[i], path_nodes[i + 1]))
    return edges


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("txt_statistics")
        / "大模型空间认知项目数据"
        / "1三种探索策略"
        / "探索策略结果"
        / "最近"
        / "最近报告"
        / "探索策略+最近评估结果报告",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("txt_statistics")
        / "大模型空间认知项目数据"
        / "1三种探索策略"
        / "探索策略结果"
        / "最近"
        / "最近道路覆盖率统计"
        / "最近_道路覆盖率统计.csv",
    )
    parser.add_argument("--glob", type=str, default="*.json")
    parser.add_argument("--context-index", type=int, default=0)
    parser.add_argument("--fuzzy-cutoff", type=float, default=0.92)
    parser.add_argument("--min-visited-poi-coverage", type=float, default=0.0)
    args = parser.parse_args()

    input_dir: Path = args.input_dir
    output_csv: Path = args.output_csv
    files = [p for p in input_dir.rglob(args.glob) if p.is_file()]
    files.sort(key=lambda p: str(p).lower())
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    region_cache: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []

    for fp in files:
        data = load_json(fp)
        if data is None:
            rows.append(
                {
                    "文件名": fp.name,
                    "区域": "",
                    "覆盖率": "",
                    "覆盖道路长度_m": "",
                    "总道路长度_m": "",
                    "解析POI数": 0,
                    "使用段数": 0,
                    "未匹配POI数": 0,
                    "无路可达段数": 0,
                    "错误": "JSON解析失败",
                }
            )
            continue

        region = infer_region(data, fp.name)
        context_text = pick_context_text(data, context_index=int(args.context_index))
        route_points = extract_route_points_from_report(data)
        poi_seq = extract_poi_sequence(context_text)
        if not poi_seq:
            poi_seq = extract_poi_sequence_from_report(data)
        start_pt = extract_start_location(context_text)
        if start_pt is None and route_points:
            start_pt = route_points[0]

        if not region:
            rows.append(
                {
                    "文件名": fp.name,
                    "区域": "",
                    "覆盖率": "",
                    "覆盖道路长度_m": "",
                    "总道路长度_m": "",
                    "解析POI数": len(poi_seq),
                    "使用段数": 0,
                    "未匹配POI数": len(poi_seq),
                    "无路可达段数": 0,
                    "错误": "无法识别region",
                }
            )
            continue

        if region not in region_cache:
            svc = LocalDataService(region_name=region)
            ok_road = svc.load_road_data()
            ok_poi = svc.load_poi_data()
            if not ok_road or not ok_poi or svc.road_network is None:
                region_cache[region] = {"ok": False, "err": "加载道路/POI失败"}
            else:
                poi_index, poi_names = build_poi_index(svc)
                poi_index_keys = sorted({normalize_name(n) for n in poi_names})
                total_len = total_graph_length_m(svc.road_network)
                region_cache[region] = {
                    "ok": True,
                    "service": svc,
                    "poi_index": poi_index,
                    "poi_index_keys": poi_index_keys,
                    "poi_names": poi_names,
                    "total_len": total_len,
                }

        cache = region_cache[region]
        if not cache.get("ok"):
            rows.append(
                {
                    "文件名": fp.name,
                    "区域": region,
                    "覆盖率": "",
                    "覆盖道路长度_m": "",
                    "总道路长度_m": "",
                    "解析POI数": len(poi_seq),
                    "使用段数": 0,
                    "未匹配POI数": len(poi_seq),
                    "无路可达段数": 0,
                    "错误": cache.get("err", "未知错误"),
                }
            )
            continue

        svc: LocalDataService = cache["service"]
        poi_index: Dict[str, Tuple[str, Tuple[float, float]]] = cache["poi_index"]
        poi_index_keys: List[str] = cache["poi_index_keys"]
        local_poi_names: List[str] = cache["poi_names"]
        total_len: float = float(cache["total_len"])

        points: List[Tuple[float, float]] = []
        if route_points:
            points = route_points
        else:
            if start_pt is not None:
                points.append(start_pt)

        unmatched = 0
        visited_unique: set[str] = set()
        for name in poi_seq:
            resolved = resolve_poi_name(
                name,
                index=poi_index,
                index_keys=poi_index_keys,
                cutoff=float(args.fuzzy_cutoff),
            )
            if resolved is None:
                unmatched += 1
                continue
            canonical, coord = resolved
            visited_unique.add(canonical)
            if not route_points:
                points.append(coord)

        poi_total = len(local_poi_names)
        poi_visited_unique = len(visited_unique)
        poi_visited_coverage = (poi_visited_unique / poi_total) if poi_total > 0 else 0.0
        missing_pois = sorted(set(local_poi_names) - visited_unique)
        missing_count = len(missing_pois)
        missing_sample = ";".join(missing_pois[:10])
        err_prefix = ""
        if float(args.min_visited_poi_coverage) > 0 and poi_visited_coverage < float(
            args.min_visited_poi_coverage
        ):
            err_prefix = f"访问POI覆盖率未达标({poi_visited_coverage:.3f})"

        if len(points) < 2:
            rows.append(
                {
                    "文件名": fp.name,
                    "区域": region,
                    "覆盖率": f"{0.0:.6f}",
                    "覆盖道路长度_m": f"{0.0:.2f}",
                    "总道路长度_m": f"{total_len:.2f}",
                    "解析POI数": len(poi_seq),
                    "访问POI去重数": poi_visited_unique,
                    "本地POI总数": poi_total,
                    "访问POI覆盖率": f"{poi_visited_coverage:.6f}",
                    "缺失访问POI数": missing_count,
                    "缺失访问POI示例": missing_sample,
                    "使用段数": 0,
                    "未匹配POI数": unmatched,
                    "无路可达段数": 0,
                    "错误": (err_prefix + ";" if err_prefix else "") + "可用点不足",
                }
            )
            continue

        covered_edges: set[Tuple[int, int]] = set()
        used_segments = 0
        no_path_segments = 0

        for i in range(len(points) - 1):
            s = points[i]
            t = points[i + 1]
            try:
                edges = shortest_path_edges(svc, s, t)
                if not edges:
                    no_path_segments += 1
                    continue
                used_segments += 1
                covered_edges.update(edges)
            except nx.NetworkXNoPath:
                no_path_segments += 1
            except Exception:
                no_path_segments += 1

        covered_len = 0.0
        G = svc.road_network
        for u, v in covered_edges:
            if G.has_edge(u, v):
                w = G[u][v].get("weight")
                if isinstance(w, (int, float)):
                    covered_len += float(w)

        coverage = (covered_len / total_len) if total_len > 0 else 0.0
        if err_prefix:
            rows.append(
                {
                    "文件名": fp.name,
                    "区域": region,
                    "覆盖率": "",
                    "覆盖道路长度_m": "",
                    "总道路长度_m": f"{total_len:.2f}",
                    "解析POI数": len(poi_seq),
                    "访问POI去重数": poi_visited_unique,
                    "本地POI总数": poi_total,
                    "访问POI覆盖率": f"{poi_visited_coverage:.6f}",
                    "缺失访问POI数": missing_count,
                    "缺失访问POI示例": missing_sample,
                    "使用段数": used_segments,
                    "未匹配POI数": unmatched,
                    "无路可达段数": no_path_segments,
                    "错误": err_prefix,
                }
            )
            continue
        rows.append(
            {
                "文件名": fp.name,
                "区域": region,
                "覆盖率": f"{coverage:.6f}",
                "覆盖道路长度_m": f"{covered_len:.2f}",
                "总道路长度_m": f"{total_len:.2f}",
                "解析POI数": len(poi_seq),
                "访问POI去重数": poi_visited_unique,
                "本地POI总数": poi_total,
                "访问POI覆盖率": f"{poi_visited_coverage:.6f}",
                "缺失访问POI数": missing_count,
                "缺失访问POI示例": missing_sample,
                "使用段数": used_segments,
                "未匹配POI数": unmatched,
                "无路可达段数": no_path_segments,
                "错误": "",
            }
        )

    fieldnames = [
        "文件名",
        "区域",
        "覆盖率",
        "覆盖道路长度_m",
        "总道路长度_m",
        "解析POI数",
        "访问POI去重数",
        "本地POI总数",
        "访问POI覆盖率",
        "缺失访问POI数",
        "缺失访问POI示例",
        "使用段数",
        "未匹配POI数",
        "无路可达段数",
        "错误",
    ]

    with output_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"已处理文件数: {len(rows)}")
    print(f"CSV输出: {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
