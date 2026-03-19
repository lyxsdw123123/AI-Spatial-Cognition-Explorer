# FastAPI后端主服务

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncio
import json
import os
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import Config
from backend.agent import ExplorerAgent
from backend.map_service import MapServiceManager
from backend.data_service.local_data_service import LocalDataService
from backend.map_api import router as map_router
from backend.evaluation_api import router as evaluation_router
from backend.evaluation_agent import EvaluationAgent
from backend.question_generator import EvaluationQuestions

# 最新的新格式探索数据（无经纬度与POI类型），供前端/API读取
latest_new_exploration_data = None
# 最新一次停止探索时生成的上下文缓存（确保评估与停止时一致）
last_context_text = None
last_context_mode = None

app = FastAPI(title="AI地图探索后端服务", version="1.0.0")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含地图服务API路由
app.include_router(map_router)
# 包含评估API路由
app.include_router(evaluation_router)

# 全局变量

explorer_agent = ExplorerAgent()
map_service_manager = MapServiceManager()
local_data_service = LocalDataService()
connected_clients = set()
current_exploration_task = None

# 数据模型
class LocationModel(BaseModel):
    latitude: float
    longitude: float

class BoundaryModel(BaseModel):
    points: List[LocationModel]

class InitExplorationModel(BaseModel):
    start_location: LocationModel
    boundary: BoundaryModel
    use_local_data: bool = False
    exploration_mode: str = "随机POI探索"
    memory_mode: Optional[str] = None
    max_rounds: int = 1
    model_provider: str = "qwen"

class POIQueryModel(BaseModel):
    location: LocationModel
    radius: int = 1000
    poi_type: str = ""

class QuestionModel(BaseModel):
    question: str

class SwitchRegionModel(BaseModel):
    region_name: str

# WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # 连接已断开，移除
                self.active_connections.remove(connection)

manager = ConnectionManager()

@app.get("/")
async def root():
    """根路径"""
    return {"message": "AI地图探索后端服务正在运行"}

@app.get("/config")
async def get_config():
    """获取配置信息"""
    return Config.get_config()

