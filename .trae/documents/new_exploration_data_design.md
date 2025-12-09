# 新 Exploration Data 数据结构设计方案

## 1. 设计目标

实现以"路径单元"为核心的记忆逻辑，将探索过程拆分为多个子路径（如"路径1：起点POI1->终点POI2"），每个子路径记录：

* 起点POI视野范围内的其他POI及其相对位置（方向+距离）

* 途径点（道路节点、POI）与上一个点的相对位置关系

* 统计信息：已访问POI数量、已访问道路节点数量、总探索距离、探索时间

1. 2\. 新的数据结构

```python
exploration_data = {
    'exploration_paths': [  # 探索路径列表（按时间顺序）
        {
            'path_id': 'path_001',
            'path_name': '路径1：起点POI1->终点POI2',
            'start_poi': {
                'id': 'poi_001',
                'name': 'POI1名称'
            },
            'end_poi': {
                'id': 'poi_002', 
                'name': 'POI2名称'
            },
            'start_poi_vision_range': [  # 起点POI视野范围内的POI
                {
                    'poi_id': 'poi_003',
                    'poi_name': 'POI3名称',
                    'relative_position': {
                        'direction': 45,  # 相对于起点POI的方向（度）
                        'distance': 150   # 距离（米）
                    },
                },
                {
                    'poi_id': 'poi_005', 
                    'poi_name': 'POI5名称',
                    'relative_position': {
                        'direction': 120,
                        'distance': 200
                    },
                }
            ],
            'route_points': [  # 途径点序列（按访问顺序）
                {
                    'point_type': 'road_node',  # 道路节点
                    'name': '道路节点1',  # 有Name字段的道路节点
                    'relative_position': {
                        'direction': 30,   # 相对于上一个点的方向
                        'distance': 80     # 相对于上一个点的距离（米）
                    }
                },
                {
                    'point_type': 'road_node',
                    'name': '道路节点2',
                    'relative_position': {
                        'direction': 60,
                        'distance': 100
                    }
                },
                {
                    'point_type': 'poi',  # 途径POI
                    'poi_id': 'poi_xxx',
                    'poi_name': '途径POI1',
                    'relative_position': {
                        'direction': 90,
                        'distance': 120
                    }
                },
                {
                    'point_type': 'end_poi',  # 终点POI（与end_poi对应）
                    'poi_id': 'poi_002',
                    'poi_name': 'POI2名称', 
                    'relative_position': {
                        'direction': 45,
                        'distance': 150
                    }
                }
            ],
            'path_distance': 450,  # 该路径总距离（米）
            'path_time': 45,       # 该路径耗时（秒）
            'created_at': '2025-11-06T19:36:21'
        }
    ],
    'exploration_summary': {  # 探索汇总信息
        'total_pois_visited': 3,            # 已访问POI总数
        'total_road_nodes_visited': 3,      # 已访问道路节点总数（只统计有Name字段的）
        'total_distance_meters': 7959,      # 总探索距离（米）
        'total_time_seconds': 182,          # 总探索时间（秒）
        'exploration_start_time': '2025-11-06T19:36:00',
        'exploration_end_time': '2025-11-06T19:39:02'
    },
    'road_nodes_data': {  # 道路节点数据（用于名称匹配）
        'nodes_with_names': [  # 有名称的道路节点
            {'name': '道路节点1'},
            {'name': '道路节点2'},
            {'name': '道路节点3'}
        ]
    }
}
```

## 3. 数据获取与计算方法

### 3.1 获取起点POI视野范围内的POI

```python
def get_pois_in_vision_range(self, center_poi, all_pois, vision_radius=1000):
    """获取中心POI视野范围内的其他POI"""
    vision_pois = []
    center_location = center_poi['location']
    
    for poi in all_pois:
        if poi['id'] == center_poi['id']:  # 排除中心POI自身
            continue
            
        # 计算距离
        distance = self.map_service.calculate_distance(center_location, poi['location'])
        
        if distance <= vision_radius:  # 在视野范围内
            # 计算方向
            direction = self._calculate_direction(center_location, poi['location'])
            
            vision_pois.append({
                'poi_id': poi['id'],
                'poi_name': poi['name'],
                'relative_position': {
                    'direction': round(direction),
                    'distance': round(distance)
                }
            })
    
    return vision_pois
```

