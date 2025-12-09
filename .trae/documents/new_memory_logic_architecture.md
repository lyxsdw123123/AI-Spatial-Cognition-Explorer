# AI探索系统新记忆逻辑架构文档（基于JSON文件存储）

## 1. 项目概述

本文档描述了AI探索系统记忆逻辑的重大更新，从原有的具体经纬度位置记忆转变为以"探索路径单元"为核心的相对位置关系记忆系统。新系统将以一次完整的探索过程为单元，记录POI视野范围内的其他POI信息以及途径节点的相对位置关系。

**重要原则**：继续使用现有的JSON文件存储系统，不引入新的数据库，保持与现有系统的完全兼容性。

## 2. 新的记忆单元结构

### 2.1 路径单元定义

每个探索路径单元包含以下核心信息：

* **起点POI**: 路径的起始兴趣点

* **终点POI**: 路径的终点兴趣点

* **起点视野信息**: 起点POI视野范围内的所有POI及其相对位置

* **途径节点序列**: 从起点到终点经过的所有节点（包括道路节点和POI）

* **相对位置关系**: 每个节点与上一个节点的相对方向和距离

### 2.2 记忆单元数据结构

```json
{
  "path_id": "path_001",
  "start_poi": {
    "name": "POI1",
    "id": "poi_001",
    "visibility_range": [
      {
        "poi_name": "POI3",
        "direction": 45, // 相对于POI1的角度（度）
        "distance": 150  // 距离（米）
      },
      {
        "poi_name": "POI5",
        "direction": 120,
        "distance": 200
      }
    ]
  },
  "route_nodes": [
    {
      "node_type": "road_node",
      "name": "道路节点1",
      "relative_position": {
        "direction": 30,
        "distance": 80,
        "previous_node": "POI1"
      }
    },
    {
      "node_type": "poi",
      "name": "途径POI1",
      "relative_position": {
        "direction": 60,
        "distance": 100,
        "previous_node": "道路节点1"
      }
    }
  ],
  "end_poi": {
    "name": "POI2",
    "id": "poi_002",
    "relative_position": {
      "direction": 90,
      "distance": 120,
      "previous_node": "途径POI1"
    }
  }
}
```

## 3. POI视野范围记录机制

### 3.1 视野范围计算

* **视野半径**: 默认设置为200米（可配置）

* **角度计算**: 使用方位角公式计算相对方向

* **距离计算**: 使用Haversine公式计算球面距离

### 3.2 相对位置计算算法

```python
def calculate_relative_position(from_coord, to_coord):
    """
    计算从一个坐标点到另一个坐标点的相对位置
    
    Args:
        from_coord: 起始坐标 (lat, lng)
        to_coord: 目标坐标 (lat, lng)
    
    Returns:
        dict: 包含方向(度)和距离(米)的字典
    """
    # 计算方位角（方向）
    lat1, lng1 = radians(from_coord[0]), radians(from_coord[1])
    lat2, lng2 = radians(to_coord[0]), radians(to_coord[1])
    
    d_lng = lng2 - lng1
    y = sin(d_lng) * cos(lat2)
    x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(d_lng)
    
    bearing = degrees(atan2(y, x))
    bearing = (bearing + 360) % 360  # 标准化到0-360度
    
    # 计算距离（米）
    distance = haversine_distance(from_coord, to_coord)
    
    return {
        "direction": round(bearing, 1),
        "distance": round(distance, 1)
    }
```

### 3.3 视野POI筛选规则

* 只记录有有效名称的POI（过滤掉无名节点）

* 按距离排序，优先记录较近的POI

* 最多记录视野范围内的前10个POI（可配置）

## 4. 途径节点记录机制

### 4.1 节点类型定义

* **道路节点**: 路网中的交叉点或重要节点

* **途径POI**: 探索路径上经过的POI点

* **终点POI**: 当前路径的终点，同时也是下一路径的起点

### 4.2 节点记录时机

* AI移动过程中实时检测经过的节点

* 当AI与节点距离小于阈值（如20米）时触发记录

* 记录节点与上一个节点的相对位置关系

### 4.3 节点记录数据结构