@app.post("/poi/search")
async def search_poi(query: POIQueryModel):
    """搜索POI"""
    try:
        location = (query.location.latitude, query.location.longitude)
        pois = await map_service_manager.get_poi_around_async(
            location, query.radius, query.poi_type
        )
        return {
            "success": True,
            "data": pois,
            "count": len(pois)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/poi/polygon")
async def search_poi_in_polygon(boundary: BoundaryModel):
    """在多边形区域内搜索POI"""
    try:
        polygon = [(point.latitude, point.longitude) for point in boundary.points]
        pois = map_service_manager.get_poi_in_polygon(polygon)
        return {
            "success": True,
            "data": pois,
            "count": len(pois)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/exploration/local_pois")
async def get_local_pois():
    """获取本地POI数据"""
    try:
        if not hasattr(local_data_service, 'poi_data') or local_data_service.poi_data is None:
            local_data_service.load_poi_data()
        
        # 将GeoDataFrame转换为前端可用的格式
        pois = []
        if local_data_service.poi_data is not None:
            for idx, row in local_data_service.poi_data.iterrows():
                poi = {
                    "name": row.get('name', f'POI_{idx}'),
                    "type": row.get('type', '未知'),
                    "location": {
                        "latitude": row.geometry.y,
                        "longitude": row.geometry.x
                    },
                    "address": row.get('address', ''),
                    "id": str(idx)
                }
                pois.append(poi)
        
        return {
            "success": True,
            "data": pois,
            "count": len(pois)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/exploration/local_roads")
async def get_local_roads():
    """获取本地道路数据"""
    try:
        if not hasattr(local_data_service, 'roads_gdf') or local_data_service.roads_gdf is None:
            local_data_service.load_road_data()
        
        # 使用LocalDataService的get_road_data方法
        roads = local_data_service.get_road_data()
        
        return {
            "success": True,
            "data": roads,
            "count": len(roads)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/exploration/init")
async def init_exploration(init_data: InitExplorationModel):
    """初始化探索"""
    try:
        start_location = (init_data.start_location.latitude, init_data.start_location.longitude)
        boundary = [(point.latitude, point.longitude) for point in init_data.boundary.points]
        
        # 如果提供记忆模式，设置到代理
        try:
            if init_data.memory_mode:
                # print(f"[DEBUG] /exploration/init memory_mode={init_data.memory_mode}")
                explorer_agent.set_memory_mode(init_data.memory_mode)
                # print(f"[DEBUG] /exploration/init 设置后代理模式={getattr(explorer_agent,'memory_mode','context')}")
        except Exception:
            pass

        try:
            if getattr(explorer_agent, 'memory_mode', 'context') == 'map':
                gb, gs = local_data_service.get_grid_boundary_and_size()
                if gb:
                    boundary = gb
        except Exception:
            pass

        # 如果使用本地数据模式，初始化本地数据服务
        if init_data.use_local_data:
            # 加载本地道路和POI数据
            local_data_service.load_road_data()
            local_data_service.load_poi_data()
            # 加载道路节点数据（用于路径记忆功能）
            local_data_service.load_road_nodes_data()
            try:
                # 注入道路节点目录到路径记忆管理器（确保探索过程中即可生成具名途径点）
                nodes = local_data_service.get_road_nodes_data()
                if nodes and getattr(explorer_agent, 'path_memory', None):
                    explorer_agent.path_memory.set_road_nodes_catalog(nodes)
                    try:
                        # print(f"[DEBUG] /exploration/init 已注入本地道路节点数据: count={len(nodes)}", flush=True)
                        pass
                    except Exception:
                        pass
            except Exception:
                pass
            
            # 将探索模式传递给AI代理
            await explorer_agent.initialize(start_location, boundary, 
                                          use_local_data=True, 
                                          exploration_mode=init_data.exploration_mode,
                                          local_data_service=local_data_service,
                                          max_rounds=init_data.max_rounds,
                                          model_provider=init_data.model_provider)
        else:
            await explorer_agent.initialize(start_location, boundary, 
                                          use_local_data=False,
                                          exploration_mode=init_data.exploration_mode,
                                          max_rounds=init_data.max_rounds,
                                          model_provider=init_data.model_provider)
        
        return {
            "success": True,
            "message": "探索初始化成功",
            "start_location": start_location,
            "boundary": boundary,
            "use_local_data": init_data.use_local_data,
            "exploration_mode": init_data.exploration_mode,
            "memory_mode": getattr(explorer_agent, 'memory_mode', 'context'),
            "max_rounds": init_data.max_rounds,
            "model_provider": init_data.model_provider
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/exploration/switch_region")
async def switch_region(switch_data: SwitchRegionModel):
    """切换探索区域"""
    try:
        # 停止当前探索（如果正在进行）
        if explorer_agent.is_exploring:
            explorer_agent.stop_exploration()
        
        # 切换本地数据服务的区域
        success = local_data_service.switch_region(switch_data.region_name)
        
        if success:
            return {
                "success": True,
                "message": f"已切换到区域: {switch_data.region_name}",
                "region_name": switch_data.region_name
            }
        else:
            return {
                "success": False,
                "message": f"切换区域失败: {switch_data.region_name}"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/exploration/start")
async def start_exploration(payload: Dict = None):
    """开始探索"""
    try:
        try:
            if isinstance(payload, dict):
                # print(f"[DEBUG] /exploration/start payload.memory_mode={payload.get('memory_mode')}")
                raw = payload.get("memory_mode")
                if isinstance(raw, str):
                    mm = raw.strip().lower()
                    if mm in ("context", "graph", "map"):
                        explorer_agent.set_memory_mode(mm)
                        # print(f"[DEBUG] /exploration/start 设置后代理模式={getattr(explorer_agent,'memory_mode','context')}")
                    else:
                        pass
                        # print(f"[DEBUG] /exploration/start 无效模式: {mm}")
                else:
                    pass
                    # print(f"[DEBUG] /exploration/start 模式不是字符串: {raw}")
            else:
                pass
                # print(f"[DEBUG] /exploration/start payload不是dict: {type(payload)}")
        except Exception as e:
            # print(f"[DEBUG] /exploration/start 设置模式异常: {e}")
            pass
        if explorer_agent.is_exploring:
            return {"success": False, "message": "探索已在进行中"}
        
        # 在后台启动探索任务
        global current_exploration_task
        current_exploration_task = asyncio.create_task(exploration_task())
        
        return {
            "success": True,
            "message": "探索已开始",
            "use_local_data": getattr(explorer_agent, 'use_local_data', False),
            "exploration_mode": getattr(explorer_agent, 'exploration_mode', '随机POI探索'),
            "memory_mode": getattr(explorer_agent, 'memory_mode', 'context')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/exploration/stop")
async def stop_exploration():
    """停止探索"""
    try:
        # print("收到停止探索请求")
        
        # 无论是否正在探索，都尝试生成报告和停止逻辑
        # print("正在停止探索...")
        report = explorer_agent.stop_exploration()
        # print(f"探索已停止，生成报告: {report}")

        # 立即取消正在运行的探索任务（停止LLM思维链）
        global current_exploration_task
        if current_exploration_task and not current_exploration_task.done():
            print("正在取消探索任务以停止LLM思维链...", flush=True)
            current_exploration_task.cancel()
            try:
                await current_exploration_task
            except asyncio.CancelledError:
                print("探索任务已成功取消", flush=True)
            except Exception as e:
                print(f"取消探索任务时出错: {e}", flush=True)
        
        # 新增：打印探索上下文到终端
        try:
            agent = EvaluationAgent()
            
            # 构建探索数据（使用状态中的格式化路径）
            status = explorer_agent.get_current_status()
            formatted_path = status.get('exploration_path', [])
            current_location = status.get('current_location')
            
            # 如果状态中没有路径，尝试从探索报告中回退获取并转换为坐标列表
            try:
                if (not formatted_path) and isinstance(report, dict):
                    rep_path = report.get('exploration_path')
                    if isinstance(rep_path, list) and rep_path:
                        converted = []
                        for p in rep_path:
                            try:
                                if isinstance(p, (list, tuple)) and len(p) >= 2:
                                    converted.append([float(p[0]), float(p[1])])
                                elif isinstance(p, dict):
                                    loc = p.get('location')
                                    if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                                        converted.append([float(loc[0]), float(loc[1])])
                                    elif isinstance(loc, dict):
                                        plat = float(loc.get('latitude') or loc.get('lat') or 0.0)
                                        plng = float(loc.get('longitude') or loc.get('lng') or 0.0)
                                        converted.append([plat, plng])
                            except Exception:
                                continue
                        if converted:
                            formatted_path = converted
            except Exception:
                pass
            
            # 构建已访问POI详情
            visited_poi_ids = set(report.get('visited_pois', [])) if isinstance(report, dict) else set()
            available_pois = explorer_agent.mental_map.get('available_pois', [])
            visited_pois = [poi for poi in available_pois if poi.get('id') in visited_poi_ids]
            
            # 道路记忆摘要
            road_memory = explorer_agent.get_memory_summary() if hasattr(explorer_agent, 'get_memory_summary') else None
            
            # 新增：道路节点数据（用于在上下文中匹配节点名称）
            road_nodes_data = None
            try:
                if getattr(explorer_agent, 'use_local_data', False) and getattr(explorer_agent, 'local_data_service', None):
                    road_nodes_data = explorer_agent.local_data_service.get_road_nodes_data()
                    try:
                        if road_nodes_data and getattr(explorer_agent, 'path_memory', None):
                            explorer_agent.path_memory.set_road_nodes_catalog(road_nodes_data)
                            try:
                                # print(f"[DEBUG] 已注入本地道路节点数据: count={len(road_nodes_data)}", flush=True)
                                pass
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                road_nodes_data = None
            
            # 保留原有评估上下文所需的完整数据，避免损伤现有功能
            exploration_data = {
                'ai_location': current_location,
                'exploration_path': formatted_path,
                'visited_pois': visited_pois,
                'exploration_report': report,
                'road_memory': road_memory,
                'road_nodes_data': road_nodes_data
            }

            # 根据新文档构建无坐标、无POI类型的新数据结构（不影响原有功能）
            def _haversine_distance(a_lat, a_lng, b_lat, b_lng):
                try:
                    import math
                    R = 6371000.0
                    dlat = math.radians(b_lat - a_lat)
                    dlng = math.radians(b_lng - a_lng)
                    s = (math.sin(dlat/2)**2 + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(dlng/2)**2)
                    return 2 * R * math.asin(math.sqrt(max(0.0, min(1.0, s))))
                except Exception:
                    return 0.0

            def _direction(from_lat, from_lng, to_lat, to_lng):
                try:
                    import math
                    lat_diff = to_lat - from_lat
                    lng_diff = to_lng - from_lng
                    angle_rad = math.atan2(lng_diff, lat_diff)
                    angle_deg = math.degrees(angle_rad)
                    if angle_deg < 0:
                        angle_deg += 360
                    return round(angle_deg)
                except Exception:
                    return 0

            # 计算相对位置的route_points（采样前20个点，跳过第一个点）
            route_points = []
            try:
                mode = getattr(explorer_agent, 'memory_mode', 'context')
                # print(f"[DEBUG] 停止探索-当前代理模式: {mode}")
                context_text = None
                nodes_out = []
                edges_out = []
                if mode == 'graph':
                    snap = explorer_agent.path_memory.build_graph_memory_snapshot()
                    try:
                        nodes = snap.get('nodes', [])
                        edges = snap.get('edges', [])
                        rels = snap.get('poi_relations', [])
                        lines = []
                        lines.append("[模式]\n- type: graph")
                        lines.append("[数据约束]\n- nodes:{id,type}\n- edges:{road_id,length_m,from_id,to_id}\n- poi_relations:{poi_a_id,poi_b_id,direction_deg,distance_m,road_id}")
                        lines.append(f"[图节点汇总]\n- 节点数: {len(nodes)}\n- POI节点数: {len([n for n in nodes if (n.get('type')=='poi')])}\n- 道路节点数: {len([n for n in nodes if (n.get('type')=='road_node')])}")
                        lines.append("[图边列表]")
                        for e in edges[:50]:
                            lines.append(f"- road_id: {e.get('road_id')}, from: {e.get('from_id')}, to: {e.get('to_id')}, length: {int(e.get('length_m') or 0)}m")
                        lines.append("[POI相对关系]")
                        for r in rels[:50]:
                            rid = r.get('road_id')
                            rid_str = rid if rid else '无'
                            lines.append(f"- {r.get('poi_a_id')} → {r.get('poi_b_id')}: 方向 {int(r.get('direction_deg') or 0)}°，距离 ≈ {int(r.get('distance_m') or 0)}m，道路: {rid_str}")
                        lines.append("[回答规则]\n1) 仅使用图连通性与POI相对关系\n2) 路径比较按edges的length_m累加\n3) 方向使用direction_deg\n4) 输出不引入未提供字段")
                        context_text = "\n".join(lines)
                    except Exception:
                        context_text = ""
                elif mode == 'map':
                    grid_size = 30
                    try:
                        _gb, _gs = local_data_service.get_grid_boundary_and_size()
                        if _gs is not None:
                            grid_size = int(_gs)
                    except Exception:
                        pass
                    snap = explorer_agent.path_memory.build_map_memory_snapshot(explorer_agent.exploration_boundary or [], grid_size)
                    try:
                        nodes = snap.get('nodes', [])
                        grid = snap.get('road_grid', {}) or {}
                        cells = grid.get('cells', [])
                        # 计算真实单元栅格边长（米），基于边界与grid_size划分近似
                        try:
                            boundary = explorer_agent.exploration_boundary or []
                            min_lat = min([p[0] for p in boundary]) if boundary else 0.0
                            max_lat = max([p[0] for p in boundary]) if boundary else 1.0
                            min_lng = min([p[1] for p in boundary]) if boundary else 0.0
                            max_lng = max([p[1] for p in boundary]) if boundary else 1.0
                            lat_mid = (min_lat + max_lat) / 2.0
                            lng_mid = (min_lng + max_lng) / 2.0
                            div = int(grid.get('grid_size') or 30)
                            div = max(1, div - 1)
                            vert_m = _haversine_distance(min_lat, lng_mid, max_lat, lng_mid)
                            hori_m = _haversine_distance(lat_mid, min_lng, lat_mid, max_lng)
                            cell_h = (vert_m / div) if div > 0 else 0.0
                            cell_w = (hori_m / div) if div > 0 else 0.0
                            cell_len_m = int(round((cell_h + cell_w) / 2.0))
                        except Exception:
                            cell_len_m = None
                        lines = []
                        lines.append("[模式]\n- type: map")
                        lines.append("[数据约束]\n- nodes:{id,name,type,i,j}\n- road_grid:{grid_size,cells:[{i,j}]}")
                        lines.append(f"[栅格参数]\n- grid_size: {int(grid.get('grid_size') or 30)}")
                        lines.append(f"- grid_cell_size_m: {cell_len_m if isinstance(cell_len_m, int) else '未提供'}")
                        lines.append("[节点列表]")
                        for n in nodes[:100]:
                            lines.append(f"- {n.get('id')} ({n.get('name')}) [{n.get('type')}] @ ({int(n.get('i') or 0)},{int(n.get('j') or 0)})")
                        lines.append(f"[道路格子]\n- road_cells_count: {len(cells)}")
                        lines.append("- road_cells_sample:")
                        for c in cells[:100]:
                            lines.append(f"  - ({int(c.get('i') or 0)},{int(c.get('j') or 0)})")
                        lines.append("[回答规则]\n1) 仅使用(i,j)与cells\n2) 连通以cells为道路\n3) 相对位置以栅格差值\n4) 输出不引入未提供字段")
                        context_text = "\n".join(lines)
                    except Exception:
                        context_text = ""
                elif mode == 'context':
                    # 普通模式：使用路径单元记录格式
                    try:
                        lines = []
                        lines.append("[模式]\n- type: context")
                        lines.append("[数据约束]\n- 路径单元记录格式")
                        lines.append("[记忆方式]\n- 路径单元序列，每个单元包含起点POI、视野内POI、移动路径")
                        lines.append("[回答规则]\n1) 基于路径单元序列进行推理\n2) 使用相对方向和距离\n3) 按时间顺序分析探索过程")
                        context_text = "\n".join(lines)
                    except Exception:
                        context_text = ""
                # 此处不打印、不设置上下文；统一在后续根据当前模式构建一次并输出
            except Exception:
                pass
                sample_count = min(len(formatted_path), 20)
                for i in range(1, sample_count):
                    prev = formatted_path[i-1]
                    curr = formatted_path[i]
                    try:
                        plat, plng = float(prev[0]), float(prev[1])
                        clat, clng = float(curr[0]), float(curr[1])
                        rp = {
                            'point_type': 'road_node',
                            'relative_position': {
                                'direction': _direction(plat, plng, clat, clng),
                                'distance': round(_haversine_distance(plat, plng, clat, clng))
                            }
                        }
                        # 尝试匹配最近的具名道路节点，仅保留名称
                        try:
                            best_name, best_d = None, float('inf')
                            if isinstance(road_nodes_data, list):
                                for nd in road_nodes_data:
                                    # 仅考虑具名节点
                                    name = nd.get('name') or nd.get('Name')
                                    if not name or (isinstance(name, str) and not name.strip()):
                                        continue

                                    # 提取节点坐标以进行近邻匹配
                                    nlat, nlng = None, None
                                    if 'coordinates' in nd and isinstance(nd['coordinates'], (list, tuple)) and len(nd['coordinates']) >= 2:
                                        # coordinates为(lng, lat)
                                        nlng = float(nd['coordinates'][0])
                                        nlat = float(nd['coordinates'][1])
                                    else:
                                        loc = nd.get('location')
                                        if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                                            # 假定为[lat, lng]
                                            nlat = float(loc[0])
                                            nlng = float(loc[1])
                                        elif isinstance(loc, dict):
                                            nlat = float(loc.get('latitude') or loc.get('lat') or 0.0)
                                            nlng = float(loc.get('longitude') or loc.get('lng') or 0.0)

                                    if nlat is None or nlng is None:
                                        continue

                                    d = _haversine_distance(clat, clng, nlat, nlng)
                                    if d < best_d:
                                        best_d = d
                                        best_name = name
                                if best_name:
                                    rp['name'] = best_name
                        except Exception:
                            pass
                        route_points.append(rp)
                    except Exception:
                        continue
            except Exception:
                route_points = []

            # 构建起点/终点POI（仅保留id和name）
            start_poi_obj = None
            end_poi_obj = None
            try:
                if isinstance(visited_pois, list) and visited_pois:
                    start_poi = visited_pois[0]
                    end_poi = visited_pois[-1]
                    start_poi_obj = {
                        'id': start_poi.get('id'),
                        'name': start_poi.get('name')
                    }
                    end_poi_obj = {
                        'id': end_poi.get('id'),
                        'name': end_poi.get('name')
                    }
            except Exception:
                pass

            # 汇总信息（不包含total_paths）
            total_distance_meters = 0
            total_time_seconds = 0
            try:
                if isinstance(report, dict):
                    total_distance_meters = int(round(float(report.get('total_distance') or 0)))
                    total_time_seconds = int(round(float(report.get('exploration_time') or 0)))
            except Exception:
                pass

            total_road_nodes_named = len([rp for rp in route_points if isinstance(rp, dict) and rp.get('name')])
            total_pois_visited = 0
            try:
                total_pois_visited = len(set([p.get('id') for p in visited_pois if isinstance(p, dict) and p.get('id') is not None]))
            except Exception:
                pass

            # 道路节点数据（仅名称）
            nodes_with_names = []
            try:
                if isinstance(road_nodes_data, list):
                    for nd in road_nodes_data:
                        name = nd.get('name') or nd.get('Name')
                        if name and (not isinstance(name, str) or name.strip()):
                            nodes_with_names.append({'name': name})
                try:
                    # print(f"[DEBUG] 本地具名道路节点统计: count={len(nodes_with_names)}", flush=True)
                    pass
                except Exception:
                    pass
            except Exception:
                nodes_with_names = []

            # 从路径记忆管理器获取真实的多个路径单元
            exploration_paths = []
            try:
                path_memory = getattr(explorer_agent, 'path_memory', None)
                path_units = path_memory.get_all_path_units() if path_memory else []
            except Exception:
                path_units = []

            # 新增：构建按时间排序的 POI 序列，并以独立字段传递到上下文
            try:
                def _created_at_of(pu):
                    try:
                        if isinstance(pu, dict):
                            ca = pu.get('created_at')
                            if isinstance(ca, str):
                                try:
                                    return datetime.fromisoformat(ca)
                                except Exception:
                                    # 兼容不带微秒或时区的字符串
                                    return datetime.fromisoformat(ca.split('Z')[0])
                            return ca or datetime.now()
                        else:
                            ca = getattr(pu, 'created_at', None)
                            return ca or datetime.now()
                    except Exception:
                        return datetime.now()

                def build_time_ordered_pois(units, all_pois, visited_ids):
                    """按探索先后生成POI顺序：严格依据路径单元的序号。

                    规则：取首个路径单元的 start_poi_name 作为第一个POI；随后依次取每个单元的 end_poi_name。
                    说明：units 将按 path_sequence 排序，避免使用不稳定的 created_at。
                    """
                    if not units or not all_pois:
                        return []

                    # 按 path_sequence 排序（若缺失则按 0 处理）
                    try:
                        sorted_units = sorted(
                            units,
                            key=lambda pu: (pu.get('path_sequence') if isinstance(pu, dict) else getattr(pu, 'path_sequence', 0)) or 0
                        )
                    except Exception:
                        sorted_units = units

                    # 构建 name -> poi 映射（仅首个匹配，过滤空名）
                    name_to_poi = {}
                    for poi in all_pois:
                        try:
                            n = poi.get('name')
                            if isinstance(n, str) and n.strip() and n not in name_to_poi:
                                name_to_poi[n] = poi
                        except Exception:
                            continue

                    ordered_list = []
                    seen_ids = set()

                    # 第一个POI：最早路径单元的 start_poi_name
                    first_unit = sorted_units[0]
                    first_start = first_unit.get('start_poi_name') if isinstance(first_unit, dict) else getattr(first_unit, 'start_poi_name', None)
                    if first_start:
                        fp = name_to_poi.get(first_start)
                        if fp:
                            fid = fp.get('id')
                            if fid in visited_ids and fid not in seen_ids:
                                ordered_list.append(fp)
                                seen_ids.add(fid)

                    # 后续POI：按路径序的每个 end_poi_name
                    for pu in sorted_units:
                        e_name = pu.get('end_poi_name') if isinstance(pu, dict) else getattr(pu, 'end_poi_name', None)
                        if e_name:
                            poi = name_to_poi.get(e_name)
                            if poi:
                                pid = poi.get('id')
                                if pid in visited_ids and pid not in seen_ids:
                                    ordered_list.append(poi)
                                    seen_ids.add(pid)

                    return ordered_list

                time_ordered_pois = []
                try:
                    ip_list = []
                    if isinstance(report, dict):
                        ip_list = report.get('interesting_pois') or []
                    seen_ids = set()
                    for ip in ip_list:
                        try:
                            poi = ip.get('poi') or {}
                            pid = poi.get('id')
                            if pid is not None and pid in visited_poi_ids and pid not in seen_ids:
                                time_ordered_pois.append(poi)
                                seen_ids.add(pid)
                        except Exception:
                            continue
                except Exception:
                    time_ordered_pois = []

                if not time_ordered_pois and path_units:
                    time_ordered_pois = build_time_ordered_pois(path_units, available_pois, visited_poi_ids)

                exploration_data['time_ordered_pois'] = time_ordered_pois
            except Exception:
                # 构建失败保持原逻辑
                pass

            if path_units:
                for pu in path_units:
                    try:
                        # 兼容对象或字典的路径单元结构
                        if isinstance(pu, dict):
                            pu_id = pu.get('path_id', '') or ''
                            pu_seq = pu.get('path_sequence')
                            s_name = pu.get('start_poi_name')
                            e_name = pu.get('end_poi_name')
                            vis_info = pu.get('visibility_info', {}) or {}
                            route_nodes = pu.get('route_nodes', []) or []
                            pu_distance = int(round(float(pu.get('total_distance_meters', 0) or 0)))
                            pu_time = int(round(float(pu.get('exploration_time_seconds', 0) or 0)))
                            created_at_str = pu.get('created_at') or datetime.now().isoformat(timespec='seconds')
                        else:
                            pu_id = getattr(pu, 'path_id', '') or ''
                            pu_seq = getattr(pu, 'path_sequence', None)
                            s_name = getattr(pu, 'start_poi_name', None)
                            e_name = getattr(pu, 'end_poi_name', None)
                            vis_info = getattr(pu, 'visibility_info', {}) or {}
                            route_nodes = getattr(pu, 'route_nodes', []) or []
                            try:
                                pu_distance = int(round(float(getattr(pu, 'total_distance_meters', 0) or 0)))
                            except Exception:
                                pu_distance = 0
                            try:
                                pu_time = int(round(float(getattr(pu, 'exploration_time_seconds', 0) or 0)))
                            except Exception:
                                pu_time = 0
                            try:
                                created_at_dt = getattr(pu, 'created_at', None)
                                created_at_str = created_at_dt.isoformat(timespec='seconds') if created_at_dt else datetime.now().isoformat(timespec='seconds')
                            except Exception:
                                created_at_str = datetime.now().isoformat(timespec='seconds')

                        pu_name = f"路径{pu_seq}" if pu_seq is not None else "探索路径"

                        # 起点/终点POI，仅保留名称与ID（ID可能不可用）
                        start_poi_dict = {'id': None, 'name': s_name} if s_name else None
                        end_poi_dict = {'id': None, 'name': e_name} if e_name else None

                        # 起点视野范围（仅保留名称与相对位置）
                        vision_list = []
                        try:
                            visible_pois = vis_info.get('visible_pois') if isinstance(vis_info, dict) else getattr(vis_info, 'visible_pois', [])
                            if isinstance(visible_pois, list):
                                for vp in visible_pois[:10]:
                                    try:
                                        vname = vp.get('name') if isinstance(vp, dict) else getattr(vp, 'name', None)
                                        rp = vp.get('relative_position') if isinstance(vp, dict) else getattr(vp, 'relative_position', None)
                                        deg = None
                                        dist = None
                                        if rp is not None:
                                            if isinstance(rp, dict):
                                                deg = rp.get('direction')
                                                dist = rp.get('distance')
                                            else:
                                                deg = getattr(rp, 'direction', None)
                                                dist = getattr(rp, 'distance', None)
                                        if vname and deg is not None and dist is not None:
                                            vision_list.append({'name': vname, 'relative_position': {'direction': int(deg), 'distance': int(dist)}})
                                    except Exception:
                                        continue
                        except Exception:
                            vision_list = []

                        # 途径点（链式相对关系，仅保留名称与相对方向/距离）
                        route_points_list = []
                        try:
                            for node in route_nodes:
                                try:
                                    label = getattr(node, 'name', None)
                                    if not label and isinstance(node, dict):
                                        label = node.get('name')
                                    rel = getattr(node, 'relative_position', None)
                                    if rel is None and isinstance(node, dict):
                                        rel = node.get('relative_position')
                                    deg = None
                                    dist = None
                                    if rel is not None:
                                        if isinstance(rel, dict):
                                            deg = rel.get('direction')
                                            dist = rel.get('distance')
                                        else:
                                            deg = getattr(rel, 'direction', None)
                                            dist = getattr(rel, 'distance', None)
                                    if label and deg is not None and dist is not None:
                                        route_points_list.append({'name': label, 'relative_position': {'direction': int(deg), 'distance': int(dist)}})
                                except Exception:
                                    continue
                        except Exception:
                            route_points_list = []

                        exploration_paths.append({
                            'path_id': pu_id or f'path_{pu_seq or ""}',
                            'path_name': pu_name,
                            'start_poi': start_poi_dict,
                            'end_poi': end_poi_dict,
                            'start_poi_vision_range': vision_list,
                            'route_points': route_points_list,
                            'path_distance': pu_distance,
                            'path_time': pu_time,
                            'created_at': created_at_str
                        })
                    except Exception:
                        continue
            else:
                # 回退：若无路径记忆，则使用当前一次探索数据构建单一路径
                exploration_paths.append({
                    'path_id': 'path_001',
                    'path_name': '探索路径',
                    'start_poi': start_poi_obj,
                    'end_poi': end_poi_obj,
                    'start_poi_vision_range': [],
                    'route_points': route_points,
                    'path_distance': total_distance_meters,
                    'path_time': total_time_seconds,
                    'created_at': datetime.now().isoformat(timespec='seconds')
                })

            # 移除调试输出：路径单元统计

            # 汇总统计使用路径记忆的统计数据（保持结构不变）
            summary_stats = None
            try:
                if path_units:
                    summary_stats = explorer_agent.path_memory.get_exploration_stats()
            except Exception:
                summary_stats = None

            if summary_stats:
                total_pois_visited = int(summary_stats.get('total_pois_visited', 0))
                total_road_nodes_named = int(summary_stats.get('total_road_nodes_visited', 0))
                total_distance_meters = int(summary_stats.get('total_distance_meters', 0))
                total_time_seconds = int(summary_stats.get('total_time_seconds', 0))

            # ===== 新增：构建 POI点单元 与 完整行驶路径（不含经纬度/兴趣度） =====
            poi_units = []
            full_route = {"start_name": "起点", "segments": []}

            try:
                # 构建名称到POI对象的映射，便于方向/距离计算
                name_to_poi = {}
                try:
                    for poi in available_pois or []:
                        n = poi.get('name')
                        if isinstance(n, str) and n.strip() and n not in name_to_poi:
                            name_to_poi[n] = poi
                except Exception:
                    pass

                def _poi_coords(p):
                    try:
                        if isinstance(p, dict):
                            loc = p.get('location') or p.get('coordinates')
                            if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                                lat, lng = float(loc[0]), float(loc[1])
                                return lat, lng
                            if isinstance(loc, dict):
                                lat = float(loc.get('latitude') or loc.get('lat') or 0.0)
                                lng = float(loc.get('longitude') or loc.get('lng') or 0.0)
                                return lat, lng
                    except Exception:
                        pass
                    return None, None

                # 使用时间排序的POI（若可用），否则退回已访问POI
                ordered_pois = []
                try:
                    if 'time_ordered_pois' in exploration_data and isinstance(exploration_data['time_ordered_pois'], list):
                        ordered_pois = exploration_data['time_ordered_pois']
                except Exception:
                    ordered_pois = []
                if not ordered_pois:
                    ordered_pois = visited_pois or []

                try:
                    names_seq = [p.get('name') for p in ordered_pois if isinstance(p, dict)]
                    # print(f"[DEBUG] 时间序POI：{names_seq}", flush=True)
                except Exception:
                    pass

                # 构建 POI点单元：对每个POI，计算视野内其他POI的方向/距离（限定范围与数量）
                VISION_RANGE_M = 800
                MAX_VISIBLE = 8
                for idx, poi in enumerate(ordered_pois, start=1):
                    try:
                        pname = poi.get('name') or f"POI_{idx}"
                        plat, plng = _poi_coords(poi)
                        visible = []
                        # 若路径单元提供起点视野，则优先使用
                        # 通过在 exploration_paths 中查找对应的起点名称来匹配视野
                        matched_vision = None
                        try:
                            for ep in exploration_paths:
                                s = ep.get('start_poi') or {}
                                if s.get('name') == pname:
                                    vlist = ep.get('start_poi_vision_range') or []
                                    if isinstance(vlist, list) and vlist:
                                        matched_vision = vlist
                                        break
                        except Exception:
                            matched_vision = None

                        if matched_vision:
                            for vp in matched_vision[:MAX_VISIBLE]:
                                try:
                                    vname = vp.get('name')
                                    rp = vp.get('relative_position') or {}
                                    deg = rp.get('direction')
                                    dist = rp.get('distance')
                                    if vname and (deg is not None) and (dist is not None):
                                        visible.append({
                                            'name': vname,
                                            'direction_deg': int(deg),
                                            'distance_m': int(dist)
                                        })
                                except Exception:
                                    continue
                        else:
                            # 回退：按距离选取附近POI
                            candidates = []
                            for other in available_pois or []:
                                try:
                                    oname = other.get('name')
                                    if not oname or oname == pname:
                                        continue
                                    olat, olng = _poi_coords(other)
                                    if plat is None or plng is None or olat is None or olng is None:
                                        continue
                                    dist = int(round(_haversine_distance(plat, plng, olat, olng)))
                                    if dist <= VISION_RANGE_M:
                                        deg = _direction(plat, plng, olat, olng)
                                        candidates.append((oname, deg, dist))
                                except Exception:
                                    continue
                            # 最近优先，截断
                            candidates.sort(key=lambda x: x[2])
                            for oname, deg, dist in candidates[:MAX_VISIBLE]:
                                visible.append({
                                    'name': oname,
                                    'direction_deg': int(deg),
                                    'distance_m': int(dist)
                                })

                        poi_units.append({
                            'poi': {'name': pname},
                            'visible_pois': visible
                        })
                    except Exception:
                        continue

                full_start_name = None
                segments = []
                try:
                    seq = []
                    try:
                        seq = explorer_agent.path_memory.get_ordered_sequence()
                    except Exception:
                        seq = []
                    try:
                        # print(f"[DEBUG] ordered_sequence_len={len(seq)}", flush=True)
                        type_counts = {}
                        for it in seq:
                            t = it.get('type')
                            type_counts[t] = type_counts.get(t, 0) + 1
                        # print(f"[DEBUG] ordered_sequence type_counts={type_counts}", flush=True)
                    except Exception:
                        pass
                    poi_indices = []
                    for idx, item in enumerate(seq):
                        t = item.get('type')
                        if t == 'poi_visit':
                            poi_indices.append(idx)
                    try:
                        # print(f"[DEBUG] poi_indices={poi_indices}", flush=True)
                        pass
                    except Exception:
                        pass
                    def _item_coords(it):
                        d = it.get('data') or {}
                        loc = d.get('location')
                        if isinstance(loc, list) and len(loc) >= 2:
                            return float(loc[0]), float(loc[1])
                        coords = d.get('coordinates')
                        if isinstance(coords, list) and len(coords) >= 2:
                            return float(coords[0]), float(coords[1])
                        return None, None
                    def _item_name(it):
                        d = it.get('data') or {}
                        n = d.get('name') or d.get('id') or '未知'
                        return str(n)
                    def _nearest_node(lat: float, lng: float, tolerance_m: float = 120.0) -> Dict:
                        try:
                            best_name, best_d = None, float('inf')
                            best_coords = (None, None)
                            for nd in (road_nodes_data or []):
                                name = nd.get('name') or nd.get('Name')
                                if not name or (isinstance(name, str) and not name.strip()):
                                    continue
                                nlat, nlng = None, None
                                if isinstance(nd.get('coordinates'), (list, tuple)) and len(nd['coordinates']) >= 2:
                                    nlng = float(nd['coordinates'][0]); nlat = float(nd['coordinates'][1])
                                else:
                                    loc = nd.get('location')
                                    if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                                        nlat = float(loc[0]); nlng = float(loc[1])
                                    elif isinstance(loc, dict):
                                        nlat = float(loc.get('latitude') or loc.get('lat') or 0.0)
                                        nlng = float(loc.get('longitude') or loc.get('lng') or 0.0)
                                if nlat is None or nlng is None:
                                    continue
                                d = _haversine_distance(lat, lng, nlat, nlng)
                                if d < best_d:
                                    best_d = d; best_name = name; best_coords = (nlat, nlng)
                            if best_d <= tolerance_m:
                                return {'name': best_name, 'lat': best_coords[0], 'lng': best_coords[1], 'distance_m': int(round(best_d))}
                            return {}
                        except Exception:
                            return {}
                    if len(poi_indices) >= 1:
                        first_idx = poi_indices[0]
                        full_start_name = _item_name(seq[first_idx])
                    if len(poi_indices) >= 2:
                        for k in range(len(poi_indices) - 1):
                            a_idx = poi_indices[k]
                            b_idx = poi_indices[k+1]
                            prev_item = seq[a_idx]
                            prev_lat, prev_lng = _item_coords(prev_item)
                            seen_names = set()
                            for m in range(a_idx + 1, b_idx):
                                curr = seq[m]
                                c_name = _item_name(curr)
                                c_lat, c_lng = _item_coords(curr)
                                deg = None
                                dist = None
                                if None not in (prev_lat, prev_lng, c_lat, c_lng):
                                    t = curr.get('type')
                                    # 仅在道路节点时进行具名替换与真实坐标匹配；POI保持原名
                                    if t == 'road_node':
                                        matched = _nearest_node(c_lat, c_lng)
                                        if matched.get('name'):
                                            c_name = matched['name']
                                            # 使用真实坐标重新计算方向与距离
                                            deg = _direction(prev_lat, prev_lng, matched['lat'], matched['lng'])
                                            dist = int(round(_haversine_distance(prev_lat, prev_lng, matched['lat'], matched['lng'])))
                                            # 去重：同名道路节点仅保留一个
                                            if c_name in seen_names:
                                                prev_lat, prev_lng = matched['lat'], matched['lng']
                                                continue
                                            seen_names.add(c_name)
                                            segments.append({'to_name': c_name, 'direction_deg': deg, 'distance_m': dist, 'to_coords': {'lat': matched['lat'], 'lng': matched['lng']}})
                                            prev_lat, prev_lng = matched['lat'], matched['lng']
                                            continue
                                    # 非道路节点（如POI）或未命中匹配：按原坐标计算
                                    deg = _direction(prev_lat, prev_lng, c_lat, c_lng)
                                    dist = int(round(_haversine_distance(prev_lat, prev_lng, c_lat, c_lng)))
                                segments.append({'to_name': c_name, 'direction_deg': deg, 'distance_m': dist})
                                prev_lat, prev_lng = c_lat, c_lng
                            end_item = seq[b_idx]
                            end_name = _item_name(end_item)
                            end_lat, end_lng = _item_coords(end_item)
                            deg = None
                            dist = None
                            # 终点前的道路节点匹配
                            if None not in (prev_lat, prev_lng, end_lat, end_lng):
                                t = end_item.get('type')
                                # 如果终点也是道路节点（理论上不太可能，通常是POI，但作为防御性编程）
                                if t == 'road_node':
                                    matched = _nearest_node(end_lat, end_lng)
                                    if matched.get('name'):
                                        end_name = matched['name']
                                        deg = _direction(prev_lat, prev_lng, matched['lat'], matched['lng'])
                                        dist = int(round(_haversine_distance(prev_lat, prev_lng, matched['lat'], matched['lng'])))
                                        segments.append({'to_name': end_name, 'direction_deg': deg, 'distance_m': dist, 'to_coords': {'lat': matched['lat'], 'lng': matched['lng']}})
                                        # 更新前一个点为终点（虽然循环结束了，但保持一致性）
                                        prev_lat, prev_lng = matched['lat'], matched['lng']
                                        continue
                                
                                # 正常情况：终点是POI，或者未匹配到具名道路节点
                                deg = _direction(prev_lat, prev_lng, end_lat, end_lng)
                                dist = int(round(_haversine_distance(prev_lat, prev_lng, end_lat, end_lng)))
                            segments.append({'to_name': end_name, 'direction_deg': deg, 'distance_m': dist})
                    elif route_points:
                        full_start_name = '起点'
                        seen_names = set()
                        prev_lat, prev_lng = None, None
                        for rp in route_points:
                            rname = rp.get('name') or '道路节点'
                            rpinfo = rp.get('relative_position') or {}
                            # 基于名称匹配真实坐标，若未命中则保留原方向/距离
                            matched = None
                            # 优先用名称匹配坐标
                            for nd in (road_nodes_data or []):
                                name_nd = nd.get('name') or nd.get('Name')
                                if name_nd and rname == name_nd:
                                    nlat, nlng = None, None
                                    if isinstance(nd.get('coordinates'), (list, tuple)) and len(nd['coordinates']) >= 2:
                                        nlng = float(nd['coordinates'][0]); nlat = float(nd['coordinates'][1])
                                    else:
                                        loc = nd.get('location')
                                        if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                                            nlat = float(loc[0]); nlng = float(loc[1])
                                        elif isinstance(loc, dict):
                                            nlat = float(loc.get('latitude') or loc.get('lat') or 0.0)
                                            nlng = float(loc.get('longitude') or loc.get('lng') or 0.0)
                                    if nlat is not None and nlng is not None:
                                        matched = {'name': rname, 'lat': nlat, 'lng': nlng}
                                        break
                            if matched and matched['name'] in seen_names:
                                # 去重：同名节点跳过
                                continue
                            if matched:
                                # 计算真实方向与距离（若存在前一坐标）
                                if None not in (prev_lat, prev_lng):
                                    deg = _direction(prev_lat, prev_lng, matched['lat'], matched['lng'])
                                    dist = int(round(_haversine_distance(prev_lat, prev_lng, matched['lat'], matched['lng'])))
                                else:
                                    deg = rpinfo.get('direction')
                                    dist = rpinfo.get('distance')
                                segments.append({'to_name': matched['name'], 'direction_deg': deg, 'distance_m': dist, 'to_coords': {'lat': matched['lat'], 'lng': matched['lng']}})
                                prev_lat, prev_lng = matched['lat'], matched['lng']
                                seen_names.add(matched['name'])
                            else:
                                segments.append({'to_name': rname, 'direction_deg': rpinfo.get('direction'), 'distance_m': rpinfo.get('distance')})
                    else:
                        # 额外回退：若序列不可用但时间序POI存在，则直接按相邻POI构建段
                        try:
                            ordered_pois = exploration_data.get('time_ordered_pois') or []
                            if isinstance(ordered_pois, list) and len(ordered_pois) >= 2:
                                first = ordered_pois[0] or {}
                                full_start_name = first.get('name') or '起点'
                                for i in range(len(ordered_pois)-1):
                                    a = ordered_pois[i] or {}
                                    b = ordered_pois[i+1] or {}
                                    alat, alng = _poi_coords(a)
                                    blat, blng = _poi_coords(b)
                                    deg = None
                                    dist = None
                                    if None not in (alat, alng, blat, blng):
                                        deg = _direction(alat, alng, blat, blng)
                                        dist = int(round(_haversine_distance(alat, alng, blat, blng)))
                                    segments.append({'to_name': b.get('name') or '未知终点', 'direction_deg': deg, 'distance_m': dist})
                        except Exception:
                            pass
                    if full_start_name:
                        full_route['start_name'] = full_start_name
                except Exception:
                    pass

                full_route['segments'] = segments
            except Exception:
                # 构建新结构过程中出现异常时，使用默认空结构继续，避免影响后续流程
                pass

            new_exploration_data = {
                'poi_units': poi_units,
                'full_route': full_route,
                'exploration_paths': exploration_paths,
                'exploration_summary': {
                    'total_pois_visited': total_pois_visited,
                    'total_road_nodes_visited': total_road_nodes_named,
                    'total_distance_meters': total_distance_meters,
                    'total_time_seconds': total_time_seconds,
                    'reselect_start_count': int(getattr(explorer_agent, 'reselect_start_count', 0) or 0),
                    'round_index': int(getattr(explorer_agent, 'exploration_round', 1)),
                    'rounds_completed': int(getattr(explorer_agent, 'rounds_completed', 0))
                },
                'road_nodes_data': {
                    'nodes_with_names': nodes_with_names
                }
            }

            # 更新全局最新的新格式探索数据
            try:
                global latest_new_exploration_data
                latest_new_exploration_data = new_exploration_data
            except Exception:
                pass

            # 仅用于调试：如需检查新数据结构，可在终端打印（不影响原有上下文）
            # print("[新结构] exploration_data:", json.dumps(new_exploration_data, ensure_ascii=False)[:500], '...')
            
            # 在传递给评估代理的数据中加入新结构，便于其按路径单元生成上下文
            exploration_data['new_exploration_data'] = new_exploration_data

            # 构建注入上下文（context模式采用ordered_sequence生成完整行驶路径）
            try:
                mode = getattr(explorer_agent, 'memory_mode', 'context')
                if mode == 'context':
                    lines = []
                    lines.append("POI点单元记录（按时间顺序）：")
                    for idx, unit in enumerate(new_exploration_data.get('poi_units', []), start=1):
                        poi_name = (unit.get('poi') or {}).get('name') or f"POI_{idx}"
                        lines.append(f"{idx}) POI：{poi_name}")
                        vp_list = unit.get('visible_pois') or []
                        lines.append("   - 视野内POI（方向度数；距离米）：")
                        for vp in vp_list:
                            vn = vp.get('name')
                            vd = vp.get('direction_deg')
                            vm = vp.get('distance_m')
                            lines.append(f"     • {vn}：方向 {int(vd) if vd is not None else '未知'}°，距离 ≈ {int(vm) if vm is not None else '未知'}m")
                    fr = new_exploration_data.get('full_route', {})
                    lines.append("")
                    lines.append("完整行驶路径（仅方向与距离）：")
                    start_name = fr.get('start_name') or "起点"
                    poi_seq = []
                    try:
                        for unit in new_exploration_data.get('poi_units', []):
                            nm = ((unit.get('poi') or {}).get('name'))
                            if isinstance(nm, str) and nm.strip():
                                poi_seq.append(nm)
                    except Exception:
                        poi_seq = []
                    poi_idx_map = {nm: i + 1 for i, nm in enumerate(poi_seq)}
                    prefix_start = f"路径{poi_idx_map.get(start_name)} " if start_name in poi_idx_map else ""
                    lines.append(f"- {prefix_start}起点：{start_name}")
                    for seg in fr.get('segments', []):
                        to_name = seg.get('to_name') or "未知终点"
                        deg = seg.get('direction_deg')
                        dist = seg.get('distance_m')
                        deg_str = f"{int(deg)}°" if isinstance(deg, (int, float)) else "未知方向"
                        dist_str = f"≈ {int(dist)}m" if isinstance(dist, (int, float)) else "未知距离"
                        prefix_seg = ""
                        if to_name in poi_idx_map:
                            idx = poi_idx_map.get(to_name)
                            if isinstance(idx, int) and idx < len(poi_seq):
                                prefix_seg = f"路径{idx} "
                        lines.append(f"→ {prefix_seg}{to_name}（方向 {deg_str}，距离 {dist_str}）")
                    sm = new_exploration_data.get('exploration_summary', {})
                    lines.append("")
                    lines.append("总和：")
                    if sm.get('total_pois_visited') is not None:
                        lines.append(f"已访问POI数量：{int(sm.get('total_pois_visited'))}")
                    if sm.get('total_road_nodes_visited') is not None:
                        lines.append(f"已访问道路节点数量（只要Name字段的）：{int(sm.get('total_road_nodes_visited'))}")
                    if sm.get('total_distance_meters') is not None:
                        lines.append(f"总探索距离：{int(sm.get('total_distance_meters'))}米")
                    if sm.get('total_time_seconds') is not None:
                        lines.append(f"探索时间：{int(sm.get('total_time_seconds'))}秒")
                    if sm.get('reselect_start_count') is not None:
                        lines.append(f"重新起点次数：{int(sm.get('reselect_start_count'))}")
                    exploration_data['context_text'] = "\n".join(lines)
                    exploration_data['context_mode'] = 'context'
                elif mode == 'raw':
                    # 原始记忆模式：直接使用LangChain的原始对话历史文本
                    try:
                        raw_history = explorer_agent.get_raw_memory_text()
                        exploration_data['context_text'] = raw_history
                        exploration_data['context_mode'] = 'raw'
                    except Exception as e:
                        print(f"[ERROR] raw模式获取历史失败: {e}")
                        exploration_data['context_text'] = "Error: Failed to retrieve raw conversation history."
                        exploration_data['context_mode'] = 'raw'
                elif mode == 'graph':
                    poi_units = new_exploration_data.get('poi_units', [])
                    paths = new_exploration_data.get('exploration_paths', [])
                    # 仅限当前时间序POI参与图构建，避免历史或无关POI混入
                    allowed_poi_names = set()
                    try:
                        for unit in poi_units:
                            pn = ((unit.get('poi') or {}).get('name'))
                            if isinstance(pn, str) and pn.strip():
                                allowed_poi_names.add(pn)
                    except Exception:
                        allowed_poi_names = set()
                    filtered_paths = []
                    try:
                        for ep in paths:
                            sname = ((ep.get('start_poi') or {}).get('name'))
                            ename = ((ep.get('end_poi') or {}).get('name'))
                            if (not sname) or (not ename):
                                continue
                            if (sname in allowed_poi_names) and (ename in allowed_poi_names):
                                filtered_paths.append(ep)
                    except Exception:
                        filtered_paths = paths or []
                    poi_coords = {}
                    road_coords = {}
                    try:
                        # 道路节点坐标仅来源于本地道路节点目录与full_route段落
                        for nd in (road_nodes_data or []):
                            nm = nd.get('name') or nd.get('Name')
                            if not nm or (isinstance(nm, str) and not nm.strip()):
                                continue
                            lat, lng = None, None
                            if isinstance(nd.get('coordinates'), (list, tuple)) and len(nd['coordinates']) >= 2:
                                lng = float(nd['coordinates'][0]); lat = float(nd['coordinates'][1])
                            else:
                                loc = nd.get('location')
                                if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                                    lat = float(loc[0]); lng = float(loc[1])
                                elif isinstance(loc, dict):
                                    lat = float(loc.get('latitude') or loc.get('lat') or 0.0)
                                    lng = float(loc.get('longitude') or loc.get('lng') or 0.0)
                            if lat is not None and lng is not None:
                                road_coords[nm] = (lat, lng)
                        fr_pre = new_exploration_data.get('full_route', {})
                        for seg in (fr_pre.get('segments') or []):
                            tn = seg.get('to_name')
                            tc = seg.get('to_coords') or {}
                            lat = tc.get('lat')
                            lng = tc.get('lng')
                            if tn and (lat is not None) and (lng is not None):
                                road_coords[tn] = (float(lat), float(lng))
                        # POI坐标仅来源于本地POI文件
                        local_pois = []
                        try:
                            if getattr(explorer_agent, 'use_local_data', False) and getattr(explorer_agent, 'local_data_service', None):
                                local_pois = explorer_agent.local_data_service.get_poi_data() or []
                        except Exception:
                            local_pois = []
                        for ap in local_pois:
                            nm = ap.get('name')
                            loc = ap.get('location') or {}
                            lat = loc.get('latitude') or loc.get('lat')
                            lng = loc.get('longitude') or loc.get('lng')
                            if nm and lat is not None and lng is not None:
                                poi_coords[nm] = (float(lat), float(lng))
                        # 回退：如本地POI未加载，则使用已访问/时间序POI填充坐标
                        if not poi_coords:
                            for vp in (visited_pois or []):
                                try:
                                    nm = vp.get('name')
                                    loc = vp.get('location') or {}
                                    lat = loc.get('latitude') or loc.get('lat')
                                    lng = loc.get('longitude') or loc.get('lng')
                                    if nm and lat is not None and lng is not None and nm not in poi_coords:
                                        poi_coords[nm] = (float(lat), float(lng))
                                except Exception:
                                    continue
                            for tp in (exploration_data.get('time_ordered_pois') or []):
                                try:
                                    nm = tp.get('name')
                                    loc = tp.get('location') or {}
                                    lat = loc.get('latitude') or loc.get('lat')
                                    lng = loc.get('longitude') or loc.get('lng')
                                    if nm and lat is not None and lng is not None and nm not in poi_coords:
                                        poi_coords[nm] = (float(lat), float(lng))
                                except Exception:
                                    continue
                    except Exception:
                        pass
                    nodes_out = []
                    edges_out = []
                    id_map = {}
                    next_id = 1
                    def _ensure_node(name: str, ntype: str):
                        nonlocal next_id
                        if name not in id_map:
                            id_map[name] = next_id
                            nodes_out.append({'id': next_id, 'type': ntype, 'name': name})
                            next_id += 1
                        return id_map[name]
                    try:
                        for unit in poi_units:
                            n = ((unit.get('poi') or {}).get('name'))
                            if n:
                                _ensure_node(n, 'POI')
                        for ep in filtered_paths:
                            sname = ((ep.get('start_poi') or {}).get('name'))
                            ename = ((ep.get('end_poi') or {}).get('name'))
                            rps = ep.get('route_points') or []
                            if sname:
                                _ensure_node(sname, 'POI')
                            for rp in rps:
                                rn = rp.get('name')
                                if rn:
                                    _ensure_node(rn, 'ROAD')
                            if ename:
                                _ensure_node(ename, 'POI')
                            chain = []
                            if sname:
                                chain.append(sname)
                            for rp in rps:
                                rn = rp.get('name')
                                if rn:
                                    chain.append(rn)
                            if ename:
                                chain.append(ename)
                            name_type_map = {nd['name']: nd['type'] for nd in nodes_out}
                            for i in range(len(chain)-1):
                                a = chain[i]
                                b = chain[i+1]
                                distm = None
                                degm = None
                                if i < len(rps):
                                    rpinfo = (rps[i].get('relative_position') or {}) if i < len(rps) else {}
                                    distm = rpinfo.get('distance')
                                    degm = rpinfo.get('direction')
                                if distm is None:
                                    at = name_type_map.get(a)
                                    bt = name_type_map.get(b)
                                    if at == 'POI':
                                        alat, alng = poi_coords.get(a, (None, None))
                                    else:
                                        alat, alng = road_coords.get(a, (None, None))
                                    if bt == 'POI':
                                        blat, blng = poi_coords.get(b, (None, None))
                                    else:
                                        blat, blng = road_coords.get(b, (None, None))
                                    if None not in (alat, alng, blat, blng):
                                        distm = int(round(_haversine_distance(alat, alng, blat, blng)))
                                        degm = _direction(alat, alng, blat, blng)
                                ida = _ensure_node(a, 'POI' if i == 0 else ('ROAD' if a in id_map and nodes_out[[x['id'] for x in nodes_out].index(id_map[a])]['type']=='ROAD' else 'POI'))
                                idb = _ensure_node(b, 'POI' if i == len(chain)-2 else 'ROAD')
                                if isinstance(distm, (int, float)):
                                    edges_out.append({'from': ida, 'to': idb, 'length_m': int(distm), 'direction_deg': int(degm) if isinstance(degm, (int, float)) else None})
                    except Exception:
                        pass
                    try:
                        fr = new_exploration_data.get('full_route', {})
                        sn = fr.get('start_name')
                        if sn and sn in poi_coords:
                            poi_coords[sn] = poi_coords[sn]
                    except Exception:
                        pass
                    try:
                        poi_names = [nd['name'] for nd in nodes_out if nd.get('type') == 'POI']
                        road_names = [nd['name'] for nd in nodes_out if nd.get('type') == 'ROAD']
                        existing = set()
                        for e in edges_out:
                            existing.add((e['from'], e['to']))
                        for pn in poi_names:
                            pc = poi_coords.get(pn)
                            if not pc:
                                continue
                            candidates = []
                            for rn in road_names:
                                rc = road_coords.get(rn)
                                if not rc:
                                    continue
                                d = int(round(_haversine_distance(pc[0], pc[1], rc[0], rc[1])))
                                degb = _direction(pc[1-1], pc[1], rc[1-1], rc[1]) if False else _direction(pc[0], pc[1], rc[0], rc[1])
                                candidates.append((rn, d, degb))
                            candidates.sort(key=lambda x: x[1])
                            for rn, d, degb in candidates[:2]:
                                ida = id_map.get(pn)
                                idb = id_map.get(rn)
                                if ida and idb and (ida, idb) not in existing and d > 0:
                                    edges_out.append({'from': ida, 'to': idb, 'length_m': d, 'direction_deg': int(degb)})
                                    existing.add((ida, idb))
                    except Exception:
                        pass
                    try:
                        valid_nodes = []
                        for nd in nodes_out:
                            nm = nd.get('name')
                            tp = nd.get('type')
                            if tp == 'POI':
                                c = poi_coords.get(nm)
                            else:
                                c = road_coords.get(nm)
                            if c and None not in c:
                                valid_nodes.append((nm, nd.get('id'), c))
                        edges_out = [e for e in edges_out if int(e.get('length_m') or 0) > 0]
                        existing = set((e['from'], e['to']) for e in edges_out)
                        if len(valid_nodes) >= 2:
                            visited = set([valid_nodes[0][1]])
                            remaining = {vid for (_, vid, _) in valid_nodes if vid not in visited}
                            coords_by_id = {vid: c for (_, vid, c) in valid_nodes}
                            while remaining:
                                best_edge = None
                                best_d = float('inf')
                                for vid in list(remaining):
                                    for uid in list(visited):
                                        a = coords_by_id.get(uid)
                                        b = coords_by_id.get(vid)
                                        if not a or not b:
                                            continue
                                        d = _haversine_distance(a[0], a[1], b[0], b[1])
                                        if d < best_d:
                                            degmst = _direction(a[0], a[1], b[0], b[1])
                                            best_d = d; best_edge = (uid, vid, int(round(d)), int(degmst))
                                if best_edge:
                                    u, v, dd, dg = best_edge
                                    if (u, v) not in existing and dd > 0:
                                        edges_out.append({'from': u, 'to': v, 'length_m': dd, 'direction_deg': dg})
                                        existing.add((u, v))
                                    visited.add(v)
                                    remaining.discard(v)
                                else:
                                    break
                    except Exception:
                        pass
                    unique = {}
                    for e in edges_out:
                        k = (e.get('from'), e.get('to'))
                        pe = unique.get(k)
                        lm = int(e.get('length_m') or 0)
                        if pe is None:
                            unique[k] = e
                        else:
                            lmp = int(pe.get('length_m') or 0)
                            if lm < lmp or (lm == lmp and e.get('direction_deg') is not None and pe.get('direction_deg') is None):
                                unique[k] = e
                    edges_out = list(unique.values())
                    edges_out.sort(key=lambda x: (int(x.get('from') or 0), int(x.get('to') or 0)))
                    if mode == 'graph':
                        lines = []
                        lines.append("# 第二种记忆道路连通图描述")
                        lines.append("## 节点列表")
                        lines.append("NODE[id,类型,附加属性]")
                        for nd in nodes_out:
                            lines.append(f"NODE[{nd['id']},{nd['type']},name={nd['name']}]")
                        lines.append("")
                        lines.append("## 边列表")
                        lines.append("EDGE[起点ID,终点ID,道路长度,方向]")
                        for e in edges_out:
                            deg_print = int(e.get('direction_deg') or 0)
                            lines.append(f"EDGE[{e['from']},{e['to']},{int(e['length_m'])}m,{deg_print}°]")
                        exploration_data['context_text'] = "\n".join(lines)
                        exploration_data['context_mode'] = 'graph'
                elif mode == 'map':
                    boundary = explorer_agent.exploration_boundary or []
                    grid_size = 20
                    min_lat = min([p[0] for p in boundary]) if boundary else 0.0
                    max_lat = max([p[0] for p in boundary]) if boundary else 1.0
                    min_lng = min([p[1] for p in boundary]) if boundary else 0.0
                    max_lng = max([p[1] for p in boundary]) if boundary else 1.0
                    try:
                        if not isinstance(locals().get('poi_coords'), dict):
                            poi_coords = {}
                        if not isinstance(locals().get('road_coords'), dict):
                            road_coords = {}
                        if not poi_coords:
                            local_pois = []
                            try:
                                if getattr(explorer_agent, 'use_local_data', False) and getattr(explorer_agent, 'local_data_service', None):
                                    local_pois = explorer_agent.local_data_service.get_poi_data() or []
                            except Exception:
                                local_pois = []
                            for ap in local_pois:
                                nm = ap.get('name')
                                loc = ap.get('location') or {}
                                lat = loc.get('latitude') or loc.get('lat')
                                lng = loc.get('longitude') or loc.get('lng')
                                if nm and lat is not None and lng is not None:
                                    poi_coords[nm] = (float(lat), float(lng))
                        if not road_coords:
                            try:
                                for nd in (road_nodes_data or []):
                                    nm = nd.get('name') or nd.get('Name')
                                    if not nm:
                                        continue
                                    lat, lng = None, None
                                    coords = nd.get('coordinates')
                                    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                                        lng = float(coords[0]); lat = float(coords[1])
                                    else:
                                        loc = nd.get('location')
                                        if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                                            lat = float(loc[0]); lng = float(loc[1])
                                        elif isinstance(loc, dict):
                                            lat = float(loc.get('latitude') or loc.get('lat') or 0.0)
                                            lng = float(loc.get('longitude') or loc.get('lng') or 0.0)
                                    if lat is not None and lng is not None:
                                        road_coords[nm] = (lat, lng)
                            except Exception:
                                pass
                        # 若边界为空或退化，则用坐标字典推导边界
                        if not boundary:
                            all_coords = list(poi_coords.values()) + list(road_coords.values())
                            if all_coords:
                                lats = [c[0] for c in all_coords if None not in c]
                                lngs = [c[1] for c in all_coords if None not in c]
                                if lats and lngs:
                                    min_lat = min(lats); max_lat = max(lats)
                                    min_lng = min(lngs); max_lng = max(lngs)
                                    if abs(max_lat - min_lat) < 1e-9:
                                        max_lat = min_lat + 1e-3
                                    if abs(max_lng - min_lng) < 1e-9:
                                        max_lng = min_lng + 1e-3
                    except Exception:
                        pass
                    def to_ij(lat, lng):
                        try:
                            i = int((lat - min_lat) / max(1e-9, (max_lat - min_lat)) * (grid_size - 1))
                            j = int((lng - min_lng) / max(1e-9, (max_lng - min_lng)) * (grid_size - 1))
                            i = max(0, min(grid_size - 1, i))
                            j = max(0, min(grid_size - 1, j))
                            return i, j
                        except Exception:
                            return 0, 0
                    def raster(a_i, a_j, b_i, b_j):
                        path = []
                        di = b_i - a_i
                        dj = b_j - a_j
                        n = max(abs(di), abs(dj))
                        if n == 0:
                            return [(a_i, a_j)]
                        si = di / float(n)
                        sj = dj / float(n)
                        x = float(a_i)
                        y = float(a_j)
                        for t in range(n + 1):
                            ii = int(round(x))
                            jj = int(round(y))
                            if not path or path[-1] != (ii, jj):
                                path.append((ii, jj))
                            x += si
                            y += sj
                        return path
                    nodes_out_local = nodes_out if isinstance(nodes_out, list) else []
                    edges_out_local = edges_out if isinstance(edges_out, list) else []
                    if not nodes_out_local:
                        tmp_nodes = []
                        cid = 1
                        for unit in (new_exploration_data.get('poi_units') or []):
                            nm = ((unit.get('poi') or {}).get('name'))
                            if nm:
                                tp = 'POI' if nm in (poi_coords or {}) else 'ROAD'
                                tmp_nodes.append({'id': cid, 'type': tp, 'name': nm}); cid += 1
                        fr = new_exploration_data.get('full_route', {}) if isinstance(new_exploration_data, dict) else {}
                        sn = fr.get('start_name')
                        if sn:
                            tp = 'POI' if sn in (poi_coords or {}) else 'ROAD'
                            tmp_nodes.append({'id': cid, 'type': tp, 'name': sn}); cid += 1
                        for seg in (fr.get('segments') or []):
                            nm = seg.get('to_name')
                            if nm:
                                tp = 'POI' if nm in (poi_coords or {}) else 'ROAD'
                                tmp_nodes.append({'id': cid, 'type': tp, 'name': nm}); cid += 1
                        # 简单去重按name
                        seen = set(); dedup = []
                        for nd in tmp_nodes:
                            if nd['name'] in seen:
                                continue
                            seen.add(nd['name']); dedup.append(nd)
                        nodes_out_local = dedup
                    id_to_name = {nd.get('id'): nd.get('name') for nd in nodes_out_local}
                    id_to_type = {nd.get('id'): nd.get('type') for nd in nodes_out_local}
                    lines = []
                    lines.append("# 第三种记忆map描述")
                    lines.append("## 节点列表")
                    lines.append("NODE[id,类型,附加属性，ij坐标]")
                    try:
                        boundary = explorer_agent.exploration_boundary or []
                        gs = int(locals().get('grid_size', 30))
                        min_lat = min([p[0] for p in boundary]) if boundary else 0.0
                        max_lat = max([p[0] for p in boundary]) if boundary else 1.0
                        min_lng = min([p[1] for p in boundary]) if boundary else 0.0
                        max_lng = max([p[1] for p in boundary]) if boundary else 1.0
                        lat_mid = (min_lat + max_lat) / 2.0
                        lng_mid = (min_lng + max_lng) / 2.0
                        div = max(1, gs - 1)
                        vert_m = _haversine_distance(min_lat, lng_mid, max_lat, lng_mid)
                        hori_m = _haversine_distance(lat_mid, min_lng, lat_mid, max_lng)
                        cell_len_m = int(round(((vert_m / div) + (hori_m / div)) / 2.0))
                        lines.append("[栅格参数]")
                        lines.append(f"- grid_size: {gs}")
                        lines.append(f"- grid_cell_size_m: {cell_len_m}")
                    except Exception:
                        lines.append("[栅格参数]")
                        lines.append(f"- grid_size: {int(locals().get('grid_size', 30))}")
                        lines.append("- grid_cell_size_m: 未提供")
                    for nd in nodes_out_local:
                        nm = nd.get('name')
                        tp = nd.get('type')
                        cid = nd.get('id')
                        name_str = str(nm) if nm is not None else ''
                        if not name_str or name_str.strip().lower() in ('null', 'none'):
                            continue
                        if tp != 'POI' and (name_str.startswith('路点_') or name_str.startswith('node_')):
                            continue
                        if tp == 'POI':
                            c = poi_coords.get(nm)
                        else:
                            c = road_coords.get(nm)
                        if not c or None in c:
                            ii, jj = 0, 0
                        else:
                            ii, jj = to_ij(c[0], c[1])
                        lines.append(f"NODE[{cid},{tp},name={nm}，（{ii}，{jj}）]")
                    lines.append("")
                    lines.append("## 道路列表")
                    lines.append("ROAD[道路坐标]")
                    roads_added = 0
                    if edges_out_local:
                        for e in edges_out_local:
                            fid = e.get('from')
                            tid = e.get('to')
                            fn = id_to_name.get(fid)
                            tn = id_to_name.get(tid)
                            ft = id_to_type.get(fid)
                            tt = id_to_type.get(tid)
                            if ft == 'POI':
                                fc = poi_coords.get(fn)
                            else:
                                fc = road_coords.get(fn)
                            if tt == 'POI':
                                tc = poi_coords.get(tn)
                            else:
                                tc = road_coords.get(tn)
                            if not fc or not tc or None in fc or None in tc:
                                continue
                            ai, aj = to_ij(fc[0], fc[1])
                            bi, bj = to_ij(tc[0], tc[1])
                            seq = raster(ai, aj, bi, bj)
                            coord_str = "，".join([f"（{i}，{j}）" for (i, j) in seq])
                            lines.append(f"ROAD[{coord_str}]")
                            roads_added += 1
                    else:
                        fr = new_exploration_data.get('full_route', {}) if isinstance(new_exploration_data, dict) else {}
                        segs = fr.get('segments') or []
                        coords_chain = []
                        start_name = fr.get('start_name')
                        start_c = poi_coords.get(start_name) or road_coords.get(start_name) if start_name else None
                        if start_c and None not in start_c:
                            coords_chain.append(start_c)
                        for seg in segs:
                            tc = None
                            tc_dict = seg.get('to_coords') if isinstance(seg, dict) else None
                            if isinstance(tc_dict, dict):
                                lat = tc_dict.get('lat'); lng = tc_dict.get('lng')
                                if lat is not None and lng is not None:
                                    tc = (float(lat), float(lng))
                            if tc is None:
                                nm = seg.get('to_name')
                                tc = poi_coords.get(nm) or road_coords.get(nm) if nm else None
                            if tc and None not in tc:
                                coords_chain.append(tc)
                        for k in range(1, len(coords_chain)):
                            a = coords_chain[k-1]; b = coords_chain[k]
                            ai, aj = to_ij(a[0], a[1]); bi, bj = to_ij(b[0], b[1])
                            seq = raster(ai, aj, bi, bj)
                            coord_str = "，".join([f"（{i}，{j}）" for (i, j) in seq])
                            lines.append(f"ROAD[{coord_str}]")
                            roads_added += 1
                    if roads_added == 0:
                        lines.append("ROAD[（0，0）]")
                    exploration_data['context_text'] = "\n".join(lines)
                    exploration_data['context_mode'] = 'map'
            except Exception:
                pass

            # 若当前选择map模式，但尚未写入上下文，则在初始化前兜底生成一次，避免后续回退
            try:
                if getattr(explorer_agent, 'memory_mode', 'context') == 'map' and not exploration_data.get('context_text'):
                    nodes_out_local = nodes_out if isinstance(nodes_out, list) else []
                    edges_out_local = edges_out if isinstance(edges_out, list) else []
                    boundary = explorer_agent.exploration_boundary or []
                    grid_size = 20
                    min_lat = min([p[0] for p in boundary]) if boundary else 0.0
                    max_lat = max([p[0] for p in boundary]) if boundary else 1.0
                    min_lng = min([p[1] for p in boundary]) if boundary else 0.0
                    max_lng = max([p[1] for p in boundary]) if boundary else 1.0
                    def to_ij(lat, lng):
                        try:
                            i = int((lat - min_lat) / max(1e-9, (max_lat - min_lat)) * (grid_size - 1))
                            j = int((lng - min_lng) / max(1e-9, (max_lng - min_lng)) * (grid_size - 1))
                            i = max(0, min(grid_size - 1, i))
                            j = max(0, min(grid_size - 1, j))
                            return i, j
                        except Exception:
                            return 0, 0
                    def raster(a_i, a_j, b_i, b_j):
                        path = []
                        di = b_i - a_i
                        dj = b_j - a_j
                        n = max(abs(di), abs(dj))
                        if n == 0:
                            return [(a_i, a_j)]
                        si = di / float(n)
                        sj = dj / float(n)
                        x = float(a_i)
                        y = float(a_j)
                        for t in range(n + 1):
                            ii = int(round(x))
                            jj = int(round(y))
                            if not path or path[-1] != (ii, jj):
                                path.append((ii, jj))
                            x += si
                            y += sj
                        return path
                    nodes_out_local = nodes_out if isinstance(nodes_out, list) else []
                    edges_out_local = edges_out if isinstance(edges_out, list) else []
                    if not nodes_out_local:
                        tmp_nodes = []
                        cid = 1
                        for nm, c in (poi_coords or {}).items():
                            tmp_nodes.append({'id': cid, 'type': 'POI', 'name': nm}); cid += 1
                        for nd in (road_nodes_data or []):
                            nm = nd.get('name') or nd.get('Name')
                            if nm:
                                tmp_nodes.append({'id': cid, 'type': 'ROAD', 'name': nm}); cid += 1
                        nodes_out_local = tmp_nodes
                    id_to_name = {nd.get('id'): nd.get('name') for nd in nodes_out_local}
                    id_to_type = {nd.get('id'): nd.get('type') for nd in nodes_out_local}
                    lines = []
                    lines.append("# 第三种记忆map描述")
                    lines.append("## 节点列表")
                    lines.append("NODE[id,类型,附加属性，ij坐标]")
                    try:
                        boundary = explorer_agent.exploration_boundary or []
                        gs = int(locals().get('grid_size', 20))
                        min_lat = min([p[0] for p in boundary]) if boundary else 0.0
                        max_lat = max([p[0] for p in boundary]) if boundary else 1.0
                        min_lng = min([p[1] for p in boundary]) if boundary else 0.0
                        max_lng = max([p[1] for p in boundary]) if boundary else 1.0
                        lat_mid = (min_lat + max_lat) / 2.0
                        lng_mid = (min_lng + max_lng) / 2.0
                        div = max(1, gs - 1)
                        vert_m = _haversine_distance(min_lat, lng_mid, max_lat, lng_mid)
                        hori_m = _haversine_distance(lat_mid, min_lng, lat_mid, max_lng)
                        cell_len_m = int(round(((vert_m / div) + (hori_m / div)) / 2.0))
                        lines.append("[栅格参数]")
                        lines.append(f"- grid_size: {gs}")
                        lines.append(f"- grid_cell_size_m: {cell_len_m}")
                    except Exception:
                        lines.append("[栅格参数]")
                        lines.append(f"- grid_size: {int(locals().get('grid_size', 20))}")
                        lines.append("- grid_cell_size_m: 未提供")
                    for nd in nodes_out_local:
                        nm = nd.get('name')
                        tp = nd.get('type')
                        cid = nd.get('id')
                        name_str = str(nm) if nm is not None else ''
                        if not name_str or name_str.strip().lower() in ('null', 'none'):
                            continue
                        if tp != 'POI' and (name_str.startswith('路点_') or name_str.startswith('node_')):
                            continue
                        if tp == 'POI':
                            c = poi_coords.get(nm)
                        else:
                            c = road_coords.get(nm)
                        if not c or None in c:
                            ii, jj = 0, 0
                        else:
                            ii, jj = to_ij(c[0], c[1])
                        lines.append(f"NODE[{cid},{tp},name={nm}，（{ii}，{jj}）]")
                    lines.append("")
                    lines.append("## 道路列表")
                    lines.append("ROAD[道路坐标]")
                    for e in edges_out_local:
                        fid = e.get('from')
                        tid = e.get('to')
                        fn = id_to_name.get(fid)
                        tn = id_to_name.get(tid)
                        ft = id_to_type.get(fid)
                        tt = id_to_type.get(tid)
                        if ft == 'POI':
                            fc = poi_coords.get(fn)
                        else:
                            fc = road_coords.get(fn)
                        if tt == 'POI':
                            tc = poi_coords.get(tn)
                        else:
                            tc = road_coords.get(tn)
                        if not fc or not tc or None in fc or None in tc:
                            continue
                        ai, aj = to_ij(fc[0], fc[1])
                        bi, bj = to_ij(tc[0], tc[1])
                        seq = raster(ai, aj, bi, bj)
                        coord_str = "，".join([f"（{i}，{j}）" for (i, j) in seq])
                        lines.append(f"ROAD[{coord_str}]")
                    exploration_data['context_text'] = "\n".join(lines)
                    exploration_data['context_mode'] = 'map'
            except Exception:
                pass
            await agent.initialize([], exploration_data)
            injected_context = exploration_data.get('context_text')
            fallback_context = agent._build_exploration_context()
            # print(f"[DEBUG] 停止探索-注入上下文: {injected_context is not None}, 回退上下文: {fallback_context is not None}")
            try:
                if getattr(explorer_agent, 'memory_mode', 'context') == 'map' and not injected_context:
                    nodes_out_local = nodes_out if isinstance(nodes_out, list) else []
                    edges_out_local = edges_out if isinstance(edges_out, list) else []
                    boundary = explorer_agent.exploration_boundary or []
                    grid_size = 30
                    min_lat = min([p[0] for p in boundary]) if boundary else 0.0
                    max_lat = max([p[0] for p in boundary]) if boundary else 1.0
                    min_lng = min([p[1] for p in boundary]) if boundary else 0.0
                    max_lng = max([p[1] for p in boundary]) if boundary else 1.0
                    def to_ij(lat, lng):
                        try:
                            i = int((lat - min_lat) / max(1e-9, (max_lat - min_lat)) * (grid_size - 1))
                            j = int((lng - min_lng) / max(1e-9, (max_lng - min_lng)) * (grid_size - 1))
                            i = max(0, min(grid_size - 1, i))
                            j = max(0, min(grid_size - 1, j))
                            return i, j
                        except Exception:
                            return 0, 0
                    def raster(a_i, a_j, b_i, b_j):
                        path = []
                        di = b_i - a_i
                        dj = b_j - a_j
                        n = max(abs(di), abs(dj))
                        if n == 0:
                            return [(a_i, a_j)]
                        si = di / float(n)
                        sj = dj / float(n)
                        x = float(a_i)
                        y = float(a_j)
                        for t in range(n + 1):
                            ii = int(round(x))
                            jj = int(round(y))
                            if not path or path[-1] != (ii, jj):
                                path.append((ii, jj))
                            x += si
                            y += sj
                        return path
                    nodes_out_local = nodes_out if isinstance(nodes_out, list) else []
                    edges_out_local = edges_out if isinstance(edges_out, list) else []
                    if not nodes_out_local:
                        tmp_nodes = []
                        cid = 1
                        for nm, c in (poi_coords or {}).items():
                            tmp_nodes.append({'id': cid, 'type': 'POI', 'name': nm}); cid += 1
                        for nd in (road_nodes_data or []):
                            nm = nd.get('name') or nd.get('Name')
                            if nm:
                                tmp_nodes.append({'id': cid, 'type': 'ROAD', 'name': nm}); cid += 1
                        nodes_out_local = tmp_nodes
                    id_to_name = {nd.get('id'): nd.get('name') for nd in nodes_out_local}
                    id_to_type = {nd.get('id'): nd.get('type') for nd in nodes_out_local}
                    lines = []
                    lines.append("# 第三种记忆map描述")
                    lines.append("## 节点列表")
                    lines.append("NODE[id,类型,附加属性，ij坐标]")
                    try:
                        boundary = explorer_agent.exploration_boundary or []
                        gs = int(locals().get('grid_size', 30))
                        min_lat = min([p[0] for p in boundary]) if boundary else 0.0
                        max_lat = max([p[0] for p in boundary]) if boundary else 1.0
                        min_lng = min([p[1] for p in boundary]) if boundary else 0.0
                        max_lng = max([p[1] for p in boundary]) if boundary else 1.0
                        lat_mid = (min_lat + max_lat) / 2.0
                        lng_mid = (min_lng + max_lng) / 2.0
                        div = max(1, gs - 1)
                        vert_m = _haversine_distance(min_lat, lng_mid, max_lat, lng_mid)
                        hori_m = _haversine_distance(lat_mid, min_lng, lat_mid, max_lng)
                        cell_len_m = int(round(((vert_m / div) + (hori_m / div)) / 2.0))
                        lines.append("[栅格参数]")
                        lines.append(f"- grid_size: {gs}")
                        lines.append(f"- grid_cell_size_m: {cell_len_m}")
                    except Exception:
                        lines.append("[栅格参数]")
                        lines.append(f"- grid_size: {int(locals().get('grid_size', 30))}")
                        lines.append("- grid_cell_size_m: 未提供")
                    for nd in nodes_out_local:
                        nm = nd.get('name')
                        tp = nd.get('type')
                        cid = nd.get('id')
                        if tp == 'POI':
                            c = poi_coords.get(nm)
                        else:
                            c = road_coords.get(nm)
                        if not c or None in c:
                            ii, jj = 0, 0
                        else:
                            ii, jj = to_ij(c[0], c[1])
                        lines.append(f"NODE[{cid},{tp},name={nm}，（{ii}，{jj}）]")
                    lines.append("")
                    lines.append("## 道路列表")
                    lines.append("ROAD[道路坐标]")
                    for e in edges_out_local:
                        fid = e.get('from')
                        tid = e.get('to')
                        fn = id_to_name.get(fid)
                        tn = id_to_name.get(tid)
                        ft = id_to_type.get(fid)
                        tt = id_to_type.get(tid)
                        if ft == 'POI':
                            fc = poi_coords.get(fn)
                        else:
                            fc = road_coords.get(fn)
                        if tt == 'POI':
                            tc = poi_coords.get(tn)
                        else:
                            tc = road_coords.get(tn)
                        if not fc or not tc or None in fc or None in tc:
                            continue
                        ai, aj = to_ij(fc[0], fc[1])
                        bi, bj = to_ij(tc[0], tc[1])
                        seq = raster(ai, aj, bi, bj)
                        coord_str = "，".join([f"（{i}，{j}）" for (i, j) in seq])
                        lines.append(f"ROAD[{coord_str}]")
                    exploration_data['context_text'] = "\n".join(lines)
                    exploration_data['context_mode'] = 'map'
                    injected_context = exploration_data.get('context_text')
            except Exception:
                pass
            if injected_context:
                pass
                # print(f"[DEBUG] 注入上下文长度: {len(injected_context)}")
            if getattr(explorer_agent, 'memory_mode', 'context') == 'map':
                nodes_out_local = nodes_out if isinstance(nodes_out, list) else []
                edges_out_local = edges_out if isinstance(edges_out, list) else []
                context_text = exploration_data.get('context_text') or ""
                if not context_text:
                    boundary = explorer_agent.exploration_boundary or []
                    grid_size = 30
                    min_lat = min([p[0] for p in boundary]) if boundary else 0.0
                    max_lat = max([p[0] for p in boundary]) if boundary else 1.0
                    min_lng = min([p[1] for p in boundary]) if boundary else 0.0
                    max_lng = max([p[1] for p in boundary]) if boundary else 1.0
                    def to_ij(lat, lng):
                        try:
                            i = int((lat - min_lat) / max(1e-9, (max_lat - min_lat)) * (grid_size - 1))
                            j = int((lng - min_lng) / max(1e-9, (max_lng - min_lng)) * (grid_size - 1))
                            i = max(0, min(grid_size - 1, i))
                            j = max(0, min(grid_size - 1, j))
                            return i, j
                        except Exception:
                            return 0, 0
                    def raster(a_i, a_j, b_i, b_j):
                        path = []
                        di = b_i - a_i
                        dj = b_j - a_j
                        n = max(abs(di), abs(dj))
                        if n == 0:
                            return [(a_i, a_j)]
                        si = di / float(n)
                        sj = dj / float(n)
                        x = float(a_i)
                        y = float(a_j)
                        for t in range(n + 1):
                            ii = int(round(x))
                            jj = int(round(y))
                            if not path or path[-1] != (ii, jj):
                                path.append((ii, jj))
                            x += si
                            y += sj
                        return path
                    id_to_name = {nd.get('id'): nd.get('name') for nd in nodes_out_local}
                    id_to_type = {nd.get('id'): nd.get('type') for nd in nodes_out_local}
                    lines = []
                    lines.append("# 第三种记忆map描述")
                    lines.append("## 节点列表")
                    lines.append("NODE[id,类型,附加属性，ij坐标]")
                    try:
                        boundary = explorer_agent.exploration_boundary or []
                        gs = int(locals().get('grid_size', 30))
                        min_lat = min([p[0] for p in boundary]) if boundary else 0.0
                        max_lat = max([p[0] for p in boundary]) if boundary else 1.0
                        min_lng = min([p[1] for p in boundary]) if boundary else 0.0
                        max_lng = max([p[1] for p in boundary]) if boundary else 1.0
                        lat_mid = (min_lat + max_lat) / 2.0
                        lng_mid = (min_lng + max_lng) / 2.0
                        div = max(1, gs - 1)
                        vert_m = _haversine_distance(min_lat, lng_mid, max_lat, lng_mid)
                        hori_m = _haversine_distance(lat_mid, min_lng, lat_mid, max_lng)
                        cell_len_m = int(round(((vert_m / div) + (hori_m / div)) / 2.0))
                        lines.append("[栅格参数]")
                        lines.append(f"- grid_size: {gs}")
                        lines.append(f"- grid_cell_size_m: {cell_len_m}")
                    except Exception:
                        lines.append("[栅格参数]")
                        lines.append(f"- grid_size: {int(locals().get('grid_size', 30))}")
                        lines.append("- grid_cell_size_m: 未提供")
                    for nd in nodes_out_local:
                        nm = nd.get('name')
                        tp = nd.get('type')
                        cid = nd.get('id')
                        if tp == 'POI':
                            c = poi_coords.get(nm)
                        else:
                            c = road_coords.get(nm)
                        if not c or None in c:
                            ii, jj = 0, 0
                        else:
                            ii, jj = to_ij(c[0], c[1])
                        lines.append(f"NODE[{cid},{tp},name={nm}，（{ii}，{jj}）]")
                    lines.append("")
                    lines.append("## 道路列表")
                    lines.append("ROAD[道路坐标]")
                    for e in edges_out_local:
                        fid = e.get('from')
                        tid = e.get('to')
                        fn = id_to_name.get(fid)
                        tn = id_to_name.get(tid)
                        ft = id_to_type.get(fid)
                        tt = id_to_type.get(tid)
                        if ft == 'POI':
                            fc = poi_coords.get(fn)
                        else:
                            fc = road_coords.get(fn)
                        if tt == 'POI':
                            tc = poi_coords.get(tn)
                        else:
                            tc = road_coords.get(tn)
                        if not fc or not tc or None in fc or None in tc:
                            continue
                        ai, aj = to_ij(fc[0], fc[1])
                        bi, bj = to_ij(tc[0], tc[1])
                        seq = raster(ai, aj, bi, bj)
                        coord_str = "，".join([f"（{i}，{j}）" for (i, j) in seq])
                        lines.append(f"ROAD[{coord_str}]")
                    context_text = "\n".join(lines)
                injected_context = context_text
            else:
                context_text = injected_context or fallback_context
            try:
                # 缓存上下文，供评估阶段一致复用
                try:
                    global last_context_text, last_context_mode
                    last_context_text = context_text
                    last_context_mode = exploration_data.get('context_mode') or getattr(explorer_agent, 'memory_mode', 'context')
                except Exception:
                    pass
                if isinstance(context_text, str) and context_text.strip():
                    print("\n" + "="*50, flush=True)
                    print("🧠 发给AI的上下文（文本格式，保持一致）", flush=True)
                    print("="*50, flush=True)
                    print(context_text, flush=True)
                    print("="*50 + "\n", flush=True)
            except Exception:
                pass
            
            
        except Exception as context_error:
            print(f"打印探索上下文失败: {context_error}")
        
        # 广播停止消息
        try:
            await manager.broadcast(json.dumps({
                "type": "exploration_stopped",
                "data": report
            }))
            print("停止消息已广播")
        except Exception as broadcast_error:
            print(f"广播停止消息失败: {broadcast_error}")
            # 广播失败不影响主要功能
        
        try:
            region_name = None
            try:
                if getattr(explorer_agent, 'use_local_data', False) and getattr(explorer_agent, 'local_data_service', None):
                    region_name = explorer_agent.local_data_service.region_name
            except Exception:
                region_name = None
            if not region_name:
                region_name = "北京天安门"
            
            print(f"[DEBUG] Generating questions for region: {region_name}")
            eq = EvaluationQuestions(region_name)
            eq_questions = eq.to_dict_list()
            eq_summary = eq.get_questions_summary()
            md_text = eq.build_markdown()
            md_rel_path = os.path.join("data", region_name, "AI探索评估-22题完整问题集.md")
            try:
                os.makedirs(os.path.dirname(md_rel_path), exist_ok=True)
                with open(md_rel_path, "w", encoding="utf-8") as f:
                    f.write(md_text)
            except Exception:
                pass
            eq_payload = {
                "region": region_name,
                "total": len(eq_questions),
                "summary": eq_summary,
                "questions": eq_questions,
                "markdown_path": md_rel_path,
            }
        except Exception as e:
            print(f"[ERROR] Failed to generate evaluation questions: {e}")
            import traceback
            traceback.print_exc()
            eq_payload = None

        return {
            "success": True,
            "message": "探索已停止",
            "report": report,
            "new_exploration_data": latest_new_exploration_data,
            "evaluation_questions": eq_payload,
        }
    except Exception as e:
        print(f"停止探索时发生错误: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"停止探索失败: {str(e)}")

@app.get("/exploration/status")
async def get_exploration_status():
    """获取探索状态"""
    try:
        status = explorer_agent.get_current_status()
        try:
            region_name = None
            if getattr(explorer_agent, "use_local_data", False) and getattr(explorer_agent, "local_data_service", None):
                region_name = getattr(explorer_agent.local_data_service, "region_name", None)
            if region_name:
                status["region_name"] = region_name
        except Exception:
            pass
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/exploration/raw_history")
async def get_exploration_raw_history(tail_lines: int = 200):
    try:
        text = ""
        try:
            text = explorer_agent.get_raw_memory_text() if hasattr(explorer_agent, "get_raw_memory_text") else ""
        except Exception:
            text = ""

        lines = text.splitlines()
        total_lines = len(lines)
        n = int(tail_lines or 0)
        if n <= 0:
            tail = ""
        else:
            tail = "\n".join(lines[-n:])
        return {"success": True, "data": {"total_lines": total_lines, "tail_lines": min(n, total_lines), "tail_text": tail}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/exploration/data")
async def get_new_exploration_data():
    """获取最新的新格式探索数据（无经纬度与POI类型）"""
    try:
        if latest_new_exploration_data is None:
            return {
                "success": False,
                "message": "暂无探索数据，请先执行探索并停止以生成数据"
            }
        return {
            "success": True,
            "data": latest_new_exploration_data,
            "message": "新格式探索数据获取成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/exploration/context")
async def get_latest_context():
    try:
        from typing import Any
        global last_context_text, last_context_mode
        if not last_context_text:
            return {"success": False, "message": "暂无上下文，请先停止探索生成上下文"}
        return {"success": True, "data": {"context_text": last_context_text, "context_mode": last_context_mode}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/qa/ask")
async def ask_question(question: QuestionModel):
    """向AI提问"""
    try:
        # 使用AI的记忆功能回答问题
        answer = explorer_agent.answer_location_question(question.question)
        return {"success": True, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/qa/memory")
async def get_memory_summary():
    """获取AI记忆摘要"""
    try:
        memory_summary = explorer_agent.get_memory_summary()
        
        return {
            "success": True,
            "data": memory_summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/memory/mode")
async def set_memory_mode(payload: Dict):
    try:
        mode_raw = payload.get("mode")
        # print(f"[DEBUG] /memory/mode 收到请求，原始数据={payload}")
        try:
            # print(f"[DEBUG] /memory/mode 输入={mode_raw}")
            if isinstance(mode_raw, str):
                m = mode_raw.strip().lower()
                if m in ("context", "graph", "map", "raw"):
                    old_mode = getattr(explorer_agent,'memory_mode','context')
                    explorer_agent.set_memory_mode(m)
                    new_mode = getattr(explorer_agent,'memory_mode','context')
                    # print(f"[DEBUG] /memory/mode 模式变更: {old_mode} -> {new_mode}")
                else:
                    pass
                    # print(f"[DEBUG] /memory/mode 无效模式: {m}")
            else:
                pass
                # print(f"[DEBUG] /memory/mode 模式类型错误: {type(mode_raw)}")
        except Exception as e:
            # print(f"[DEBUG] /memory/mode 设置异常: {e}")
            pass
        # print(f"[DEBUG] /memory/mode 返回代理模式={getattr(explorer_agent,'memory_mode','context')}")
        return {"success": True, "mode": explorer_agent.memory_mode}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memory/graph")
async def get_graph_memory():
    try:
        snap = explorer_agent.path_memory.build_graph_memory_snapshot()
        return {"success": True, "data": snap}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memory/map")
async def get_map_memory():
    try:
        boundary = explorer_agent.exploration_boundary or []
        snap = explorer_agent.path_memory.build_map_memory_snapshot(boundary, 20)
        return {"success": True, "data": snap}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 移除旧的generate_answer函数，现在使用AI的记忆功能

async def exploration_task():
    """探索任务"""
    try:
        await explorer_agent.start_exploration()
    except asyncio.CancelledError:
        print("探索任务已被取消 (LLM思维链停止)")
    except Exception as e:
        print(f"探索任务出错：{e}")
        await manager.broadcast(json.dumps({
            "type": "error",
            "message": str(e)
        }))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接"""
    await manager.connect(websocket)
    try:
        # 启动状态广播任务
        asyncio.create_task(broadcast_status(websocket))
        
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 处理不同类型的消息
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket错误：{e}")
        manager.disconnect(websocket)

async def broadcast_status(websocket: WebSocket):
    """广播AI状态"""
    try:
        while websocket in manager.active_connections:
            if explorer_agent.is_exploring:
                status = explorer_agent.get_current_status()
                await websocket.send_text(json.dumps({
                    "type": "ai_status",
                    "data": status
                }))
            
            await asyncio.sleep(1)  # 每秒广播一次
            
    except Exception as e:
        print(f"状态广播错误：{e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host=Config.BACKEND_HOST,
        port=Config.BACKEND_PORT,
        reload=True
    )