### 3.2 计算相对方向和距离

```python
def _calculate_relative_position(self, from_location, to_location):
    """计算两个位置之间的相对位置和距离"""
    # 计算距离（米）
    distance = self.map_service.calculate_distance(from_location, to_location)
    
    # 计算方向（度）
    direction = self._calculate_direction(from_location, to_location)
    
    return {
        'direction': round(direction),
        'distance': round(distance)
    }

def _calculate_direction(self, from_location, to_location):
    """计算从一个位置到另一个位置的方向角度"""
    from_lat, from_lng = from_location
    to_lat, to_lng = to_location
    
    # 计算纬度差和经度差
    lat_diff = to_lat - from_lat
    lng_diff = to_lng - from_lng
    
    # 使用atan2计算角度（弧度）
    angle_rad = math.atan2(lng_diff, lat_diff)
    
    # 转换为度数，并调整为0-360度范围
    angle_deg = math.degrees(angle_rad)
    if angle_deg < 0:
        angle_deg += 360
        
    return angle_deg
```

### 3.3 记录路径序列

```python
def build_route_points(self, path_sequence, start_poi_location):
    """构建途径点序列，包含相对位置信息"""
    route_points = []
    previous_location = start_poi_location
    
    for point in path_sequence:
        point_data = {
            'point_type': point.get('type', 'unknown'),
            'relative_position': self._calculate_relative_position(
                previous_location, 
                point['location']
            )
        }
        
        # 根据点类型添加特定信息
        if point['type'] == 'road_node':
            if 'name' in point and point['name']:  # 只记录有名称的道路节点
                point_data['name'] = point['name']
        elif point['type'] == 'poi':
            point_data['poi_id'] = point.get('id')
            point_data['poi_name'] = point.get('name')
        
        route_points.append(point_data)
        previous_location = point['location']  # 更新上一个位置
    
    return route_points
```

## 4. 统计信息计算

### 4.1 已访问POI数量统计

```python
def count_visited_pois(self, exploration_paths):
    """统计已访问的POI数量"""
    visited_poi_ids = set()
    
    for path in exploration_paths:
        # 记录起点POI
        if 'start_poi' in path and path['start_poi']:
            visited_poi_ids.add(path['start_poi']['id'])
        
        # 记录终点POI
        if 'end_poi' in path and path['end_poi']:
            visited_poi_ids.add(path['end_poi']['id'])
        
        # 记录途径POI
        for point in path.get('route_points', []):
            if point['point_type'] == 'poi' and 'poi_id' in point:
                visited_poi_ids.add(point['poi_id'])
    
    return len(visited_poi_ids)
```

### 4.2 已访问道路节点数量统计

```python
def count_visited_road_nodes(self, exploration_paths):
    """统计已访问的有名称道路节点数量"""
    visited_node_names = set()
    
    for path in exploration_paths:
        for point in path.get('route_points', []):
            if (point['point_type'] == 'road_node' and 
                'name' in point and 
                point['name']):  # 只统计有名称的道路节点
                visited_node_names.add(point['name'])
    
    return len(visited_node_names)
```

### 4.3 总探索距离和时间

```python
def calculate_exploration_stats(self, exploration_paths):
    """计算探索统计信息"""
    total_distance = 0
    total_time = 0
    
    for path in exploration_paths:
        total_distance += path.get('path_distance', 0)
        total_time += path.get('path_time', 0)
    
    return {
        'total_distance_meters': round(total_distance),
        'total_time_seconds': round(total_time)
    }
```

## 5. 集成到现有系统

### 5.1 修改 explorer\_agent.py

在`explorer_agent.py`中添加新方法：