```json
{
  "node_sequence": [
    {
      "sequence_id": 1,
      "node_type": "start_poi",
      "name": "起点POI1",
      "coordinates": null,  // 不存储具体坐标
      "visibility_info": [...]  // 只起点有视野信息
    },
    {
      "sequence_id": 2,
      "node_type": "road_node",
      "name": "道路节点1",
      "relative_position": {
        "direction": 45,
        "distance": 80,
        "previous_node": "起点POI1"
      }
    }
  ]
}
```

## 5. 新的探索上下文格式

### 5.1 路径级上下文格式

```
路径{序号}：起点{POI名称}->终点{POI名称}
信息：
1. 起点{起点名称}视野范围内的POI
有：{POI3名称}（相对于{起点名称}位置关系，方向：{角度}度，距离：{距离}米），
   {POI5名称}（方向：{角度}度，距离：{距离}米）
2. 途径点有：
   {道路节点1名称}（与上一个节点{起点名称}的相对位置关系，方向：{角度}度，距离：{距离}米），
   {道路节点2名称}（与道路节点1的相对位置关系，方向：{角度}度，距离：{距离}米），
   {途径POI1名称}（与道路节点2的相对位置关系，方向：{角度}度，距离：{距离}米），
   终点{终点名称}（与上一个节点的相对位置关系，方向：{角度}度，距离：{距离}米）
```

### 5.2 总结级上下文格式

```
总和：
已访问POI数量：{数量}
已访问道路节点数量（只要Name字段的）：{数量}
总探索距离：{距离}米
探索时间：{时间}秒
```

### 5.3 完整上下文示例

```
路径1：起点POI1->终点POI2
信息：
1. 起点POI1视野范围内的POI
有：POI3（相对于POI1位置关系，方向：45度，距离：150米），
   POI5（方向：120度，距离：200米），
   POI6（方向：270度，距离：180米）
2. 途径点有：
   道路节点1（与上一个节点POI1的相对位置关系，方向：30度，距离：80米），
   道路节点2（与道路节点1的相对位置关系，方向：60度，距离：100米），
   途径POI1（与道路节点2的相对位置关系，方向：90度，距离：120米），
   终点POI2（与上一个节点的相对位置关系，方向：45度，距离：150米）

路径2：起点POI2->终点POI3
信息：
1. 起点POI2视野范围内的POI
有：POI4（相对于POI2位置关系，方向：90度，距离：100米），
   POI7（方向：180度，距离：250米）
2. 途径点有：
   道路节点3（与上一个节点POI2的相对位置关系，方向：135度，距离：90米），
   终点POI3（与上一个节点的相对位置关系，方向：180度，距离：200米）

总和：
已访问POI数量：3
已访问道路节点数量（只要Name字段的）：3
总探索距离：7959米
探索时间：182秒
```

## 6. 坐标计算和单位转换方法

### 6.1 坐标系统

* 使用WGS84坐标系统（经纬度）

* 所有计算基于球面几何

### 6.2 距离计算公式

```python
def haversine_distance(coord1, coord2):
    """
    使用Haversine公式计算两点间的球面距离
    
    Args:
        coord1: (lat, lng) 起始坐标
        coord2: (lat, lng) 目标坐标
    
    Returns:
        float: 距离（米）
    """
    R = 6371000  # 地球半径（米）
    lat1, lng1 = radians(coord1[0]), radians(coord1[1])
    lat2, lng2 = radians(coord2[0]), radians(coord2[1])
    
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    distance = R * c
    return distance
```

### 6.3 方位角计算

```python
def calculate_bearing(from_coord, to_coord):
    """
    计算从一个坐标点到另一个坐标点的方位角
    
    Args:
        from_coord: (lat, lng) 起始坐标
        to_coord: (lat, lng) 目标坐标
    
    Returns:
        float: 方位角（度，0-360）
    """
    lat1, lng1 = radians(from_coord[0]), radians(from_coord[1])
    lat2, lng2 = radians(to_coord[0]), radians(to_coord[1])
    
    dlng = lng2 - lng1
    
    y = sin(dlng) * cos(lat2)
    x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlng)
    
    bearing = degrees(atan2(y, x))
    bearing = (bearing + 360) % 360
    
    return bearing
```

