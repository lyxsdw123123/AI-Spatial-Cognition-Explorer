# POI层记忆系统

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import math

class POIMemoryLayer:
    """POI层记忆系统 - 记录POI间连接关系和距离信息"""
    
    def __init__(self):
        # POI间连接关系
        self.poi_connections = {}  # key: "poi_a_id->poi_b_id", value: connection_info
        
    def record_poi_connection(self, start_poi: Dict, end_poi: Dict, path_data: Dict) -> None:
        """记录POI间连接关系
        
        Args:
            start_poi: 起始POI信息 {id, name, location, type}
            end_poi: 终点POI信息 {id, name, location, type}
            path_data: 路径数据 {actual_distance, nodes, segments}
        """
        start_id = start_poi['id']
        end_id = end_poi['id']
        
        # 创建连接键
        connection_key = f"{start_id}->{end_id}"
        
        # 计算直线距离
        direct_distance = self._calculate_direct_distance(
            start_poi['location'], end_poi['location']
        )
        
        # 获取实际路径距离
        actual_distance = path_data.get('actual_distance', direct_distance)
        
        # 记录连接信息
        connection_info = {
            "start_poi": {
                "id": start_id,
                "name": start_poi['name'],
                "location": start_poi['location'],
                "type": start_poi.get('type', '未知')
            },
            "end_poi": {
                "id": end_id,
                "name": end_poi['name'],
                "location": end_poi['location'],
                "type": end_poi.get('type', '未知')
            },
            "direct_distance": direct_distance,
            "actual_distance": actual_distance,
            "exploration_count": 1,
            "last_updated": datetime.now().isoformat(),
            "path_nodes": path_data.get('nodes', []),
            "path_segments": path_data.get('segments', [])
        }
        
        # 如果连接已存在，更新信息
        if connection_key in self.poi_connections:
            existing = self.poi_connections[connection_key]
            existing['exploration_count'] += 1
            existing['last_updated'] = datetime.now().isoformat()
            # 更新距离信息（取平均值）
            existing['actual_distance'] = (
                existing['actual_distance'] + actual_distance
            ) / 2
        else:
            self.poi_connections[connection_key] = connection_info
            
        print(f"记录POI连接: {start_poi['name']} -> {end_poi['name']}, 直线距离: {direct_distance:.1f}m, 实际距离: {actual_distance:.1f}m")
    
    def get_poi_distance(self, poi_a_id: str, poi_b_id: str) -> Optional[Dict]:
        """获取POI间距离信息
        
        Args:
            poi_a_id: POI A的ID
            poi_b_id: POI B的ID
            
        Returns:
            距离信息字典或None
        """
        # 尝试正向查找
        forward_key = f"{poi_a_id}->{poi_b_id}"
        if forward_key in self.poi_connections:
            return self.poi_connections[forward_key]
            
        # 尝试反向查找
        reverse_key = f"{poi_b_id}->{poi_a_id}"
        if reverse_key in self.poi_connections:
            # 返回反向连接信息，但交换起终点
            reverse_info = self.poi_connections[reverse_key].copy()
            reverse_info['start_poi'], reverse_info['end_poi'] = (
                reverse_info['end_poi'], reverse_info['start_poi']
            )
            return reverse_info
            
        return None
    
    def get_poi_connections_from(self, poi_id: str) -> List[Dict]:
        """获取从指定POI出发的所有连接
        
        Args:
            poi_id: POI的ID
            
        Returns:
            连接信息列表
        """
        connections = []
        for key, connection in self.poi_connections.items():
            if key.startswith(f"{poi_id}->"):
                connections.append(connection)
        return connections
    
    def get_poi_connections_to(self, poi_id: str) -> List[Dict]:
        """获取到达指定POI的所有连接
        
        Args:
            poi_id: POI的ID
            
        Returns:
            连接信息列表
        """
        connections = []
        for key, connection in self.poi_connections.items():
            if key.endswith(f"->{poi_id}"):
                connections.append(connection)
        return connections
    
    def get_all_connected_pois(self, poi_id: str) -> List[Dict]:
        """获取与指定POI相连的所有POI
        
        Args:
            poi_id: POI的ID
            
        Returns:
            相连POI信息列表
        """
        connected_pois = []
        
        # 获取出发连接
        for connection in self.get_poi_connections_from(poi_id):
            connected_pois.append({
                'poi': connection['end_poi'],
                'distance': connection['actual_distance'],
                'direction': 'outgoing'
            })
            
        # 获取到达连接
        for connection in self.get_poi_connections_to(poi_id):
            connected_pois.append({
                'poi': connection['start_poi'],
                'distance': connection['actual_distance'],
                'direction': 'incoming'
            })
            
        return connected_pois
    
    def find_shortest_path_between_pois(self, start_poi_id: str, end_poi_id: str) -> Optional[Dict]:
        """查找两个POI间的最短路径
        
        Args:
            start_poi_id: 起始POI ID
            end_poi_id: 终点POI ID
            
        Returns:
            路径信息或None
        """
        # 直接连接
        direct_connection = self.get_poi_distance(start_poi_id, end_poi_id)
        if direct_connection:
            return {
                'path_type': 'direct',
                'total_distance': direct_connection['actual_distance'],
                'connections': [direct_connection]
            }
        
        # 简单的一跳路径查找
        start_connections = self.get_poi_connections_from(start_poi_id)
        
        shortest_path = None
        shortest_distance = float('inf')
        
        for connection in start_connections:
            intermediate_poi_id = connection['end_poi']['id']
            second_connection = self.get_poi_distance(intermediate_poi_id, end_poi_id)
            
            if second_connection:
                total_distance = connection['actual_distance'] + second_connection['actual_distance']
                if total_distance < shortest_distance:
                    shortest_distance = total_distance
                    shortest_path = {
                        'path_type': 'via_poi',
                        'total_distance': total_distance,
                        'connections': [connection, second_connection],
                        'intermediate_poi': connection['end_poi']
                    }
        
        return shortest_path
    
    def _calculate_direct_distance(self, location1: List[float], location2: List[float]) -> float:
        """计算两点间直线距离（米）
        
        Args:
            location1: 位置1 [纬度, 经度]
            location2: 位置2 [纬度, 经度]
            
        Returns:
            距离（米）
        """
        lat1, lon1 = math.radians(location1[0]), math.radians(location1[1])
        lat2, lon2 = math.radians(location2[0]), math.radians(location2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # 地球半径（米）
        r = 6371000
        return c * r
    
    def get_memory_stats(self) -> Dict:
        """获取记忆统计信息
        
        Returns:
            统计信息字典
        """
        total_connections = len(self.poi_connections)
        unique_pois = set()
        
        for connection in self.poi_connections.values():
            unique_pois.add(connection['start_poi']['id'])
            unique_pois.add(connection['end_poi']['id'])
        
        return {
            'total_connections': total_connections,
            'unique_pois': len(unique_pois),
            'memory_type': 'POI层记忆'
        }
    
    def clear_memory(self) -> None:
        """清空记忆"""
        self.poi_connections.clear()
        print("POI层记忆已清空")