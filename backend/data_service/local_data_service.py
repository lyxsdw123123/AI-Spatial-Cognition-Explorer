import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import nearest_points
import networkx as nx
from typing import List, Dict, Tuple, Optional
import os
from config.config import Config

class LocalDataService:
    """本地数据服务类，用于处理shapefile数据和道路网络"""
    
    def __init__(self, region_name: str = "北京天安门"):
        self.config = Config()
        self.region_name = region_name
        self.roads_gdf = None
        self.poi_gdf = None
        self.poi_data = None  # 添加poi_data属性
        self.road_network = None
        self.road_nodes = {}
        self.road_nodes_gdf = None  # 道路节点数据
        self.road_nodes_data = {}  # 道路节点字典，用于路径记忆
        self.poi_file_path_override: Optional[str] = None
        self.road_file_path_override: Optional[str] = None
        self.road_nodes_file_path_override: Optional[str] = None
        self.grid_file_path_override: Optional[str] = None
        
    def switch_region(self, new_region_name: str) -> bool:
        """切换到新的区域并清理旧数据
        
        Args:
            new_region_name: 新区域名称
            
        Returns:
            bool: 切换是否成功
        """
        try:
            # 清理旧数据
            self._clear_all_data()
            
            # 设置新区域
            self.region_name = new_region_name
            # print(f"已切换到区域: {new_region_name}")
            
            return True
            
        except Exception as e:
            print(f"切换区域失败: {str(e)}")
            return False
    
    def _clear_all_data(self):
        """清理所有已加载的数据"""
        self.roads_gdf = None
        self.poi_gdf = None
        self.poi_data = None
        self.road_network = None
        self.road_nodes = {}
        self.road_nodes_gdf = None
        self.road_nodes_data = {}
        self.poi_file_path_override = None
        self.road_file_path_override = None
        self.road_nodes_file_path_override = None
        self.grid_file_path_override = None
        # print("已清理所有数据")

    def set_data_file_overrides(
        self,
        *,
        poi_file_path: Optional[str] = None,
        road_file_path: Optional[str] = None,
        road_nodes_file_path: Optional[str] = None,
        grid_file_path: Optional[str] = None,
    ) -> None:
        self.poi_file_path_override = poi_file_path
        self.road_file_path_override = road_file_path
        self.road_nodes_file_path_override = road_nodes_file_path
        self.grid_file_path_override = grid_file_path
        
    def _get_region_data_path(self, filename: str) -> str:
        """获取指定区域的数据文件路径
        
        Args:
            filename: 文件名（如 "POI数据.shp"）
            
        Returns:
            str: 完整的文件路径
        """
        return os.path.join("data", self.region_name, filename)
    
    def get_grid_boundary_and_size(self) -> Tuple[List[List[float]], int]:
        try:
            grid_path = self.grid_file_path_override or self._get_region_data_path("格网数据.shp")
            if not os.path.exists(grid_path):
                return [], 20
            gdf = gpd.read_file(grid_path, encoding='utf-8')
            try:
                if gdf.crs and str(gdf.crs).upper() != "EPSG:4326":
                    gdf = gdf.to_crs(epsg=4326)
            except Exception:
                pass
            min_lng, min_lat, max_lng, max_lat = gdf.total_bounds
            boundary = [
                [float(min_lat), float(min_lng)],
                [float(max_lat), float(min_lng)],
                [float(max_lat), float(max_lng)],
                [float(min_lat), float(max_lng)]
            ]
            return boundary, 20
        except Exception:
            return [], 20
        
    def load_road_data(self, road_file_path: str = None) -> bool:
        """加载道路数据
        
        Args:
            road_file_path: 道路shapefile文件路径，默认使用当前区域的道路数据.shp
            
        Returns:
            bool: 加载是否成功
        """
        try:
            if road_file_path is None:
                road_file_path = self.road_file_path_override or self._get_region_data_path("道路数据.shp")
                
            if not os.path.exists(road_file_path):
                print(f"道路数据文件不存在: {road_file_path}")
                return False
                
            self.roads_gdf = gpd.read_file(road_file_path, encoding='utf-8')
            # print(f"成功加载道路数据，共 {len(self.roads_gdf)} 条道路")
            
            # 构建道路网络
            self._build_road_network()
            return True
            
        except Exception as e:
            print(f"加载道路数据失败: {str(e)}")
            return False
    
    def load_poi_data(self, poi_file_path: str = None) -> bool:
        """加载POI数据
        
        Args:
            poi_file_path: POI shapefile文件路径，默认使用当前区域的POI数据.shp
            
        Returns:
            bool: 加载是否成功
        """
        try:
            if poi_file_path is None:
                poi_file_path = self.poi_file_path_override or self._get_region_data_path("POI数据.shp")
                
            if not os.path.exists(poi_file_path):
                print(f"POI数据文件不存在: {poi_file_path}")
                return False
            
            # 设置环境变量以修复shapefile索引文件
            os.environ['SHAPE_RESTORE_SHX'] = 'YES'
            self.poi_gdf = gpd.read_file(poi_file_path, encoding='utf-8')
            self.poi_data = self.poi_gdf  # 设置poi_data属性
            # print(f"成功加载POI数据，共 {len(self.poi_gdf)} 个POI点")
            return True
            
        except Exception as e:
            print(f"加载POI数据失败: {str(e)}")
            return False
    
    def _build_road_network(self):
        """构建道路网络图"""
        if self.roads_gdf is None:
            return
            
        self.road_network = nx.Graph()
        self.road_nodes = {}  # 重置节点字典
        coord_to_node = {}  # 坐标到节点ID的映射
        node_id = 0
        
        for idx, road in self.roads_gdf.iterrows():
            geometry = road.geometry
            
            if isinstance(geometry, LineString):
                coords = list(geometry.coords)
                node_id = self._add_road_segment_connected(coords, coord_to_node, node_id)
            elif isinstance(geometry, MultiLineString):
                for line in geometry.geoms:
                    coords = list(line.coords)
                    node_id = self._add_road_segment_connected(coords, coord_to_node, node_id)
        
        # print(f"道路网络构建完成，节点数: {self.road_network.number_of_nodes()}, 边数: {self.road_network.number_of_edges()}")
        
        # 检查网络连通性
        if self.road_network.number_of_nodes() > 0:
            connected_components = list(nx.connected_components(self.road_network))
            # print(f"道路网络连通分量数: {len(connected_components)}")
            if len(connected_components) > 1:
                largest_component = max(connected_components, key=len)
                # print(f"最大连通分量节点数: {len(largest_component)}/{self.road_network.number_of_nodes()}")
    
    def _add_road_segment_connected(self, coords: List[Tuple], coord_to_node: Dict, node_id: int) -> int:
        """添加道路段到网络图，确保相同坐标的节点共享ID"""
        tolerance = 1e-6  # 坐标容差
        
        for i in range(len(coords) - 1):
            coord1 = coords[i]
            coord2 = coords[i + 1]
            
            # 查找或创建第一个节点
            node1_id = None
            for existing_coord, existing_id in coord_to_node.items():
                if abs(existing_coord[0] - coord1[0]) < tolerance and abs(existing_coord[1] - coord1[1]) < tolerance:
                    node1_id = existing_id
                    break
            
            if node1_id is None:
                node1_id = node_id
                coord_to_node[coord1] = node1_id
                self.road_network.add_node(node1_id, pos=coord1)
                self.road_nodes[node1_id] = coord1
                node_id += 1
            
            # 查找或创建第二个节点
            node2_id = None
            for existing_coord, existing_id in coord_to_node.items():
                if abs(existing_coord[0] - coord2[0]) < tolerance and abs(existing_coord[1] - coord2[1]) < tolerance:
                    node2_id = existing_id
                    break
            
            if node2_id is None:
                node2_id = node_id
                coord_to_node[coord2] = node2_id
                self.road_network.add_node(node2_id, pos=coord2)
                self.road_nodes[node2_id] = coord2
                node_id += 1
            
            # 计算边的权重（距离）
            distance = self._calculate_distance(coord1, coord2)
            
            # 添加边
            self.road_network.add_edge(node1_id, node2_id, weight=distance)
        
        return node_id
    
    def _add_road_segment(self, coords: List[Tuple], start_node_id: int):
        """添加道路段到网络图（旧方法，保留兼容性）"""
        for i in range(len(coords) - 1):
            node1_id = start_node_id + i
            node2_id = start_node_id + i + 1
            
            # 添加节点
            self.road_network.add_node(node1_id, pos=coords[i])
            self.road_network.add_node(node2_id, pos=coords[i + 1])
            
            # 计算边的权重（距离）
            distance = self._calculate_distance(coords[i], coords[i + 1])
            
            # 添加边
            self.road_network.add_edge(node1_id, node2_id, weight=distance)
            
            # 存储节点位置
            self.road_nodes[node1_id] = coords[i]
            self.road_nodes[node2_id] = coords[i + 1]
    
    def _calculate_distance(self, point1: Tuple, point2: Tuple) -> float:
        """计算两点间距离（米）"""
        # 简化的距离计算，实际应用中可以使用更精确的地理距离计算
        return np.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2) * 111000
    
    def project_point_to_road(self, point: Tuple[float, float]) -> Tuple[float, float]:
        """将点投影到最近的道路上
        
        Args:
            point: 输入点坐标 (lon, lat)
            
        Returns:
            Tuple: 投影后的点坐标 (lon, lat)
        """
        if self.roads_gdf is None:
            return point
            
        input_point = Point(point)
        min_distance = float('inf')
        closest_point = point
        
        for idx, road in self.roads_gdf.iterrows():
            geometry = road.geometry
            
            if isinstance(geometry, (LineString, MultiLineString)):
                # 找到最近点
                nearest_geom = nearest_points(input_point, geometry)[1]
                distance = input_point.distance(nearest_geom)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_point = (nearest_geom.x, nearest_geom.y)
        
        return closest_point
    
    def find_shortest_path(self, start_point: Tuple[float, float], end_point: Tuple[float, float]) -> List[Tuple[float, float]]:
        """在道路网络中找到最短路径
        
        Args:
            start_point: 起始点坐标 (lon, lat)
            end_point: 终点坐标 (lon, lat)
            
        Returns:
            List: 路径点列表
        """
        # print(f"🗺️ [路径规划] 开始计算路径: {start_point} -> {end_point}")
        # print(f"🗺️ [路径规划] 道路网络状态: 节点数={self.road_network.number_of_nodes() if self.road_network else 0}, 边数={self.road_network.number_of_edges() if self.road_network else 0}")
        
        if self.road_network is None or len(self.road_nodes) == 0:
            # print(f"🗺️ [路径规划] ❌ 道路网络未初始化，返回直线路径")
            return [start_point, end_point]
        
        # 找到最近的道路节点
        start_node = self._find_nearest_road_node(start_point)
        end_node = self._find_nearest_road_node(end_point)
        
        # print(f"🗺️ [路径规划] 最近节点: 起点节点={start_node}, 终点节点={end_node}")
        
        if start_node is None or end_node is None:
            # print(f"🗺️ [路径规划] ❌ 无法找到最近道路节点，返回直线路径")
            return [start_point, end_point]
        
        try:
            # 使用Dijkstra算法找最短路径
            path_nodes = nx.shortest_path(self.road_network, start_node, end_node, weight='weight')
            # print(f"🗺️ [路径规划] ✅ 找到路径，节点序列长度: {len(path_nodes)}")
            
            # 转换为坐标列表
            path_coords = []
            for node in path_nodes:
                if node in self.road_nodes:
                    path_coords.append(self.road_nodes[node])
            
            # print(f"🗺️ [路径规划] ✅ 路径坐标转换完成，坐标点数: {len(path_coords)}")
            return path_coords if path_coords else [start_point, end_point]
            
        except nx.NetworkXNoPath:
            # print(f"🗺️ [路径规划] ❌ NetworkX无法找到路径，返回直线路径")
            return [start_point, end_point]
    
    def _find_nearest_road_node(self, point: Tuple[float, float]) -> Optional[int]:
        """找到最近的道路节点"""
        if not self.road_nodes:
            return None
            
        min_distance = float('inf')
        nearest_node = None
        
        for node_id, node_pos in self.road_nodes.items():
            distance = self._calculate_distance(point, node_pos)
            if distance < min_distance:
                min_distance = distance
                nearest_node = node_id
        
        return nearest_node
    
    def get_poi_data(self) -> List[Dict]:
        """获取POI数据
        
        Returns:
            List: POI数据列表
        """
        if self.poi_gdf is None:
            return []
        
        poi_list = []
        for idx, poi in self.poi_gdf.iterrows():
            # 过滤掉无效POI（name为None或空，或者geometry为None）
            poi_name = poi.get('name')
            if poi_name is None or poi_name == '' or str(poi_name).lower() == 'none':
                # print(f"🔍 [数据过滤] 跳过无效POI: 索引={idx}, name={poi_name}")
                continue
                
            if poi.geometry is None:
                # print(f"🔍 [数据过滤] 跳过无geometry的POI: 索引={idx}, name={poi_name}")
                continue
            
            poi_dict = {
                'id': str(idx),
                'name': poi_name,
                'type': poi.get('type', 'unknown'),
                'location': {
                    'lng': poi.geometry.x,
                    'lat': poi.geometry.y
                },
                'address': poi.get('address', ''),
                'distance': 0  # 将在使用时计算
            }
            poi_list.append(poi_dict)
        
        # print(f"🔍 [数据加载] 从{len(self.poi_gdf)}个原始POI中过滤出{len(poi_list)}个有效POI")
        return poi_list
    
    def get_road_data(self) -> List[Dict]:
        """获取道路数据
        
        Returns:
            List: 道路数据列表
        """
        if self.roads_gdf is None:
            return []
        
        road_list = []
        for idx, road in self.roads_gdf.iterrows():
            geometry = road.geometry
            
            if isinstance(geometry, LineString):
                coords = [[coord[0], coord[1]] for coord in geometry.coords]
                road_dict = {
                    'id': str(idx),
                    'name': road.get('name', f'Road_{idx}'),
                    'coordinates': coords
                }
                road_list.append(road_dict)
            elif isinstance(geometry, MultiLineString):
                for line_idx, line in enumerate(geometry.geoms):
                    coords = [[coord[0], coord[1]] for coord in line.coords]
                    road_dict = {
                        'id': f"{idx}_{line_idx}",
                        'name': road.get('name', f'Road_{idx}_{line_idx}'),
                        'coordinates': coords
                    }
                    road_list.append(road_dict)
        
        return road_list
    
    def is_data_loaded(self) -> bool:
        """检查数据是否已加载"""
        return self.roads_gdf is not None and self.poi_gdf is not None
    
    def load_road_nodes_data(self, road_nodes_file_path: str = None) -> bool:
        """加载道路节点数据
        
        Args:
            road_nodes_file_path: 道路节点shapefile文件路径，默认使用当前区域的道路节点数据.shp
            
        Returns:
            bool: 加载是否成功
        """
        try:
            if road_nodes_file_path is None:
                road_nodes_file_path = self.road_nodes_file_path_override or self._get_region_data_path("道路节点数据.shp")
            
            if not os.path.exists(road_nodes_file_path):
                print(f"道路节点数据文件不存在: {road_nodes_file_path}")
                return False
            
            # 设置环境变量以修复shapefile索引文件
            os.environ['SHAPE_RESTORE_SHX'] = 'YES'
            self.road_nodes_gdf = gpd.read_file(road_nodes_file_path, encoding='utf-8')
            
            # 构建道路节点字典，用于路径记忆
            self.road_nodes_data = {}
            for idx, node in self.road_nodes_gdf.iterrows():
                node_id = str(idx)
                # 兼容字段大小写：优先使用'name'，其次'Name'，无则为None
                node_name = node.get('name') if 'name' in node else None
                if node_name is None or (isinstance(node_name, float) and np.isnan(node_name)):
                    node_name = node.get('Name') if 'Name' in node else None
                # 清理无效字符串
                if node_name is not None:
                    try:
                        node_name_str = str(node_name).strip()
                        if node_name_str.lower() == 'null' or node_name_str == '':
                            node_name = None
                        else:
                            node_name = node_name_str
                    except Exception:
                        node_name = None
                
                self.road_nodes_data[node_id] = {
                    'id': node_id,
                    'name': node_name,
                    'location': {
                        'lng': node.geometry.x,
                        'lat': node.geometry.y
                    },
                    'coordinates': (node.geometry.x, node.geometry.y)
                }
            
            # print(f"成功加载道路节点数据，共 {len(self.road_nodes_gdf)} 个节点")
            return True
            
        except Exception as e:
            print(f"加载道路节点数据失败: {str(e)}")
            return False
    
    def get_road_nodes_data(self) -> List[Dict]:
        """获取道路节点数据
        
        Returns:
            List: 道路节点数据列表
        """
        if self.road_nodes_gdf is None:
            return []
        
        nodes_list = []
        for node_id, node_data in self.road_nodes_data.items():
            nodes_list.append(node_data)
        
        return nodes_list
    

    
    def get_random_road_point(self) -> Tuple[float, float]:
        """获取随机道路点作为AI初始位置"""
        if not self.road_nodes:
            return (116.3974, 39.9093)  # 默认天安门坐标
        
        random_node = np.random.choice(list(self.road_nodes.keys()))
        return self.road_nodes[random_node]