### 6.4 单位转换

* 距离：统一使用米（m）作为单位

* 方向：使用度（°）作为单位，范围0-360

* 时间：使用秒（s）作为单位

## 7. 数据存储结构修改方案

### 7.1 现有系统说明

**重要说明**：我们继续使用现有的JSON文件存储系统，不引入新的数据库。当前系统已经很好地满足了数据存储需求，使用JSON文件具有以下优势：

* 简单易用，无需额外的数据库配置

* 便于调试和数据查看

* 与现有代码完全兼容

* 支持版本控制和数据备份

### 7.2 现有数据结构分析

当前系统存储：

* POI具体坐标位置

* 道路节点具体坐标位置

* 探索路径的经纬度序列

* 访问计数统计

### 7.3 新数据结构需求

在保持现有JSON文件存储的基础上，需要新增以下数据结构：

* 路径单元记忆结构

* 相对位置关系记录

* 视野范围记录

* 节点序列记录

### 7.4 JSON数据结构扩展设计

#### 7.4.1 路径单元数据结构 (path\_units)

```json
{
  "path_units": {
    "path_001": {
      "path_id": "path_001",
      "session_id": "session_20251105_143022",
      "path_sequence": 1,
      "start_poi_name": "天安门",
      "end_poi_name": "故宫博物院",
      "total_distance_meters": 450,
      "exploration_time_seconds": 120,
      "created_at": "2025-11-05T14:30:22.123Z",
      "visibility_info": {
        "天安门": [
          {
            "visible_poi_name": "人民大会堂",
            "relative_direction_degrees": 45.2,
            "relative_distance_meters": 180
          },
          {
            "visible_poi_name": "国家博物馆",
            "relative_direction_degrees": 135.8,
            "relative_distance_meters": 200
          }
        ]
      },
      "route_nodes": [
        {
          "sequence_order": 1,
          "node_type": "start_poi",
          "node_name": "天安门",
          "node_description": "起点POI"
        },
        {
          "sequence_order": 2,
          "node_type": "road_node",
          "node_name": "长安街交叉口",
          "relative_direction_degrees": 30.5,
          "relative_distance_meters": 80,
          "previous_node_name": "天安门"
        },
        {
          "sequence_order": 3,
          "node_type": "end_poi",
          "node_name": "故宫博物院",
          "relative_direction_degrees": 15.2,
          "relative_distance_meters": 120,
          "previous_node_name": "长安街交叉口"
        }
      ]
    }
  }
}
```

#### 7.4.2 探索统计数据结构 (exploration\_stats)

```json
{
  "exploration_stats": {
    "session_20251105_143022": {
      "session_id": "session_20251105_143022",
      "total_pois_visited": 8,
      "total_road_nodes_visited": 15,
      "total_distance_meters": 2800,
      "total_time_seconds": 720,
      "path_count": 5,
      "created_at": "2025-11-05T14:30:22.123Z",
      "updated_at": "2025-11-05T14:42:22.456Z"
    }
  }
}
```

#### 7.4.3 相对位置关系缓存 (relative\_positions)

```json
{
  "relative_positions": {
    "天安门_人民大会堂": {
      "from_node": "天安门",
      "to_node": "人民大会堂",
      "relative_direction_degrees": 45.2,
      "relative_distance_meters": 180,
      "calculation_timestamp": "2025-11-05T14:30:22.123Z"
    },
    "长安街交叉口_故宫博物院": {
      "from_node": "长安街交叉口",
      "to_node": "故宫博物院",
      "relative_direction_degrees": 15.2,
      "relative_distance_meters": 120,
      "calculation_timestamp": "2025-11-05T14:31:45.678Z"
    }
  }
}
```

### 7.5 文件存储策略

#### 7.5.1 文件命名规范

* 路径单元数据：`path_units_{session_id}_{timestamp}.json`

* 统计数据：`exploration_stats_{session_id}.json`

* 相对位置缓存：`relative_positions_{session_id}.json`

#### 7.5.2 存储目录结构