```python
exploration_data = {
    'exploration_paths': [  # 探索路径列表（按时间顺序）
        {
            'path_id': 'path_001',
            'path_name': '路径1：起点POI1->终点POI2',
            'start_poi': {
                'id': 'poi_001',
                'name': 'POI1名称'
            },
            'end_poi': {
                'id': 'poi_002', 
                'name': 'POI2名称'
            },
            'start_poi_vision_range': [  # 起点POI视野范围内的POI
                {
                    'poi_id': 'poi_003',
                    'poi_name': 'POI3名称',
                    'relative_position': {
                        'direction': 45,  # 相对于起点POI的方向（度）
                        'distance': 150   # 距离（米）
                    },
                },
                {
                    'poi_id': 'poi_005', 
                    'poi_name': 'POI5名称',
                    'relative_position': {
                        'direction': 120,
                        'distance': 200
                    },
                }
            ],
            'route_points': [  # 途径点序列（按访问顺序）
                {
                    'point_type': 'road_node',  # 道路节点
                    'name': '道路节点1',  # 有Name字段的道路节点
                    'relative_position': {
                        'direction': 30,   # 相对于上一个点的方向
                        'distance': 80     # 相对于上一个点的距离（米）
                    }
                },
                {
                    'point_type': 'road_node',
                    'name': '道路节点2',
                    'relative_position': {
                        'direction': 60,
                        'distance': 100
                    }
                },
                {
                    'point_type': 'poi',  # 途径POI
                    'poi_id': 'poi_xxx',
                    'poi_name': '途径POI1',
                    'relative_position': {
                        'direction': 90,
                        'distance': 120
                    }
                },
                {
                    'point_type': 'end_poi',  # 终点POI（与end_poi对应）
                    'poi_id': 'poi_002',
                    'poi_name': 'POI2名称', 
                    'relative_position': {
                        'direction': 45,
                        'distance': 150
                    }
                }
            ],
            'path_distance': 450,  # 该路径总距离（米）
            'path_time': 45,       # 该路径耗时（秒）
            'created_at': '2025-11-06T19:36:21'
        }
    ],
    'exploration_summary': {  # 探索汇总信息
        'total_pois_visited': 3,            # 已访问POI总数
        'total_road_nodes_visited': 3,      # 已访问道路节点总数（只统计有Name字段的）
        'total_distance_meters': 7959,      # 总探索距离（米）
        'total_time_seconds': 182,          # 总探索时间（秒）
        'exploration_start_time': '2025-11-06T19:36:00',
        'exploration_end_time': '2025-11-06T19:39:02'
    },
    'road_nodes_data': {  # 道路节点数据（用于名称匹配）
        'nodes_with_names': [  # 有名称的道路节点
            {'name': '道路节点1'},
            {'name': '道路节点2'},
            {'name': '道路节点3'}
        ]
    }
}
```

### 5.2 修改后端API

在`backend/main.py`中修改获取探索数据的接口：

```python
@app.get("/exploration/data")
async def get_exploration_data():
    """获取探索数据（新格式）"""
    try:
        # 使用新的数据结构构建方法
        exploration_data = explorer_agent.build_new_exploration_data()
        
        return {
            "success": True,
            "data": exploration_data,
            "message": "探索数据获取成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 6. 实施步骤

1. **第一阶段**：实现基础的数据结构定义和计算方法
2. **第二阶段**：修改路径记忆系统，支持新的路径单元记录
3. **第三阶段**：集成POI视野范围计算功能
4. **第四阶段**：实现途径点相对位置记录
5. **第五阶段**：添加统计信息计算
6. **第六阶段**：测试和优化

## 7. 优势特点

* **人类化记忆**：以路径为单元，符合人类的空间记忆方式

* **相对位置**：使用方向和距离，更直观理解空间关系

* **视野感知**：记录起点POI的视野范围，模拟真实观察场景

* **路径连续性**：保持路径序列的完整性

* **统计精确**：准确统计各类访问点的数量

* **兼容现有**：基于现有JSON文件存储，无需数据库改造

