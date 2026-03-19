# 路径记忆管理器

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import json
import os
import uuid

from .poi_memory_layer import POIMemoryLayer
from .road_node_memory_layer import RoadNodeMemoryLayer
from .road_data_memory_layer import RoadDataMemoryLayer

class PathMemoryManager:
    """路径记忆管理器 - 统一管理三层记忆系统"""
    
    def __init__(self, data_dir: str = "data/mental_maps"):
        # 初始化三层记忆系统
        self.poi_layer = POIMemoryLayer()
        self.node_layer = RoadNodeMemoryLayer()
        self.road_layer = RoadDataMemoryLayer()
        
        # 数据存储目录
        self.data_dir = data_dir
        # self._ensure_data_dir()  # 用户不需要持久化存储
        
        # 记忆管理配置
        self.auto_save = False
        self.save_interval = 10  # 每10次操作自动保存一次
        self.operation_count = 0
        
        # 初始化状态
        self.is_initialized = False
        self.start_location = None
        self.boundary = None
        self.exploration_mode = None

        # 路径单元管理（一个POI一个路径）
        self.path_units: List = []
        self._path_unit_sequence = 0
        self._last_poi_visit: Optional[Dict] = None  # 保存最近一次POI访问的最小信息
        self.path_units_dir = os.path.join("data", "path_units")
        # self._ensure_path_units_dir()  # 用户不需要持久化存储，禁用自动创建
        self._grid_cache = None
        self.ordered_sequence: List[Dict] = []
        
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
    
    def initialize(self, start_location: List[float], boundary: List[List[float]], 
                   exploration_mode: str = "exploration") -> None:
        """初始化路径记忆系统
        
        Args:
            start_location: 起始位置 [纬度, 经度]
            boundary: 探索边界
            exploration_mode: 探索模式
        """
        try:
            existing_catalog = getattr(self, "_road_nodes_catalog", None)
        except Exception:
            existing_catalog = None

        try:
            self.poi_layer = POIMemoryLayer()
            self.node_layer = RoadNodeMemoryLayer()
            self.road_layer = RoadDataMemoryLayer()
        except Exception:
            pass

        try:
            self.path_units = []
            self._path_unit_sequence = 0
            self._last_poi_visit = None
            self._grid_cache = None
            self.ordered_sequence = []
        except Exception:
            pass

        try:
            self.operation_count = 0
        except Exception:
            pass

        self.start_location = start_location
        self.boundary = boundary
        self.exploration_mode = exploration_mode
        self.is_initialized = True

        try:
            if existing_catalog is not None:
                self._road_nodes_catalog = existing_catalog
        except Exception:
            pass
        
        print(f"路径记忆系统初始化完成: 起始位置={start_location}, 模式={exploration_mode}")

    def append_sequence_item(self, item_type: str, data: Dict) -> None:
        try:
            item = {"type": str(item_type), "data": data or {}, "timestamp": datetime.now().isoformat()}
            self.ordered_sequence.append(item)
        except Exception:
            pass

    def get_ordered_sequence(self) -> List[Dict]:
        try:
            return list(self.ordered_sequence)
        except Exception:
            return []

    # ===== 路径单元数据结构与API =====
    class RelativePosition:
        def __init__(self, direction: Optional[float], distance: Optional[float]):
            self.direction = direction
            self.distance = distance

    class RouteNode:
        def __init__(self, name: str, relative_position: Optional[Dict] = None):
            self.name = name
            # 期望结构：{"direction": 度数, "distance": 米}
            if relative_position and isinstance(relative_position, dict):
                self.relative_position = PathMemoryManager.RelativePosition(
                    relative_position.get("direction"),
                    relative_position.get("distance")
                )
            else:
                self.relative_position = PathMemoryManager.RelativePosition(None, None)

    class PathUnit:
        def __init__(
            self,
            path_id: str,
            path_sequence: int,
            start_poi_name: str,
            end_poi_name: str,
            visibility_info: Optional[Dict],
            route_nodes: Optional[List["PathMemoryManager.RouteNode"]],
            total_distance_meters: float,
            exploration_time_seconds: float,
            created_at: Optional[datetime] = None,
        ):
            self.path_id = path_id
            self.path_sequence = path_sequence
            self.start_poi_name = start_poi_name
            self.end_poi_name = end_poi_name
            # visibility_info 期望包含 {"visible_pois": [{"name":..., "relative_position":{direction, distance}}], ...}
            self.visibility_info = visibility_info or {"visible_pois": []}
            self.route_nodes = route_nodes or []
            self.total_distance_meters = total_distance_meters or 0
            self.exploration_time_seconds = exploration_time_seconds or 0
            self.created_at = created_at or datetime.now()

    def create_path_unit(
        self,
        start_poi_name: str,
        end_poi_name: str,
        start_poi_visible_list: List[Dict],
        route_nodes: Optional[List[Dict]],
        total_distance_meters: float,
        exploration_time_seconds: float,
    ) -> "PathUnit":
        """创建并记录一个路径单元（起点POI->终点POI）。

        仅记录：
        - 起点POI视野范围内的POI（名称+相对方向/距离）
        - 途径点（道路节点或途径POI）的链式相对位置（名称+方向/距离）；如果无途径点则为空
        - 距离与时间
        """
        try:
            self._path_unit_sequence += 1
            pu_id = f"path_unit_{uuid.uuid4()}"

            # 构造visibility_info
            visibility_info = {
                "visible_pois": []
            }
            for vp in (start_poi_visible_list or [])[:10]:
                name = (vp.get("name") if isinstance(vp, dict) else None) or "POI"
                rp = vp.get("relative_position") if isinstance(vp, dict) else None
                direction = None
                distance = None
                if isinstance(rp, dict):
                    direction = rp.get("direction")
                    distance = rp.get("distance")
                if name and direction is not None and distance is not None:
                    visibility_info["visible_pois"].append({
                        "name": name,
                        "relative_position": {"direction": direction, "distance": distance}
                    })

            # 构造route_nodes
            route_nodes_objs: List[PathMemoryManager.RouteNode] = []
            if isinstance(route_nodes, list):
                for n in route_nodes:
                    try:
                        label = n.get("name") if isinstance(n, dict) else None
                        rel = n.get("relative_position") if isinstance(n, dict) else None
                        if label:
                            route_nodes_objs.append(PathMemoryManager.RouteNode(label, rel))
                    except Exception:
                        continue

            pu = PathMemoryManager.PathUnit(
                path_id=pu_id,
                path_sequence=self._path_unit_sequence,
                start_poi_name=start_poi_name,
                end_poi_name=end_poi_name,
                visibility_info=visibility_info,
                route_nodes=route_nodes_objs,
                total_distance_meters=float(total_distance_meters or 0),
                exploration_time_seconds=float(exploration_time_seconds or 0),
                created_at=datetime.now(),
            )

            self.path_units.append(pu)
            try:
                # print(f"[DEBUG] create_path_unit: route_nodes_count={len(route_nodes_objs)} names={[getattr(x,'name',None) for x in route_nodes_objs]}", flush=True)
                pass
            except Exception:
                pass
            # 同步写入磁盘
            try:
                pu_dict = self._path_unit_to_dict(pu)
                _ = pu_dict
            except Exception as e:
                pass
            print(f"✅ 记录路径单元: {start_poi_name} -> {end_poi_name} (序号 {pu.path_sequence})")
            return pu
        except Exception as e:
            print(f"❌ 记录路径单元失败: {e}")
            # 返回一个最小结构，避免中断
            pu = PathMemoryManager.PathUnit(
                path_id=f"path_unit_{uuid.uuid4()}",
                path_sequence=self._path_unit_sequence,
                start_poi_name=start_poi_name or "起点POI",
                end_poi_name=end_poi_name or "终点POI",
                visibility_info={"visible_pois": []},
                route_nodes=[],
                total_distance_meters=float(total_distance_meters or 0),
                exploration_time_seconds=float(exploration_time_seconds or 0),
                created_at=datetime.now(),
            )
            self.path_units.append(pu)
            return pu

    def get_all_path_units(self) -> List["PathUnit"]:
        """返回所有已记录的路径单元（字典结构）"""
        units: List[Dict] = []
        # 先加入内存中的路径单元（过滤测试数据）
        for pu in self.path_units:
            try:
                d = self._path_unit_to_dict(pu)
                sn = (d.get("start_poi_name") or "")
                en = (d.get("end_poi_name") or "")
                # 过滤包含“测试”字样的POI，避免测试污染真实输出
                if (isinstance(sn, str) and ("测试" in sn)) or (isinstance(en, str) and ("测试" in en)):
                    continue
                units.append(d)
            except Exception:
                continue

        # 再加载磁盘上的路径单元文件（过滤测试数据）
        # 默认不启用磁盘加载，避免跨区域/跨实验污染；仅在 auto_save=True 时启用
        if self.auto_save:
            try:
                if os.path.isdir(self.path_units_dir):
                    for fname in os.listdir(self.path_units_dir):
                        if not fname.endswith(".json"):
                            continue
                        if fname.startswith("path_unit_test_"):
                            continue
                        fpath = os.path.join(self.path_units_dir, fname)
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, dict) and data.get("path_id"):
                                sid = data.get("session_id") or ""
                                start_name = data.get("start_poi_name") or ""
                                end_name = data.get("end_poi_name") or ""
                                if isinstance(sid, str) and sid.startswith("test_session"):
                                    continue
                                if (isinstance(start_name, str) and ("测试POI" in start_name or "测试" in start_name)) or (isinstance(end_name, str) and ("测试POI" in end_name or "测试" in end_name)):
                                    continue
                                units.append(data)
            except Exception as e:
                print(f"⚠️ 加载磁盘路径单元失败: {e}")

        # 按序列排序，保持稳定输出
        try:
            units.sort(key=lambda x: int(x.get("path_sequence", 0)))
        except Exception:
            pass
        return units

    def get_exploration_stats(self) -> Dict:
        """基于路径单元的探索统计（后端期望的结构）"""
        try:
            poi_names = set()
            total_distance = 0.0
            total_time = 0.0
            total_route_nodes_named = 0
            for pu in self.path_units:
                if pu.start_poi_name:
                    poi_names.add(pu.start_poi_name)
                if pu.end_poi_name:
                    poi_names.add(pu.end_poi_name)
                total_distance += float(pu.total_distance_meters or 0)
                total_time += float(pu.exploration_time_seconds or 0)
                total_route_nodes_named += len([n for n in (pu.route_nodes or []) if getattr(n, 'name', None)])

            return {
                "total_pois_visited": len(poi_names),
                "total_road_nodes_visited": int(total_route_nodes_named),
                "total_distance_meters": int(round(total_distance)),
                "total_time_seconds": int(round(total_time)),
            }
        except Exception:
            return {
                "total_pois_visited": 0,
                "total_road_nodes_visited": 0,
                "total_distance_meters": 0,
                "total_time_seconds": 0,
            }

    def _path_unit_to_dict(self, pu: "PathUnit") -> Dict:
        """对象转为字典，符合后端期望结构"""
        route_nodes = []
        try:
            for n in (pu.route_nodes or []):
                route_nodes.append({
                    "name": getattr(n, "name", None),
                    "relative_position": {
                        "direction": getattr(getattr(n, "relative_position", None), "direction", None),
                        "distance": getattr(getattr(n, "relative_position", None), "distance", None),
                    }
                })
        except Exception:
            route_nodes = []

        return {
            "path_id": pu.path_id,
            "path_sequence": pu.path_sequence,
            "start_poi_name": pu.start_poi_name,
            "end_poi_name": pu.end_poi_name,
            "visibility_info": pu.visibility_info or {"visible_pois": []},
            "route_nodes": route_nodes,
            "total_distance_meters": pu.total_distance_meters or 0,
            "exploration_time_seconds": pu.exploration_time_seconds or 0,
            "created_at": pu.created_at.isoformat() if isinstance(pu.created_at, datetime) else pu.created_at,
        }

    def _ensure_path_units_dir(self) -> None:
        try:
            os.makedirs(self.path_units_dir, exist_ok=True)
        except Exception as e:
            print(f"⚠️ 创建路径单元目录失败: {e}")

    def build_graph_memory_snapshot(self) -> Dict:
        nodes = []
        edges = []
        relations = []
        poi_ids = set()
        road_node_ids = set()
        try:
            for key, conn in (self.poi_layer.poi_connections or {}).items():
                s = conn.get("start_poi", {})
                e = conn.get("end_poi", {})
                sid = s.get("id")
                eid = e.get("id")
                if sid:
                    poi_ids.add(sid)
                if eid:
                    poi_ids.add(eid)
        except Exception:
            pass
        try:
            for nid in (self.road_layer.node_to_segments or {}).keys():
                if isinstance(nid, str) and nid:
                    road_node_ids.add(nid)
        except Exception:
            pass
        try:
            for pid in poi_ids:
                nodes.append({"id": pid, "type": "poi"})
            for nid in road_node_ids:
                nodes.append({"id": nid, "type": "road_node"})
        except Exception:
            nodes = nodes
        try:
            for seg in (self.road_layer.road_segments or {}).values():
                rid = seg.get("segment_id") or seg.get("id")
                length = float(seg.get("length") or 0)
                f = seg.get("start_node")
                t = seg.get("end_node")
                if rid is not None and f is not None and t is not None:
                    edges.append({"road_id": rid, "length_m": int(round(length)), "from_id": f, "to_id": t})
        except Exception:
            edges = edges
        try:
            for conn in (self.poi_layer.poi_connections or {}).values():
                sp = conn.get("start_poi", {})
                ep = conn.get("end_poi", {})
                sid = sp.get("id")
                eid = ep.get("id")
                sl = sp.get("location")
                el = ep.get("location")
                dd = self._calc_distance(sl, el)
                deg = self._calc_direction_deg(sl, el)
                rid = f"poi_edge_{sid}_{eid}" if sid and eid else None
                if sid and eid and isinstance(dd, (int, float)) and isinstance(deg, (int, float)):
                    edges.append({"road_id": rid, "length_m": int(round(float(conn.get("actual_distance", dd) or dd))), "from_id": sid, "to_id": eid})
                    relations.append({"poi_a_id": sid, "poi_b_id": eid, "direction_deg": int(round(deg)), "distance_m": int(round(dd)), "road_id": rid})
        except Exception:
            relations = relations
        return {"nodes": nodes, "edges": edges, "poi_relations": relations}

    def build_map_memory_snapshot(self, boundary: List[List[float]], grid_size: int = 30) -> Dict:
        if not boundary or len(boundary) < 1:
            return {"nodes": [], "road_grid": {"grid_size": grid_size, "cells": []}}
        min_lat = min(p[0] for p in boundary)
        max_lat = max(p[0] for p in boundary)
        min_lng = min(p[1] for p in boundary)
        max_lng = max(p[1] for p in boundary)
        def to_ij(lat: float, lng: float) -> Tuple[int, int]:
            try:
                i = int((lat - min_lat) / max(1e-9, (max_lat - min_lat)) * (grid_size - 1))
                j = int((lng - min_lng) / max(1e-9, (max_lng - min_lng)) * (grid_size - 1))
                i = max(0, min(grid_size - 1, i))
                j = max(0, min(grid_size - 1, j))
                return i, j
            except Exception:
                return 0, 0
        nodes_out = []
        cells = set()
        try:
            poi_seen = set()
            for conn in (self.poi_layer.poi_connections or {}).values():
                for pe in (conn.get("start_poi", {}), conn.get("end_poi", {})):
                    pid = pe.get("id")
                    name = pe.get("name")
                    loc = pe.get("location")
                    if pid and isinstance(loc, (list, tuple)) and len(loc) >= 2 and pid not in poi_seen:
                        i, j = to_ij(float(loc[0]), float(loc[1]))
                        nodes_out.append({"id": pid, "name": name, "type": "poi", "i": i, "j": j})
                        poi_seen.add(pid)
        except Exception:
            pass
        try:
            def parse_node_latlng(nid: str) -> Optional[Tuple[float, float]]:
                try:
                    if isinstance(nid, str) and nid.startswith("node_"):
                        parts = nid.split("_")
                        if len(parts) >= 3:
                            lat = float(parts[1])
                            lng = float(parts[2])
                            return lat, lng
                except Exception:
                    return None
                return None
            road_node_seen = set()
            for seg in (self.road_layer.road_segments or {}).values():
                for nid in [seg.get("start_node"), seg.get("end_node")]:
                    ll = parse_node_latlng(nid)
                    if ll and nid not in road_node_seen:
                        i, j = to_ij(ll[0], ll[1])
                        nodes_out.append({"id": str(nid), "name": str(nid), "type": "road_node", "i": i, "j": j})
                        road_node_seen.add(nid)
        except Exception:
            pass
        try:
            def raster_line(a: Tuple[float, float], b: Tuple[float, float]):
                i1, j1 = to_ij(a[0], a[1])
                i2, j2 = to_ij(b[0], b[1])
                di = abs(i2 - i1)
                dj = abs(j2 - j1)
                si = 1 if i1 < i2 else -1
                sj = 1 if j1 < j2 else -1
                err = di - dj
                ci, cj = i1, j1
                while True:
                    cells.add((ci, cj))
                    if ci == i2 and cj == j2:
                        break
                    e2 = 2 * err
                    if e2 > -dj:
                        err -= dj
                        ci += si
                    if e2 < di:
                        err += di
                        cj += sj
            for seg in (self.road_layer.road_segments or {}).values():
                coords = seg.get("coordinates") or []
                if isinstance(coords, list) and len(coords) >= 2:
                    for k in range(1, len(coords)):
                        a = coords[k-1]
                        b = coords[k]
                        try:
                            a_lat, a_lng = float(a[0]), float(a[1])
                            b_lat, b_lng = float(b[0]), float(b[1])
                        except Exception:
                            continue
                        raster_line((a_lat, a_lng), (b_lat, b_lng))
        except Exception:
            pass
        return {"nodes": nodes_out, "road_grid": {"grid_size": grid_size, "cells": [{"i": i, "j": j} for (i, j) in sorted(cells)]}}

    def _calc_distance(self, a: List[float], b: List[float]) -> float:
        try:
            import math
            lat1, lng1 = float(a[0]), float(a[1])
            lat2, lng2 = float(b[0]), float(b[1])
            R = 6371000.0
            dlat = math.radians(lat2 - lat1)
            dlng = math.radians(lng2 - lng1)
            s = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2)
            return 2 * R * math.asin(math.sqrt(max(0.0, min(1.0, s))))
        except Exception:
            return 0.0

    def _calc_direction_deg(self, a: List[float], b: List[float]) -> float:
        try:
            import math
            lat_diff = float(b[0]) - float(a[0])
            lng_diff = float(b[1]) - float(a[1])
            angle_rad = math.atan2(lng_diff, lat_diff)
            angle_deg = math.degrees(angle_rad)
            if angle_deg < 0:
                angle_deg += 360
            return angle_deg
        except Exception:
            return 0.0
    
    def set_road_nodes_catalog(self, nodes: List[Dict]) -> None:
        try:
            self._road_nodes_catalog = nodes or []
            try:
                # print(f"[DEBUG] 路节点目录注入: count={len(self._road_nodes_catalog)}", flush=True)
                pass
            except Exception:
                pass
        except Exception:
            self._road_nodes_catalog = []
    
    def _resolve_road_node_name(self, node_id: str, coords: Optional[List[float]] = None) -> str:
        try:
            lat, lng = None, None
            if isinstance(node_id, str) and node_id.startswith("node_"):
                parts = node_id.split("_")
                if len(parts) >= 3:
                    lat = float(parts[1]); lng = float(parts[2])
            if (lat is None or lng is None) and isinstance(coords, (list, tuple)) and len(coords) >= 2:
                lat = float(coords[0]); lng = float(coords[1])
            best_name, best_d = None, float("inf")
            catalog = getattr(self, "_road_nodes_catalog", []) or []
            for nd in catalog:
                name = nd.get("name") or nd.get("Name")
                if not name or (isinstance(name, str) and not name.strip()):
                    continue
                nlat, nlng = None, None
                if isinstance(nd.get("coordinates"), (list, tuple)) and len(nd["coordinates"]) >= 2:
                    nlng = float(nd["coordinates"][0]); nlat = float(nd["coordinates"][1])
                else:
                    loc = nd.get("location")
                    if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                        nlat = float(loc[0]); nlng = float(loc[1])
                    elif isinstance(loc, dict):
                        nlat = float(loc.get("latitude") or loc.get("lat") or 0.0)
                        nlng = float(loc.get("longitude") or loc.get("lng") or 0.0)
                if nlat is None or nlng is None or lat is None or lng is None:
                    continue
                d = self._calc_distance([lat, lng], [nlat, nlng])
                if d < best_d:
                    best_d = d; best_name = name
            return best_name or node_id
        except Exception:
            return node_id
    
    def _nearest_catalog_name(self, lat: float, lng: float, tolerance_m: float = 120.0) -> Optional[str]:
        try:
            best_name, best_d = None, float("inf")
            catalog = getattr(self, "_road_nodes_catalog", []) or []
            for nd in catalog:
                name = nd.get("name") or nd.get("Name")
                if not name or (isinstance(name, str) and not name.strip()):
                    continue
                nlat, nlng = None, None
                if isinstance(nd.get("coordinates"), (list, tuple)) and len(nd["coordinates"]) >= 2:
                    nlng = float(nd["coordinates"][0]); nlat = float(nd["coordinates"][1])
                else:
                    loc = nd.get("location")
                    if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                        nlat = float(loc[0]); nlng = float(loc[1])
                    elif isinstance(loc, dict):
                        nlat = float(loc.get("latitude") or loc.get("lat") or 0.0)
                        nlng = float(loc.get("longitude") or loc.get("lng") or 0.0)
                if nlat is None or nlng is None:
                    continue
                d = self._calc_distance([lat, lng], [nlat, nlng])
                if d < best_d:
                    best_d = d; best_name = name
            try:
                # print(f"[DEBUG] 最近具名节点: at=({lat:.6f},{lng:.6f}) -> {best_name} dist≈{int(best_d)}m tol={int(tolerance_m)}m", flush=True)
                pass
            except Exception:
                pass
            if best_d <= tolerance_m:
                return best_name
            return None
        except Exception:
            return None
    
    def record_exploration_path(self, from_location: List[float], to_location: List[float], 
                               action: str, notes: str = "") -> None:
        """记录探索路径（简化版本）
        
        Args:
            from_location: 起始位置 [纬度, 经度]
            to_location: 终点位置 [纬度, 经度]
            action: 动作类型
            notes: 备注信息
        """
        try:
            # 计算距离
            import math
            lat1, lng1 = from_location
            lat2, lng2 = to_location
            
            # 简化的距离计算
            lat_diff = lat2 - lat1
            lng_diff = lng2 - lng1
            distance = math.sqrt(lat_diff**2 + lng_diff**2) * 111000  # 转换为米
            
            # 创建路径数据
            path_data = {
                'start_location': from_location,
                'end_location': to_location,
                'nodes': [from_location, to_location],
                'segments': [{'start': from_location, 'end': to_location, 'distance': distance}],
                'poi_waypoints': [],
                'total_distance': distance,
                'action': action,
                'notes': notes,
                'timestamp': datetime.now().isoformat()
            }
            
            # 记录到节点层
            self.node_layer.record_node_sequence(
                nodes=path_data['nodes'],
                poi_waypoints=path_data['poi_waypoints'],
                start_location=path_data['start_location'],
                end_location=path_data['end_location'],
                total_distance=path_data['total_distance']
            )
            
            # 记录道路段到道路层
            self.road_layer.record_road_segment(
                start_node=tuple(from_location),
                end_node=tuple(to_location),
                segment_data={
                    'length': distance,
                    'road_type': action,
                    'coordinates': [from_location, to_location],
                    'notes': notes
                }
            )
            
            self._increment_operation_count()
            
        except Exception as e:
            print(f"记录探索路径时出错: {e}")
    
    def record_exploration_path_detailed(self, path_data: Dict) -> None:
        """记录详细探索路径 - AI记忆增强版本
        
        这个方法是AI探索系统的核心记忆功能，用于记录和存储AI在地图探索过程中的详细路径信息。
        AI需要理解并记住这个数据结构，以便在后续的探索和问答中使用这些信息。
        
        Args:
            path_data: 路径数据字典，包含以下关键信息：
                {
                    'start_location': [纬度, 经度] - 起始位置坐标
                        示例: [39.9042, 116.4074] (天安门广场)
                        
                    'end_location': [纬度, 经度] - 终点位置坐标  
                        示例: [39.9163, 116.3972] (故宫)
                        
                    'nodes': [节点列表] - 路径上的关键节点
                        示例: ['天安门东', '王府井', '故宫南门']
                        用途: 记录路径的关键转折点和重要位置
                        
                    'segments': [道路段列表] - 连接节点的道路段
                        示例: [
                            {'name': '东长安街', 'length': 500, 'type': '主干道'},
                            {'name': '王府井大街', 'length': 800, 'type': '商业街'}
                        ]
                        
                    'poi_waypoints': [途径POI列表] - 路径上经过的兴趣点
                        示例: [
                            {'name': '王府井百货', 'type': '购物', 'coordinates': [39.9097, 116.4109]},
                            {'name': '东华门', 'type': '古建筑', 'coordinates': [39.9186, 116.3969]}
                        ]
                        
                    'total_distance': 总距离(米) - 路径的总长度
                        示例: 1300.5
                        
                    'start_poi': 起始POI信息(可选) - 起点的POI详细信息
                        示例: {'name': '天安门广场', 'type': '广场', 'address': '东城区'}
                        
                    'end_poi': 终点POI信息(可选) - 终点的POI详细信息
                        示例: {'name': '故宫博物院', 'type': '博物馆', 'address': '东城区'}
                }
        
        AI记忆要点:
        1. 这个方法会将路径信息分层存储到三个记忆层：节点层、道路层、POI层
        2. 每次调用都会生成一个唯一的路径ID，用于后续查询和关联
        3. 路径信息会被用于回答空间关系、距离计算、路径规划等问题
        4. POI之间的连接关系会被记录，形成空间认知网络
        
        Returns:
            None - 但会在内部生成路径ID并存储到记忆系统中
        """
        try:
            # === 数据验证和格式化 ===
            validated_data = self._validate_and_format_path_data(path_data)
            
            # === 记录到节点记忆层 ===
            # 节点层负责记录路径的拓扑结构和节点序列
            path_id = self.node_layer.record_node_sequence(
                nodes=validated_data.get('nodes', []),
                poi_waypoints=validated_data.get('poi_waypoints', []),
                start_location=validated_data['start_location'],
                end_location=validated_data['end_location'],
                total_distance=validated_data.get('total_distance', 0)
            )
            
            # === 记录到道路记忆层 ===
            # 道路层负责记录具体的道路段信息和连接关系
            segments = validated_data.get('segments', [])
            for i, segment in enumerate(segments):
                segment_data = self._format_segment_data(segment, validated_data, i)
                start_node, end_node = self._determine_segment_nodes(validated_data, i)
                
                self.road_layer.record_road_segment(
                    start_node=start_node,
                    end_node=end_node,
                    segment_data=segment_data
                )
            
            # === 记录到POI记忆层 ===
            # POI层负责记录兴趣点之间的连接和空间关系
            self._record_poi_connections(validated_data, segments)
            
            # === 增强记忆存储 ===
            self._enhance_memory_storage(path_id, validated_data)

            # === 累积当前路径段的途径点与距离（用于之后生成路径单元）===
            try:
                segs = validated_data.get('segments') or []
                nodes_chain = []
                total_dist = 0.0
                last_latlng = None
                for i, seg in enumerate(segs):
                    sd = self._format_segment_data(seg, validated_data, i)
                    coords = sd.get('coordinates') or []
                    if not isinstance(coords, list) or len(coords) < 2:
                        continue
                    a = coords[0]; b = coords[1]
                    try:
                        a_lat, a_lng = float(a[0]), float(a[1])
                        b_lat, b_lng = float(b[0]), float(b[1])
                    except Exception:
                        continue
                    direction = sd.get('direction')
                    if direction is None:
                        direction = int(round(self._calc_direction_deg([a_lat, a_lng], [b_lat, b_lng])))
                    dist = float(sd.get('length', sd.get('distance', 0)) or 0.0)
                    if dist == 0.0:
                        dist = float(self._calc_distance([a_lat, a_lng], [b_lat, b_lng]) or 0.0)
                    # 直接从本地道路节点文件匹配具名节点（只要Name）
                    name_a = self._nearest_catalog_name(a_lat, a_lng)
                    name_b = self._nearest_catalog_name(b_lat, b_lng)
                    # 追加起点匹配
                    if name_a and (not nodes_chain or nodes_chain[-1].get('name') != name_a):
                        rp_dist = dist if last_latlng is None else int(round(self._calc_distance(last_latlng, [a_lat, a_lng])))
                        nodes_chain.append({'name': name_a, 'relative_position': {'direction': direction, 'distance': rp_dist}})
                        last_latlng = [a_lat, a_lng]
                        try:
                            # print(f"[DEBUG] 追加具名路点(start): name={name_a} dir={direction} dist≈{int(rp_dist)}m", flush=True)
                            pass
                        except Exception:
                            pass
                    # 追加终点匹配
                    if name_b and (not nodes_chain or nodes_chain[-1].get('name') != name_b):
                        nodes_chain.append({'name': name_b, 'relative_position': {'direction': direction, 'distance': int(round(dist))}})
                        last_latlng = [b_lat, b_lng]
                        try:
                            # print(f"[DEBUG] 追加具名路点(end): name={name_b} dir={direction} dist≈{int(round(dist))}m", flush=True)
                            pass
                        except Exception:
                            pass
                    total_dist += dist
                self._current_leg_route_nodes = nodes_chain
                self._current_leg_total_distance = total_dist
                try:
                    # print(f"[DEBUG] 当前段具名路点数={len(self._current_leg_route_nodes)} 总距离≈{int(round(self._current_leg_total_distance))}m", flush=True)
                    pass
                except Exception:
                    pass
            except Exception as e:
                print(f"⚠️ 累积路径段失败: {e}")
            
            try:
                end_loc = validated_data.get('end_location') or []
                name = f"路点_{end_loc[0]:.6f}_{end_loc[1]:.6f}" if isinstance(end_loc, list) and len(end_loc) >= 2 else "路点"
                self.append_sequence_item("road_node", {"name": name, "location": end_loc})
                for wp in (validated_data.get('poi_waypoints') or []):
                    self.append_sequence_item("poi_waypoint", wp)
            except Exception:
                pass
            
            self._increment_operation_count()
            print(f"✅ AI记忆系统: 成功记录探索路径 (ID: {path_id})")
            print(f"   📍 起点: {validated_data.get('start_location')}")
            print(f"   📍 终点: {validated_data.get('end_location')}")
            print(f"   📏 距离: {validated_data.get('total_distance', 0):.1f}米")
            print(f"   🗺️  节点数: {len(validated_data.get('nodes', []))}")
            print(f"   🏢 POI数: {len(validated_data.get('poi_waypoints', []))}")
            
        except Exception as e:
            print(f"❌ AI记忆系统错误: 记录探索路径失败 - {e}")
            # 记录错误但不中断程序运行
            self._log_memory_error("record_exploration_path_detailed", str(e), path_data)
    
    def _validate_and_format_path_data(self, path_data: Dict) -> Dict:
        """验证和格式化路径数据，确保AI能正确处理各种输入格式"""
        validated = {}
        
        # 验证必需字段
        required_fields = ['start_location', 'end_location']
        for field in required_fields:
            if field not in path_data:
                raise ValueError(f"缺少必需字段: {field}")
            
            # 确保坐标格式正确
            location = path_data[field]
            if not isinstance(location, list) or len(location) != 2:
                raise ValueError(f"{field} 必须是包含两个数字的列表 [纬度, 经度]")
            
            validated[field] = [float(location[0]), float(location[1])]
        
        # 格式化可选字段
        validated['nodes'] = path_data.get('nodes', [])
        validated['segments'] = path_data.get('segments', [])
        validated['poi_waypoints'] = path_data.get('poi_waypoints', [])
        validated['total_distance'] = float(path_data.get('total_distance', 0))
        validated['start_poi'] = path_data.get('start_poi')
        validated['end_poi'] = path_data.get('end_poi')
        
        return validated
    
    def _format_segment_data(self, segment: Any, path_data: Dict, index: int) -> Dict:
        """格式化道路段数据"""
        if isinstance(segment, dict):
            return segment
        else:
            # 为非字典格式的segment创建标准结构
            segments_count = len(path_data.get('segments', []))
            return {
                'length': path_data.get('total_distance', 0) / segments_count if segments_count > 0 else 0,
                'road_type': '探索路径',
                'coordinates': segment if isinstance(segment, list) else [],
                'segment_index': index,
                'exploration_timestamp': datetime.now().isoformat()
            }
    
    def _determine_segment_nodes(self, path_data: Dict, segment_index: int) -> Tuple[str, str]:
        """确定道路段的起终点节点"""
        nodes = path_data.get('nodes', [])
        
        if segment_index < len(nodes) - 1:
            start_node = str(nodes[segment_index]) if nodes else f"node_{segment_index}"
            end_node = str(nodes[segment_index + 1]) if segment_index + 1 < len(nodes) else f"node_{segment_index+1}"
        else:
            start_node = f"segment_start_{segment_index}"
            end_node = f"segment_end_{segment_index}"
        
        return start_node, end_node
    
    def _record_poi_connections(self, path_data: Dict, segments: List) -> None:
        """记录POI之间的连接关系"""
        start_poi = path_data.get('start_poi')
        end_poi = path_data.get('end_poi')
        
        if start_poi and end_poi:
            self.poi_layer.record_poi_connection(
                start_poi=start_poi,
                end_poi=end_poi,
                path_data={
                    'actual_distance': path_data.get('total_distance', 0),
                    'nodes': path_data.get('nodes', []),
                    'segments': segments,
                    'poi_waypoints': path_data.get('poi_waypoints', []),
                    'exploration_timestamp': datetime.now().isoformat()
                }
            )
    
    def _enhance_memory_storage(self, path_id: str, path_data: Dict) -> None:
        """增强记忆存储 - 为AI提供更好的记忆检索能力"""
        # 创建记忆索引，便于AI快速检索相关路径
        memory_index = {
            'path_id': path_id,
            'start_location': path_data['start_location'],
            'end_location': path_data['end_location'],
            'distance': path_data.get('total_distance', 0),
            'node_count': len(path_data.get('nodes', [])),
            'poi_count': len(path_data.get('poi_waypoints', [])),
            'timestamp': datetime.now().isoformat(),
            'memory_tags': self._generate_memory_tags(path_data)
        }
        
        # 存储到内存索引（如果有的话）
        if hasattr(self, 'memory_index'):
            self.memory_index[path_id] = memory_index
    
    def _generate_memory_tags(self, path_data: Dict) -> List[str]:
        """生成记忆标签，帮助AI分类和检索路径信息"""
        tags = []
        
        # 基于距离的标签
        distance = path_data.get('total_distance', 0)
        if distance < 500:
            tags.append('短距离路径')
        elif distance < 2000:
            tags.append('中距离路径')
        else:
            tags.append('长距离路径')
        
        # 基于POI数量的标签
        poi_count = len(path_data.get('poi_waypoints', []))
        if poi_count == 0:
            tags.append('直接路径')
        elif poi_count <= 2:
            tags.append('简单路径')
        else:
            tags.append('复杂路径')
        
        # 基于节点数量的标签
        node_count = len(path_data.get('nodes', []))
        if node_count <= 2:
            tags.append('直线路径')
        else:
            tags.append('多节点路径')
        
        return tags
    
    def _log_memory_error(self, method_name: str, error_msg: str, data: Dict) -> None:
        """记录记忆系统错误，用于调试和改进"""
        error_log = {
            'timestamp': datetime.now().isoformat(),
            'method': method_name,
            'error': error_msg,
            'data_keys': list(data.keys()) if isinstance(data, dict) else str(type(data))
        }
        print(f"🔍 AI记忆调试: {error_log}")
    
    def record_poi_visit(self, poi_data, visit_details: Dict) -> str:
        """记录POI访问
        
        Args:
            poi_data: POI数据，可以是字典或字符串
            visit_details: 访问详情字典
            
        Returns:
            访问记录ID
        """
        try:
            # 处理POI数据
            if isinstance(poi_data, str):
                # 如果是字符串，创建基本POI信息
                poi_id = poi_data
                poi_name = poi_data
                poi_type = '未知类型'
                location = [0, 0]
            elif isinstance(poi_data, dict):
                # 如果是字典，提取信息
                poi_id = poi_data.get('id', str(uuid.uuid4()))
                poi_name = poi_data.get('name', '未知POI')
                poi_type = poi_data.get('type', '未知类型')
                location = poi_data.get('location', [0, 0])
            else:
                # 其他类型，转换为字符串处理
                poi_id = str(poi_data)
                poi_name = str(poi_data)
                poi_type = '未知类型'
                location = [0, 0]
            
            visit_id = f"visit_{uuid.uuid4()}"
            try:
                if hasattr(self.poi_layer, 'record_poi_visit'):
                    visit_id = self.poi_layer.record_poi_visit(
                        poi_id=poi_id,
                        poi_name=poi_name,
                        poi_type=poi_type,
                        location=location,
                        visit_time=visit_details.get('visit_time', datetime.now().isoformat()),
                        interest_level=visit_details.get('interest_level', 5),
                        notes=visit_details.get('notes', ''),
                        approach_path=visit_details.get('approach_path', [])
                    )
                else:
                    try:
                        # print(f"[DEBUG] POI层不支持record_poi_visit，使用回退ID: {visit_id}", flush=True)
                        pass
                    except Exception:
                        pass
            except Exception as e:
                try:
                    print(f"⚠️ POI层记录失败，继续流程: {e}", flush=True)
                except Exception:
                    pass
            
            # 在访问POI时，基于上一个已访问POI创建路径单元；首个POI仅作为起点并重置累积
            try:
                if hasattr(self, '_last_poi_visit') and self._last_poi_visit is not None:
                    # 正常路径单元：上一个POI -> 当前POI
                    start_poi_name = self._last_poi_visit.get('poi_name') or self._last_poi_visit.get('id') or '未知起点'
                    end_poi_name = poi_name
                    # 使用上一个POI的视野快照，确保“起点POI视野范围”正确
                    start_visible = self._last_poi_visit.get('visible_snapshot', []) or []
                    # 使用当前累积的路径节点与距离（从上一个POI到当前POI的路段）
                    self.create_path_unit(
                        start_poi_name=start_poi_name,
                        end_poi_name=end_poi_name,
                        start_poi_visible_list=start_visible,
                        route_nodes=getattr(self, '_current_leg_route_nodes', []),
                        total_distance_meters=float(getattr(self, '_current_leg_total_distance', 0.0) or 0.0),
                        exploration_time_seconds=0.0,
                    )
                    # 重置当前路径段累积，为下一段做准备
                    self._current_leg_route_nodes = []
                    self._current_leg_total_distance = 0.0
                else:
                    # 首个POI：不要生成道路->POI的路径单元；清空累积，后续开始累积POI->POI
                    self._current_leg_route_nodes = []
                    self._current_leg_total_distance = 0.0

                # 更新最后一次POI访问，保存可见快照以供下一条路径使用
                self._last_poi_visit = {
                    'id': poi_id,
                    'poi_name': poi_name,
                    'location': location,
                    'visit_time': visit_details.get('visit_time', datetime.now().isoformat()),
                    'visible_snapshot': visit_details.get('visible_snapshot', []) or []
                }
            except Exception as e:
                print(f"⚠️ 在POI访问后创建路径单元失败: {e}")

            try:
                self.append_sequence_item("poi_visit", {
                    "id": poi_id,
                    "name": poi_name,
                    "location": location,
                    "visit_time": (visit_details.get('visit_time') if isinstance(visit_details.get('visit_time'), str) else datetime.now().isoformat()),
                    "interest_level": visit_details.get('interest_level'),
                    "notes": visit_details.get('notes'),
                    "location_when_visited": visit_details.get('location_when_visited'),
                    "visible_snapshot": visit_details.get('visible_snapshot') or [],
                    "approach_path": visit_details.get('approach_path') or {}
                })
                try:
                    # print(f"[DEBUG] ordered_sequence append poi_visit: name={poi_name}, id={poi_id}", flush=True)
                    # print(f"[DEBUG] ordered_sequence current length={len(self.ordered_sequence)}", flush=True)
                    pass
                except Exception:
                    pass
            except Exception:
                pass
            self._increment_operation_count()
            try:
                # print(f"[DEBUG] 记录POI访问完成: poi={poi_name} visit_id={visit_id}", flush=True)
                pass
            except Exception:
                pass
            return visit_id
            
        except Exception as e:
            print(f"记录POI访问时出错: {e}")
            return ""
    
    def record_road_traversal(self, start_node: Tuple[float, float], end_node: Tuple[float, float], 
                             road_type: str = "unknown", length: float = 0) -> None:
        """记录道路通行（简化版本）
        
        Args:
            start_node: 起始节点 (经度, 纬度)
            end_node: 终点节点 (经度, 纬度)
            road_type: 道路类型
            length: 道路长度
        """
        try:
            segment_data = {
                'length': length,
                'road_type': road_type,
                'coordinates': [start_node, end_node],
                'timestamp': datetime.now().isoformat()
            }
            
            self.road_layer.record_road_segment(
                start_node=start_node,
                end_node=end_node,
                segment_data=segment_data
            )
            
            self._increment_operation_count()
            
        except Exception as e:
            print(f"记录道路通行时出错: {e}")
    
    def record_road_traversal_detailed(self, road_segments: List[Dict]) -> None:
        """记录详细道路通行
        
        Args:
            road_segments: 道路段列表
        """
        try:
            for segment in road_segments:
                self.road_layer.record_road_segment(
                    start_node=segment.get('start_node', ''),
                    end_node=segment.get('end_node', ''),
                    segment_data=segment
                )
            
            self._increment_operation_count()
            print(f"记录道路通行: {len(road_segments)}个道路段")
            
        except Exception as e:
            print(f"记录道路通行时出错: {e}")
    
    def get_poi_connections(self, poi_id: str) -> List[Dict]:
        """获取POI连接
        
        Args:
            poi_id: POI ID
            
        Returns:
            连接列表
        """
        return self.poi_layer.get_poi_connections_from(poi_id)
    
    def get_node_paths_from_location(self, location: List[float]) -> List[Dict]:
        """获取从指定位置出发的节点路径
        
        Args:
            location: 位置 [纬度, 经度]
            
        Returns:
            路径列表
        """
        # 查找从该位置开始的路径
        matching_paths = []
        for path_info in self.node_layer.node_sequences.values():
            if self.node_layer._is_location_near(location, path_info['start_location'], 100):
                matching_paths.append(path_info)
        return matching_paths
    
    def get_road_info_by_type(self, road_type: str) -> List[Dict]:
        """根据道路类型获取道路信息
        
        Args:
            road_type: 道路类型
            
        Returns:
            道路信息列表
        """
        return self.road_layer.find_segments_by_road_type(road_type)
    
    def find_path_between_pois(self, poi_a_id: str, poi_b_id: str) -> Optional[Dict]:
        """查找POI间路径
        
        Args:
            poi_a_id: POI A的ID
            poi_b_id: POI B的ID
            
        Returns:
            路径信息或None
        """
        return self.poi_layer.find_shortest_path_between_pois(poi_a_id, poi_b_id)
    
    def get_spatial_relationships(self, location: List[float]) -> List[Dict]:
        """获取空间关系
        
        Args:
            location: 位置 [纬度, 经度]
            
        Returns:
            空间关系列表
        """
        # 简化实现：返回附近的POI连接
        nearby_pois = []
        for poi_id in self.poi_layer.poi_connections:
            connections = self.poi_layer.get_poi_connections_from(poi_id)
            if connections:
                nearby_pois.extend(connections)
        return nearby_pois[:10]  # 返回前10个
    
    def query_poi_connection(self, poi_a_id: str, poi_b_id: str) -> Optional[Dict]:
        """查询POI间连接
        
        Args:
            poi_a_id: POI A的ID
            poi_b_id: POI B的ID
            
        Returns:
            连接信息或None
        """
        return self.poi_layer.get_poi_distance(poi_a_id, poi_b_id)
    
    def query_node_path(self, path_id: str) -> Optional[Dict]:
        """查询节点路径
        
        Args:
            path_id: 路径ID
            
        Returns:
            路径信息或None
        """
        return self.node_layer.get_node_path(path_id)
    
    def query_road_info(self, segment_id: str) -> Optional[Dict]:
        """查询道路信息
        
        Args:
            segment_id: 道路段ID
            
        Returns:
            道路段信息或None
        """
        return self.road_layer.get_road_info(segment_id)
    
    def find_path_between_locations(self, start_location: List[float], 
                                  end_location: List[float]) -> Optional[Dict]:
        """查找两个位置间的路径
        
        Args:
            start_location: 起始位置 [纬度, 经度]
            end_location: 终点位置 [纬度, 经度]
            
        Returns:
            路径信息或None
        """
        # 在节点层查找路径
        paths = self.node_layer.find_paths_between_locations(
            start_location, end_location
        )
        
        if paths:
            # 返回最短路径
            shortest_path = min(paths, key=lambda x: x.get('total_distance', float('inf')))
            return shortest_path
        
        return None
    
    def find_paths_through_poi(self, poi_id: str) -> List[Dict]:
        """查找经过指定POI的路径
        
        Args:
            poi_id: POI ID
            
        Returns:
            路径列表
        """
        return self.node_layer.find_paths_with_poi(poi_id)
    
    def get_poi_spatial_relationships(self, poi_id: str) -> Dict:
        """获取POI的空间关系
        
        Args:
            poi_id: POI ID
            
        Returns:
            空间关系信息
        """
        # 获取POI连接
        connections = self.poi_layer.get_all_connected_pois(poi_id)
        
        # 获取经过该POI的路径
        paths = self.find_paths_through_poi(poi_id)
        
        return {
            'poi_id': poi_id,
            'connected_pois': connections,
            'paths_through': paths,
            'connection_count': len(connections),
            'path_count': len(paths)
        }
    
    def answer_path_question(self, question: str, context: Dict = None) -> str:
        """回答路径相关问题
        
        Args:
            question: 问题文本
            context: 上下文信息
            
        Returns:
            回答文本
        """
        try:
            # 简单的问题匹配和回答
            if "距离" in question or "多远" in question:
                return self._answer_distance_question(question, context)
            elif "路径" in question or "怎么走" in question:
                return self._answer_route_question(question, context)
            elif "经过" in question or "途径" in question:
                return self._answer_waypoint_question(question, context)
            else:
                return "抱歉，我还不能理解这个问题。请尝试询问关于距离、路径或途径的问题。"
                
        except Exception as e:
            return f"回答问题时出错: {e}"
    
    def _answer_distance_question(self, question: str, context: Dict = None) -> str:
        """回答距离相关问题"""
        # 这里可以实现更复杂的问题解析和回答逻辑
        stats = self.get_memory_stats()
        return f"根据我的记忆，我已经记录了{stats['poi_layer']['total_connections']}个POI连接，总共探索了{stats['node_layer']['total_distance']:.1f}米的路径。"
    
    def _answer_route_question(self, question: str, context: Dict = None) -> str:
        """回答路径相关问题"""
        stats = self.get_memory_stats()
        return f"我记录了{stats['node_layer']['total_paths']}条路径，包含{stats['road_layer']['total_segments']}个道路段。"
    
    def _answer_waypoint_question(self, question: str, context: Dict = None) -> str:
        """回答途径点相关问题"""
        stats = self.get_memory_stats()
        return f"在我的记忆中，有{stats['poi_layer']['unique_pois']}个不同的POI被记录。"
    
    def get_memory_stats(self) -> Dict:
        """获取整体记忆统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'poi_layer': self.poi_layer.get_memory_stats(),
            'node_layer': self.node_layer.get_memory_stats(),
            'road_layer': self.road_layer.get_memory_stats(),
            'total_operations': self.operation_count,
            'last_updated': datetime.now().isoformat()
        }
    
    def save_memory(self, filename: str = None) -> bool:
        """保存记忆到文件
        
        Args:
            filename: 文件名（可选）
            
        Returns:
            是否保存成功
        """
        try:
            if not filename:
                filename = f"path_memory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            filepath = os.path.join(self.data_dir, filename)
            
            memory_data = {
                'poi_connections': self.poi_layer.poi_connections,
                'node_sequences': self.node_layer.node_sequences,
                'road_segments': self.road_layer.road_segments,
                'metadata': {
                    'saved_time': datetime.now().isoformat(),
                    'operation_count': self.operation_count,
                    'stats': self.get_memory_stats()
                }
            }
            
            memory_data = memory_data
            
            return True
            
        except Exception as e:
            print(f"保存记忆时出错: {e}")
            return False
    
    def load_memory(self, filename: str) -> bool:
        """从文件加载记忆
        
        Args:
            filename: 文件名
            
        Returns:
            是否加载成功
        """
        try:
            filepath = os.path.join(self.data_dir, filename)
            
            if not os.path.exists(filepath):
                print(f"记忆文件不存在: {filepath}")
                return False
            
            with open(filepath, 'r', encoding='utf-8') as f:
                memory_data = json.load(f)
            
            # 恢复记忆数据
            self.poi_layer.poi_connections = memory_data.get('poi_connections', {})
            self.node_layer.node_sequences = memory_data.get('node_sequences', {})
            self.road_layer.road_segments = memory_data.get('road_segments', {})
            
            # 重建索引
            self._rebuild_indices()
            
            metadata = memory_data.get('metadata', {})
            self.operation_count = metadata.get('operation_count', 0)
            
            print(f"记忆已从文件加载: {filepath}")
            return True
            
        except Exception as e:
            print(f"加载记忆时出错: {e}")
            return False
    
    def _rebuild_indices(self):
        """重建索引"""
        # 重建节点层索引
        self.node_layer.node_to_paths.clear()
        for path_id, path_info in self.node_layer.node_sequences.items():
            for node_id in path_info.get('nodes', []):
                if node_id not in self.node_layer.node_to_paths:
                    self.node_layer.node_to_paths[node_id] = []
                self.node_layer.node_to_paths[node_id].append(path_id)
        
        # 重建道路层索引
        self.road_layer.node_to_segments.clear()
        for segment_id, segment_info in self.road_layer.road_segments.items():
            for node_id in [segment_info['start_node'], segment_info['end_node']]:
                if node_id not in self.road_layer.node_to_segments:
                    self.road_layer.node_to_segments[node_id] = []
                if segment_id not in self.road_layer.node_to_segments[node_id]:
                    self.road_layer.node_to_segments[node_id].append(segment_id)
    
    def _increment_operation_count(self):
        """增加操作计数并检查是否需要自动保存"""
        self.operation_count += 1
        
        if self.auto_save and self.operation_count % self.save_interval == 0:
            self.save_memory()
    
    def clear_all_memory(self) -> None:
        """清空所有记忆"""
        self.poi_layer.clear_memory()
        self.node_layer.clear_memory()
        self.road_layer.clear_memory()
        self.operation_count = 0
        print("所有路径记忆已清空")
