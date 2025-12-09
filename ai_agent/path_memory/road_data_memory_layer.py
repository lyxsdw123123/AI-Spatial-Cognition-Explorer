# 道路数据层记忆系统

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid

class RoadDataMemoryLayer:
    """道路数据层记忆系统 - 记录道路段信息"""
    
    def __init__(self):
        # 道路段信息
        self.road_segments = {}  # key: segment_id, value: segment_info
        # 节点到道路段的映射
        self.node_to_segments = {}  # key: node_id, value: [segment_ids]
        
    def record_road_segment(self, start_node: str, end_node: str, 
                          segment_data: Dict) -> str:
        """记录道路段信息
        
        Args:
            start_node: 起始节点ID或坐标
            end_node: 终止节点ID或坐标
            segment_data: 道路段数据 {length, road_type, coordinates, etc.}
            
        Returns:
            道路段ID
        """
        # 生成道路段ID
        segment_id = segment_data.get('id', str(uuid.uuid4()))
        
        # 处理节点信息
        start_node_id = self._process_node_id(start_node)
        end_node_id = self._process_node_id(end_node)
        
        # 创建道路段信息
        segment_info = {
            "segment_id": segment_id,
            "start_node": start_node_id,
            "end_node": end_node_id,
            "length": segment_data.get('length', 0),
            "road_type": segment_data.get('road_type', '未知'),
            "road_name": segment_data.get('road_name', ''),
            "coordinates": segment_data.get('coordinates', []),
            "traversal_count": 1,
            "created_time": datetime.now().isoformat(),
            "last_traversed": datetime.now().isoformat(),
            "speed_limit": segment_data.get('speed_limit', 0),
            "road_condition": segment_data.get('road_condition', '良好')
        }
        
        # 如果道路段已存在，更新信息
        if segment_id in self.road_segments:
            existing = self.road_segments[segment_id]
            existing['traversal_count'] += 1
            existing['last_traversed'] = datetime.now().isoformat()
            # 更新长度信息（取平均值）
            if segment_data.get('length', 0) > 0:
                existing['length'] = (existing['length'] + segment_data['length']) / 2
        else:
            self.road_segments[segment_id] = segment_info
            
            # 更新节点到道路段的映射
            for node_id in [start_node_id, end_node_id]:
                if node_id not in self.node_to_segments:
                    self.node_to_segments[node_id] = []
                if segment_id not in self.node_to_segments[node_id]:
                    self.node_to_segments[node_id].append(segment_id)
        
        print(f"记录道路段: {segment_id}, 长度: {segment_info['length']:.1f}m, 类型: {segment_info['road_type']}")
        return segment_id
    
    def get_road_info(self, segment_id: str) -> Optional[Dict]:
        """获取道路段信息
        
        Args:
            segment_id: 道路段ID
            
        Returns:
            道路段信息或None
        """
        return self.road_segments.get(segment_id)
    
    def find_segments_by_nodes(self, start_node: str, end_node: str) -> List[Dict]:
        """根据起终点节点查找道路段
        
        Args:
            start_node: 起始节点ID
            end_node: 终止节点ID
            
        Returns:
            匹配的道路段列表
        """
        matching_segments = []
        
        start_node_id = self._process_node_id(start_node)
        end_node_id = self._process_node_id(end_node)
        
        for segment in self.road_segments.values():
            # 检查正向匹配
            if (segment['start_node'] == start_node_id and 
                segment['end_node'] == end_node_id):
                matching_segments.append(segment)
            # 检查反向匹配（道路通常是双向的）
            elif (segment['start_node'] == end_node_id and 
                  segment['end_node'] == start_node_id):
                matching_segments.append(segment)
        
        return matching_segments
    
    def find_segments_from_node(self, node_id: str) -> List[Dict]:
        """查找从指定节点出发的所有道路段
        
        Args:
            node_id: 节点ID
            
        Returns:
            道路段列表
        """
        segments = []
        processed_node_id = self._process_node_id(node_id)
        segment_ids = self.node_to_segments.get(processed_node_id, [])
        
        for segment_id in segment_ids:
            segment = self.road_segments.get(segment_id)
            if segment and segment['start_node'] == processed_node_id:
                segments.append(segment)
        
        return segments
    
    def find_segments_to_node(self, node_id: str) -> List[Dict]:
        """查找到达指定节点的所有道路段
        
        Args:
            node_id: 节点ID
            
        Returns:
            道路段列表
        """
        segments = []
        processed_node_id = self._process_node_id(node_id)
        segment_ids = self.node_to_segments.get(processed_node_id, [])
        
        for segment_id in segment_ids:
            segment = self.road_segments.get(segment_id)
            if segment and segment['end_node'] == processed_node_id:
                segments.append(segment)
        
        return segments
    
    def find_segments_by_road_type(self, road_type: str) -> List[Dict]:
        """根据道路类型查找道路段
        
        Args:
            road_type: 道路类型
            
        Returns:
            匹配的道路段列表
        """
        matching_segments = []
        
        for segment in self.road_segments.values():
            if segment['road_type'] == road_type:
                matching_segments.append(segment)
        
        return matching_segments
    
    def get_total_distance_by_road_type(self, road_type: str) -> float:
        """获取指定道路类型的总距离
        
        Args:
            road_type: 道路类型
            
        Returns:
            总距离（米）
        """
        total_distance = 0
        segments = self.find_segments_by_road_type(road_type)
        
        for segment in segments:
            total_distance += segment['length']
        
        return total_distance
    
    def get_most_traversed_segments(self, limit: int = 10) -> List[Dict]:
        """获取最常通行的道路段
        
        Args:
            limit: 返回数量限制
            
        Returns:
            按通行次数排序的道路段列表
        """
        segments = list(self.road_segments.values())
        segments.sort(key=lambda x: x['traversal_count'], reverse=True)
        return segments[:limit]
    
    def update_segment_traversal(self, segment_id: str) -> None:
        """更新道路段通行次数
        
        Args:
            segment_id: 道路段ID
        """
        if segment_id in self.road_segments:
            self.road_segments[segment_id]['traversal_count'] += 1
            self.road_segments[segment_id]['last_traversed'] = datetime.now().isoformat()
            print(f"更新道路段通行次数: {segment_id}, 次数: {self.road_segments[segment_id]['traversal_count']}")
    
    def get_road_network_stats(self) -> Dict:
        """获取道路网络统计信息
        
        Returns:
            统计信息字典
        """
        if not self.road_segments:
            return {
                'total_segments': 0,
                'total_nodes': 0,
                'total_distance': 0,
                'road_types': {}
            }
        
        total_segments = len(self.road_segments)
        total_nodes = len(self.node_to_segments)
        total_distance = sum(segment['length'] for segment in self.road_segments.values())
        
        # 统计道路类型
        road_types = {}
        for segment in self.road_segments.values():
            road_type = segment['road_type']
            if road_type not in road_types:
                road_types[road_type] = {'count': 0, 'total_length': 0}
            road_types[road_type]['count'] += 1
            road_types[road_type]['total_length'] += segment['length']
        
        return {
            'total_segments': total_segments,
            'total_nodes': total_nodes,
            'total_distance': round(total_distance, 2),
            'road_types': road_types,
            'average_segment_length': round(total_distance / total_segments, 2) if total_segments > 0 else 0
        }
    
    def _process_node_id(self, node: str) -> str:
        """处理节点ID，确保格式一致
        
        Args:
            node: 节点ID或坐标
            
        Returns:
            处理后的节点ID
        """
        if isinstance(node, (list, tuple)):
            # 如果是坐标，转换为字符串ID
            return f"node_{node[0]}_{node[1]}"
        else:
            # 如果已经是字符串ID，直接返回
            return str(node)
    
    def get_memory_stats(self) -> Dict:
        """获取记忆统计信息
        
        Returns:
            统计信息字典
        """
        stats = self.get_road_network_stats()
        stats['memory_type'] = '道路数据层记忆'
        return stats
    
    def clear_memory(self) -> None:
        """清空记忆"""
        self.road_segments.clear()
        self.node_to_segments.clear()
        print("道路数据层记忆已清空")