# 道路节点层记忆系统

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid

class RoadNodeMemoryLayer:
    """道路节点层记忆系统 - 记录节点序列和途径POI"""
    
    def __init__(self):
        # 节点序列记忆
        self.node_sequences = {}  # key: path_id, value: sequence_info
        # 节点到路径的映射
        self.node_to_paths = {}  # key: node_id, value: [path_ids]
        
    def record_node_sequence(self, nodes: List, poi_waypoints: List[Dict], 
                           start_location: List[float], end_location: List[float],
                           total_distance: float = 0) -> str:
        """记录节点序列
        
        Args:
            nodes: 节点列表，可以是坐标列表或节点ID列表
            poi_waypoints: 途径POI列表
            start_location: 起始位置 [纬度, 经度]
            end_location: 终点位置 [纬度, 经度]
            total_distance: 总距离
            
        Returns:
            路径ID
        """
        # 生成唯一路径ID
        path_id = str(uuid.uuid4())
        
        # 处理节点数据
        processed_nodes = []
        coordinates = []
        
        for node in nodes:
            if isinstance(node, (list, tuple)) and len(node) >= 2:
                # 节点是坐标
                coord = [float(node[0]), float(node[1])]  # [纬度, 经度] 或 [经度, 纬度]
                coordinates.append(coord)
                processed_nodes.append(f"node_{len(processed_nodes)}")
            elif isinstance(node, (str, int)):
                # 节点是ID
                processed_nodes.append(str(node))
                # 如果没有坐标信息，使用占位符
                coordinates.append([0.0, 0.0])
            else:
                # 其他格式，尝试转换
                processed_nodes.append(str(node))
                coordinates.append([0.0, 0.0])
        
        # 创建序列信息
        sequence_info = {
            "path_id": path_id,
            "nodes": processed_nodes,
            "coordinates": coordinates,
            "poi_waypoints": poi_waypoints,
            "start_location": start_location,
            "end_location": end_location,
            "total_distance": total_distance,
            "node_count": len(processed_nodes),
            "created_time": datetime.now().isoformat(),
            "traversal_count": 1
        }
        
        # 存储序列
        self.node_sequences[path_id] = sequence_info
        
        # 更新节点到路径的映射
        for node_id in processed_nodes:
            if node_id not in self.node_to_paths:
                self.node_to_paths[node_id] = []
            self.node_to_paths[node_id].append(path_id)
        
        print(f"记录节点序列: 路径ID={path_id}, 节点数={len(processed_nodes)}, 途径POI数={len(poi_waypoints)}")
        return path_id
    
    def get_node_path(self, path_id: str) -> Optional[Dict]:
        """获取指定路径的节点序列
        
        Args:
            path_id: 路径ID
            
        Returns:
            节点序列信息或None
        """
        return self.node_sequences.get(path_id)
    
    def find_paths_through_node(self, node_id: str) -> List[Dict]:
        """查找经过指定节点的所有路径
        
        Args:
            node_id: 节点ID
            
        Returns:
            路径信息列表
        """
        paths = []
        path_ids = self.node_to_paths.get(node_id, [])
        
        for path_id in path_ids:
            path_info = self.node_sequences.get(path_id)
            if path_info:
                paths.append(path_info)
        
        return paths
    
    def find_paths_between_locations(self, start_location: List[float], 
                                   end_location: List[float], 
                                   tolerance: float = 100) -> List[Dict]:
        """查找两个位置间的路径
        
        Args:
            start_location: 起始位置 [纬度, 经度]
            end_location: 终点位置 [纬度, 经度]
            tolerance: 位置容差（米）
            
        Returns:
            匹配的路径列表
        """
        matching_paths = []
        
        for path_info in self.node_sequences.values():
            # 检查起点和终点是否在容差范围内
            start_match = self._is_location_near(
                start_location, path_info['start_location'], tolerance
            )
            end_match = self._is_location_near(
                end_location, path_info['end_location'], tolerance
            )
            
            if start_match and end_match:
                matching_paths.append(path_info)
        
        return matching_paths
    
    def find_paths_with_poi(self, poi_id: str) -> List[Dict]:
        """查找经过指定POI的路径
        
        Args:
            poi_id: POI ID
            
        Returns:
            路径信息列表
        """
        matching_paths = []
        
        for path_info in self.node_sequences.values():
            # 检查途径POI列表
            for waypoint in path_info['poi_waypoints']:
                if waypoint.get('id') == poi_id:
                    matching_paths.append(path_info)
                    break
        
        return matching_paths
    
    def get_common_nodes(self, path_id1: str, path_id2: str) -> List[str]:
        """获取两条路径的共同节点
        
        Args:
            path_id1: 路径1 ID
            path_id2: 路径2 ID
            
        Returns:
            共同节点列表
        """
        path1 = self.node_sequences.get(path_id1)
        path2 = self.node_sequences.get(path_id2)
        
        if not path1 or not path2:
            return []
        
        nodes1 = set(path1['nodes'])
        nodes2 = set(path2['nodes'])
        
        return list(nodes1.intersection(nodes2))
    
    def update_path_traversal(self, path_id: str) -> None:
        """更新路径遍历次数
        
        Args:
            path_id: 路径ID
        """
        if path_id in self.node_sequences:
            self.node_sequences[path_id]['traversal_count'] += 1
            self.node_sequences[path_id]['last_traversed'] = datetime.now().isoformat()
            print(f"更新路径遍历次数: {path_id}, 次数: {self.node_sequences[path_id]['traversal_count']}")
    
    def get_path_statistics(self) -> Dict:
        """获取路径统计信息
        
        Returns:
            统计信息字典
        """
        if not self.node_sequences:
            return {
                'total_paths': 0,
                'total_nodes': 0,
                'average_path_length': 0,
                'total_distance': 0
            }
        
        total_paths = len(self.node_sequences)
        total_nodes = len(self.node_to_paths)
        total_distance = sum(path['total_distance'] for path in self.node_sequences.values())
        average_path_length = sum(path['node_count'] for path in self.node_sequences.values()) / total_paths
        
        return {
            'total_paths': total_paths,
            'total_nodes': total_nodes,
            'average_path_length': round(average_path_length, 2),
            'total_distance': round(total_distance, 2)
        }
    
    def _is_location_near(self, location1: List[float], location2: List[float], 
                         tolerance: float) -> bool:
        """检查两个位置是否在容差范围内
        
        Args:
            location1: 位置1 [纬度, 经度]
            location2: 位置2 [纬度, 经度]
            tolerance: 容差（米）
            
        Returns:
            是否在范围内
        """
        import math
        
        lat1, lon1 = math.radians(location1[0]), math.radians(location1[1])
        lat2, lon2 = math.radians(location2[0]), math.radians(location2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # 地球半径（米）
        r = 6371000
        distance = c * r
        
        return distance <= tolerance
    
    def get_memory_stats(self) -> Dict:
        """获取记忆统计信息
        
        Returns:
            统计信息字典
        """
        stats = self.get_path_statistics()
        stats['memory_type'] = '道路节点层记忆'
        return stats
    
    def clear_memory(self) -> None:
        """清空记忆"""
        self.node_sequences.clear()
        self.node_to_paths.clear()
        print("道路节点层记忆已清空")