```
data/
├── mental_maps/          # 原有的心理地图数据
├── path_units/           # 新增的路径单元数据
├── exploration_stats/    # 新增的探索统计数据
├── relative_positions/   # 新增的相对位置缓存
└── session_data/         # 会话级别的综合数据
```

#### 7.5.3 数据整合方案

为了保持与现有系统的兼容性，我们将：

1. 保留原有的JSON文件格式和存储逻辑
2. 新增的数据结构存储在独立的文件中
3. 在需要时，通过session\_id关联不同文件中的数据
4. 提供统一的API接口，屏蔽底层的数据存储细节

## 8. 实施步骤和优先级

### 8.1 第一阶段：核心算法开发（高优先级）

1. **坐标计算工具开发**

   * 实现Haversine距离计算

   * 实现方位角计算

   * 实现相对位置计算

   * 完成单元测试

2. **视野范围检测算法**

   * 实现POI视野范围检测

   * 实现相对位置关系计算

   * 实现节点过滤逻辑（只记录有名称的节点）

3. **路径单元构建逻辑**

   * 实现路径开始/结束检测

   * 实现节点序列记录

   * 实现相对位置关系存储

### 8.2 第二阶段：JSON数据存储层扩展（高优先级）

1. **JSON文件结构定义**

   * 定义路径单元JSON文件格式

   * 定义探索统计JSON文件格式

   * 定义相对位置缓存JSON文件格式

   * 创建示例文件和验证脚本

2. **文件存储管理器开发**

   * 实现路径单元文件读写接口

   * 实现探索统计文件管理

   * 实现相对位置缓存管理

   * 实现文件版本控制和备份机制

### 8.3 第三阶段：记忆管理器重构（中优先级）

1. **PathMemoryManager重构**

   * 移除具体坐标存储逻辑

   * 新增路径单元管理

   * 新增相对位置关系管理

   * 保持向后兼容性

2. **ExplorerAgent适配**

   * 修改探索过程中的节点记录逻辑

   * 集成新的记忆管理器

   * 保持探索行为一致性

### 8.4 第四阶段：上下文生成器开发（中优先级）

1. **EvaluationAgent改造**

   * 实现新的上下文构建逻辑

   * 实现路径级上下文格式化

   * 实现总结级上下文格式化

2. **上下文模板系统**

   * 创建路径上下文模板

   * 创建总结上下文模板

   * 实现模板渲染引擎

### 8.5 第五阶段：前后端集成（低优先级）

1. **前端可视化适配**

   * 更新地图显示逻辑

   * 更新探索路径可视化

   * 更新节点信息显示

2. **API接口更新**

   * 更新探索数据返回格式

   * 更新上下文生成接口

   * 保持API向后兼容性

### 8.6 第六阶段：测试与验证（低优先级）

1. **单元测试**

   * 测试坐标计算算法

   * 测试视野范围检测

   * 测试相对位置计算

2. **集成测试**

   * 测试完整探索流程

   * 测试上下文生成

   * 测试数据一致性

## 9. 风险评估与缓解措施

### 9.1 技术风险

* **坐标计算精度**: 使用成熟的地理计算库，进行充分测试

* **性能问题**: 优化JSON文件读写，使用内存缓存减少文件IO

* **数据一致性**: 实现文件锁机制和备份策略，确保数据完整性

### 9.2 兼容性风险

* **现有数据迁移**: 保留原有数据结构，逐步迁移

* **API兼容性**: 保持现有API接口，新增v2版本

* **前端适配**: 分阶段更新，保持功能可用

### 9.3 缓解措施

* 分阶段实施，每个阶段都有完整的测试

* 保留原有功能作为fallback机制

* 建立完整的数据备份和恢复机制

## 10. 预期效果

### 10.1 记忆效果提升

* 更符合人类认知方式的位置记忆

* 更丰富的空间关系信息

* 更准确的相对位置描述

### 10.2 系统性能优化

* 减少具体坐标数据的存储

* 优化查询性能

* 提升上下文生成效率

### 10.3 用户体验改善

* 更自然的探索上下文描述

* 更准确的AI心理地图评估

* 更丰富的问答交互体验

