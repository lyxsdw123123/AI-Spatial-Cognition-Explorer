# AI探索智能体模块

import asyncio
import random
import math
from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime
from langchain_community.llms import Tongyi
from langchain.prompts import PromptTemplate
from langchain.schema import BaseOutputParser
from config.config import Config
from map_service.amap_service import AmapService
from .path_memory import PathMemoryManager

class ExplorerAgent:
    """AI探索智能体"""
    
    def __init__(self):
        self.current_location = None  # 当前位置 [纬度, 经度]
        self.exploration_boundary = None  # 探索边界
        self.vision_radius = Config.AI_VISION_RADIUS
        self.move_speed = Config.AI_MOVE_SPEED
        self.move_interval = Config.AI_MOVE_INTERVAL
        
        # 探索状态
        self.is_exploring = False
        self.exploration_path = []  # 探索路径（保留用于兼容性）
        self.visited_pois = set()  # 已访问的POI ID
        self.interesting_pois = []  # 感兴趣的POI
        self.mental_map = {}  # 心理地图（保留用于兼容性）
        
        # 三层路径记忆系统
        self.path_memory = PathMemoryManager()
        self.memory_mode = "context"
        self.exploration_round = 1
        self.rounds_completed = 0
        self.ever_visited_pois = set()
        self.all_boundary_pois = []
        self.total_pois_targets = 0
        self.exploration_complete = False
        
        # 位置历史记录机制 - 防止徘徊
        self.position_history = []  # 最近访问的位置历史
        self.max_history_size = 20  # 保存最近20个位置
        self.min_move_distance = 50  # 最小移动距离（米）
        self.avoid_radius = 100  # 避免重复访问的半径（米）
        self.direction_history = []  # 最近的移动方向历史
        self.max_direction_history = 10  # 保存最近10个方向
        
        # 地图服务
        self.map_service = AmapService()
        
        # 最短路径探索的两阶段移动状态
        self.shortest_path_stage = None  # 存储两阶段移动的状态信息
        
        # AI模型
        self.llm = Tongyi(
            dashscope_api_key=Config.DASHSCOPE_API_KEY,
            model_name="qwen-turbo",
            temperature=0.7
        )
        
        # 决策提示模板
        self.decision_prompt = PromptTemplate(
            input_variables=["current_location", "visible_pois", "exploration_history", "mental_map"],
            template="""
            你是一个AI探索者，正在探索一个陌生的地图区域。
            
            当前位置：{current_location}
            视野内的POI：{visible_pois}
            探索历史：{exploration_history}
            当前心理地图：{mental_map}
            
            请根据以下规则做出决策：
            1. 如果视野内有未探索的有趣POI，选择最感兴趣的一个前往
            2. 如果视野内没有POI，选择一个合理的方向继续探索
            3. 避免重复访问已经探索过的区域
            4. 记录对POI的兴趣程度和相对位置关系
            
            请以JSON格式返回决策：
            {
                "action": "move_to_poi" 或 "explore_direction",
                "target": "目标POI名称" 或 "方向角度(0-360度)",
                "reason": "决策理由",
                "interest_level": "对目标的兴趣程度(1-10)",
                "notes": "对当前环境的观察和记录"
            }
            """
        )
    
    async def initialize(self, start_location: Tuple[float, float], 
                        boundary: List[Tuple[float, float]],
                        use_local_data: bool = False,
                        exploration_mode: str = "随机POI探索",
                        local_data_service = None):
        """初始化AI探索者
        
        Args:
            start_location: 起始位置 [纬度, 经度]
            boundary: 探索边界多边形顶点列表
            use_local_data: 是否使用本地数据模式
            exploration_mode: 探索模式（随机POI探索、最近距离探索、随机选择两个POI进行最短路径探索）
            local_data_service: 本地数据服务实例
        """
        self.current_location = list(start_location)
        self.exploration_boundary = boundary
        self.use_local_data = use_local_data
        self.exploration_mode = exploration_mode
        self.local_data_service = local_data_service
        
        # 初始化路径记忆系统
        self.path_memory.initialize(start_location, boundary, exploration_mode)
        
        # 保留原有数据结构用于兼容性
        self.exploration_path = [{
            'location': self.current_location.copy(),
            'timestamp': datetime.now(),
            'action': 'start',
            'notes': f'开始探索 - 模式：{exploration_mode}'
        }]
        self.mental_map = {
            'start_location': self.current_location.copy(),
            'boundary': boundary,
            'poi_relationships': {},
            'interesting_areas': [],
            'use_local_data': use_local_data,
            'exploration_mode': exploration_mode
        }
        
        # 如果使用本地数据模式，确保AI位置在道路上
        if use_local_data and local_data_service:
            self._ensure_on_road()
    
    def _ensure_on_road(self):
        """确保AI位置在道路上，如果不在则移动到最近的道路"""
        if not self.local_data_service:
            return
            
        try:
            # 获取当前位置到最近道路的投影点
            projected_point = self.local_data_service.project_point_to_road(
                (self.current_location[1], self.current_location[0])  # (经度, 纬度)
            )
            
            if projected_point:
                old_location = self.current_location.copy()
                self.current_location = [projected_point[1], projected_point[0]]  # 纬度, 经度
                
                # 记录移动到道路的动作
                self.exploration_path.append({
                    'location': self.current_location.copy(),
                    'timestamp': datetime.now(),
                    'action': 'move_to_road',
                    'notes': f'从 {old_location} 移动到最近道路 {self.current_location}'
                })
                
                # 记录到路径记忆系统 - 使用详细版本
                path_data = {
                    'start_location': old_location,
                    'end_location': self.current_location,
                    'nodes': [f"起始位置_{old_location[0]:.6f}_{old_location[1]:.6f}", 
                             f"道路位置_{self.current_location[0]:.6f}_{self.current_location[1]:.6f}"],
                    'segments': [{
                        'name': '移动到道路',
                        'length': self._calculate_distance(old_location, self.current_location),
                        'road_type': '调整路径',
                        'coordinates': [old_location, self.current_location]
                    }],
                    'poi_waypoints': [],
                    'total_distance': self._calculate_distance(old_location, self.current_location),
                    'start_poi': None,
                    'end_poi': None
                }
                self.path_memory.record_exploration_path_detailed(path_data)
                
                print(f"AI位置已调整到道路上: {self.current_location}")
        except Exception as e:
            print(f"移动到道路时出错: {e}")
    
    async def start_exploration(self):
        """开始探索"""
        try:
            if (not self.is_exploring) and len(self.visited_pois) > 0:
                self.ever_visited_pois |= set(self.visited_pois)
                self.rounds_completed += 1
                self.exploration_round = self.rounds_completed + 1
                self.visited_pois = set()
                self.exploration_path = []
                self._current_action = None
                self._last_decision = None
                self.position_history = []
                self.direction_history = []
        except Exception:
            pass
        self.is_exploring = True
        print(f"AI开始探索，起始位置：{self.current_location}")
        
        # 在开始探索时自动获取边界内的所有POI
        await self._load_boundary_pois()
        
        while self.is_exploring:
            try:
                print(f"\n🔍 AI正在探索...")
                print(f"📍 当前位置：({self.current_location[0]:.6f}, {self.current_location[1]:.6f})")
                
                # 获取视野内的POI
                visible_pois = await self._get_visible_pois()
                if self._has_completed_poi_cycle():
                    self.exploration_complete = True
                    self._current_action = "所有POI已探索，开启下一轮"
                    try:
                        self.ever_visited_pois |= set(self.visited_pois)
                        self.rounds_completed += 1
                        self.exploration_round = self.rounds_completed + 1
                        self.visited_pois = set()
                        self.exploration_path = []
                        self._last_decision = None
                        self.position_history = []
                        self.direction_history = []
                    except Exception:
                        pass
                    continue
                else:
                    self.exploration_complete = False
                print(f"👀 视野内发现 {len(visible_pois)} 个未访问POI")
                if visible_pois:
                    print("🤔 AI正在分析并做出决策...")
                
                # AI决策
                self._current_action = "正在分析POI并做决策"
                decision = await self._make_decision(visible_pois)
                
                # 保存最近的决策
                self._last_decision = decision
                
                # 执行决策
                self._current_action = f"执行决策：{decision.get('action', '未知')}"
                await self._execute_decision(decision)
                
                # 决策执行后等待更长时间
                if visible_pois:
                    print("⏳ 等待下一次决策...")
                    await asyncio.sleep(5)  # 有POI时等待5秒
                else:
                    await asyncio.sleep(2)  # 无POI时等待2秒
                
            except Exception as e:
                print(f"探索过程中出错：{e}")
                await asyncio.sleep(1)
    
    def stop_exploration(self):
        """停止探索"""
        self.is_exploring = False
        print("AI停止探索")
        return self._generate_exploration_report()
    
    async def _load_boundary_pois(self):
        """在开始探索时加载边界内的所有POI"""
        try:
            if self.exploration_boundary:
                print("正在加载边界内的POI...")
                
                # 根据数据模式选择不同的POI加载方式
                if self.use_local_data and self.local_data_service:
                    # 使用本地数据模式
                    print("使用本地数据模式加载POI")
                    boundary_pois = self.local_data_service.get_poi_data()
                    
                    # 过滤边界内的POI
                    filtered_pois = []
                    for poi in boundary_pois:
                        # 将location字典转换为元组格式 (lat, lng)
                        poi_location = (poi['location']['lat'], poi['location']['lng'])
                        if self._is_within_boundary(poi_location):
                            # 同时更新POI的location格式为列表 [lat, lng]
                            poi['location'] = [poi['location']['lat'], poi['location']['lng']]
                            filtered_pois.append(poi)
                    
                    boundary_pois = filtered_pois
                    print(f"从本地数据中筛选出{len(boundary_pois)}个边界内POI")
                else:
                    # 使用在线地图服务
                    print("使用在线地图服务加载POI")
                    boundary_pois = self.map_service.get_poi_in_polygon(self.exploration_boundary)
                
                self.mental_map['available_pois'] = boundary_pois
                try:
                    for poi in boundary_pois:
                        if poi.get('id') is None:
                            nm = poi.get('name')
                            if isinstance(nm, str) and nm:
                                poi['id'] = nm
                except Exception:
                    pass
                self.all_boundary_pois = boundary_pois
                self.total_pois_targets = len(boundary_pois)
                print(f"成功加载{len(boundary_pois)}个POI到AI视野中")
                
                # 记录POI类型分布
                poi_types = {}
                for poi in boundary_pois:
                    poi_type = poi.get('type', '未知')
                    poi_types[poi_type] = poi_types.get(poi_type, 0) + 1
                
                print(f"POI类型分布：{poi_types}")
            else:
                print("未设置探索边界，将在探索过程中动态发现POI")
                self.mental_map['available_pois'] = []
                
        except Exception as e:
            print(f"加载边界POI时出错：{e}")
            self.mental_map['available_pois'] = []
    
    async def _get_visible_pois(self) -> List[Dict]:
        """获取视野内的POI - 只从边界内已加载的POI中筛选"""
        # 从已加载的边界POI中筛选视野内的POI，确保前端和后端POI数据一致
        available_pois = self.mental_map.get('available_pois', [])
        
        # 调试信息：输出POI数据结构
        if available_pois:
            print(f"🔍 [调试] 可用POI数量: {len(available_pois)}")
            for i, poi in enumerate(available_pois[:3]):  # 只显示前3个POI的结构
                print(f"🔍 [调试] POI[{i}] 结构: {poi}")
                print(f"🔍 [调试] POI[{i}] name字段: {poi.get('name', 'MISSING_NAME')} (类型: {type(poi.get('name'))})")
        
        # 过滤视野内且未访问的POI
        visible_pois = []
        for poi in available_pois:
            # 检查POI数据完整性
            poi_name = poi.get('name')
            if poi_name is None or poi_name == '' or str(poi_name).lower() == 'none':
                print(f"🔍 [警告] 发现无效POI名称: {poi_name}, POI数据: {poi}")
                continue  # 跳过无效POI
                
            if poi['id'] not in self.visited_pois:
                # 计算距离
                distance = self.map_service.calculate_distance(
                    self.current_location, poi['location']
                )
                
                # 只选择视野范围内的POI
                if distance <= self.vision_radius:
                    poi['distance_to_ai'] = distance
                    visible_pois.append(poi)
        
        print(f"🔍 从{len(available_pois)}个边界POI中发现{len(visible_pois)}个视野内POI")
        return visible_pois

    def _has_completed_poi_cycle(self) -> bool:
        try:
            targets = []
            for p in (self.all_boundary_pois or []):
                pid = p.get('id') or p.get('name')
                if pid:
                    targets.append(pid)
            target_set = set(targets)
            return len(target_set) > 0 and target_set.issubset(set(self.visited_pois))
        except Exception:
            return False

    def _build_visible_snapshot(self, visible_pois: List[Dict]) -> List[Dict]:
        """构建当前决策位置的视野快照（名称+相对方向/距离）"""
        snapshot: List[Dict] = []
        try:
            for poi in (visible_pois or []):
                name = poi.get('name')
                loc = poi.get('location')
                if not name or not isinstance(loc, (list, tuple)):
                    continue
                direction = self._calculate_direction(self.current_location, loc)
                distance = self.map_service.calculate_distance(self.current_location, loc)
                snapshot.append({
                    'name': name,
                    'relative_position': {
                        'direction': direction,
                        'distance': distance
                    }
                })
        except Exception:
            pass
        return snapshot
    
    async def _make_decision(self, visible_pois: List[Dict]) -> Dict:
        """AI决策 - 根据探索模式选择不同的决策逻辑"""
        if self.exploration_mode == "随机POI探索":
            return self._random_poi_decision(visible_pois)
        elif self.exploration_mode == "最近距离探索":
            return self._nearest_poi_decision(visible_pois)
        elif self.exploration_mode == "随机选择两个POI进行最短路径探索":
            return self._shortest_path_decision(visible_pois)
        else:
            # 默认使用最近距离探索
            return self._nearest_poi_decision(visible_pois)
    
    def _random_poi_decision(self, visible_pois: List[Dict]) -> Dict:
        """随机POI探索决策"""
        if visible_pois:
            # 随机选择一个POI
            target_poi = random.choice(visible_pois)
            print(f"🎯 随机选择POI：{target_poi['name']} (距离{target_poi['distance_to_ai']:.0f}米)")
            
            return {
                "action": "move_to_poi",
                "target": target_poi['name'],
                "target_location": target_poi['location'],
                "reason": f"随机选择POI：{target_poi['name']}",
                "interest_level": 5,
                "notes": f"随机探索{target_poi['type']}类型的POI，距离{target_poi['distance_to_ai']:.0f}米"
            }
        else:
            return self._random_direction_decision()
    
    def _nearest_poi_decision(self, visible_pois: List[Dict]) -> Dict:
        """最近距离探索决策"""
        if visible_pois:
            # 按距离排序，选择最近的POI
            visible_pois.sort(key=lambda x: x['distance_to_ai'])
            target_poi = visible_pois[0]
            print(f"🎯 选择最近POI：{target_poi['name']} (距离{target_poi['distance_to_ai']:.0f}米)")
            
            return {
                "action": "move_to_poi",
                "target": target_poi['name'],
                "target_location": target_poi['location'],
                "reason": f"前往最近的POI：{target_poi['name']}",
                "interest_level": 7,
                "notes": f"发现{target_poi['type']}类型的POI，距离{target_poi['distance_to_ai']:.0f}米"
            }
        else:
            return self._random_direction_decision()
    
    def _shortest_path_decision(self, visible_pois: List[Dict]) -> Dict:
        """最短路径探索决策 - 在视野内随机选择两个POI作为起点和终点"""
        if len(visible_pois) >= 2:
            # 随机选择两个POI作为起点和终点
            selected_pois = random.sample(visible_pois, 2)
            start_poi = selected_pois[0]
            end_poi = selected_pois[1]
            
            # 准备起点和终点信息
            start_point = {
                "name": start_poi['name'],
                "location": start_poi['location'],
                "coordinates": f"({start_poi['location'][0]:.6f}, {start_poi['location'][1]:.6f})",
                "type": start_poi.get('type', '未知类型')
            }
            end_point = {
                "name": end_poi['name'],
                "location": end_poi['location'],
                "coordinates": f"({end_poi['location'][0]:.6f}, {end_poi['location'][1]:.6f})",
                "type": end_poi.get('type', '未知类型')
            }
            
            print(f"🎯 最短路径探索：从{start_poi['name']}到{end_poi['name']}")
            
            # 设置两阶段移动标记
            self.shortest_path_stage = {
                'current_stage': 'to_start',  # 当前阶段：前往起点
                'start_poi': start_poi,
                'end_poi': end_poi,
                'start_point': start_point,
                'end_point': end_point
            }
            
            # 第一阶段：移动到起点POI
            return {
                "action": "move_to_poi",
                "target": start_poi['name'],
                "target_location": start_poi['location'],
                "reason": f"最短路径探索第一阶段：前往起点{start_poi['name']}",
                "interest_level": 8,
                "notes": f"最短路径探索：先前往起点{start_poi['name']}，然后规划到{end_poi['name']}的路径",
                "start_point": start_point,  # 起点信息
                "end_point": end_point,  # 终点信息
                "exploration_mode": "最短路径探索",  # 探索方式标识
                "shortest_path_stage": "to_start"  # 标记当前阶段
            }
        elif len(visible_pois) == 1:
            # 只有一个POI时直接前往
            return self._nearest_poi_decision(visible_pois)
        else:
            return self._random_direction_decision()
    
    def _random_direction_decision(self) -> Dict:
        """智能方向探索决策 - 沿道路朝最近POI移动"""
        # 首先尝试找到最近的未访问POI
        nearest_unvisited_poi = self._find_nearest_unvisited_poi()
        
        if nearest_unvisited_poi:
            # 计算朝向最近POI的方向
            direction = self._calculate_direction_to_poi(nearest_unvisited_poi)
            reason = f"朝最近未访问POI移动：{nearest_unvisited_poi['name']}"
            print(f"🎯 智能探索：朝最近POI {nearest_unvisited_poi['name']} 方向移动（{direction:.0f}度）")
            
            # 记录方向到历史
            self._add_direction_to_history(direction)
            
            return {
                "action": "explore_direction",
                "target": direction,
                "target_location": None,
                "reason": reason,
                "interest_level": 7,
                "notes": f"沿道路朝最近POI移动，目标：{nearest_unvisited_poi['name']}，距离{nearest_unvisited_poi.get('distance', 0):.0f}米"
            }
        else:
            # 如果没有未访问的POI，使用原有的智能方向选择
            unexplored_directions = self._get_unexplored_directions()
            
            if unexplored_directions:
                # 优先选择未探索的方向
                direction = random.choice(unexplored_directions)
                reason = "选择未探索方向"
                print(f"🔍 智能探索：选择未探索方向{direction}度")
            else:
                # 如果所有方向都探索过，选择最久未使用的方向
                direction = self._get_least_used_direction()
                reason = "选择最久未使用方向"
                print(f"🔍 智能探索：选择最久未使用方向{direction}度")
            
            # 记录方向到历史
            self._add_direction_to_history(direction)
            
            return {
                "action": "explore_direction",
                "target": direction,
                "target_location": None,
                "reason": f"视野内无POI，{reason}",
                "interest_level": 3,
                "notes": "智能探索未知区域，避免徘徊"
            }
    
    def _get_least_used_direction(self) -> float:
        """获取最久未使用的方向"""
        all_directions = [0, 45, 90, 135, 180, 225, 270, 315]
        
        if not self.direction_history:
            return random.choice(all_directions)
        
        # 计算每个方向的最后使用时间（索引越大越近期）
        direction_scores = {}
        for direction in all_directions:
            last_used_index = -1
            for i, hist_dir in enumerate(self.direction_history):
                if abs(direction - hist_dir) < 30:  # 30度范围内认为是相同方向
                    last_used_index = i
            direction_scores[direction] = last_used_index
        
        # 选择最久未使用的方向（索引最小的）
        least_used_direction = min(direction_scores.keys(), key=lambda x: direction_scores[x])
        return least_used_direction
    
    def _default_decision(self, visible_pois: List[Dict]) -> Dict:
        """默认决策逻辑"""
        if visible_pois:
            # 选择最近的POI
            target_poi = min(visible_pois, key=lambda x: x['distance_to_ai'])
            return {
                "action": "move_to_poi",
                "target": target_poi['name'],
                "target_location": target_poi['location'],
                "reason": f"前往最近的POI：{target_poi['name']}",
                "interest_level": 5,
                "notes": f"发现{target_poi['type']}类型的POI"
            }
        else:
            # 使用智能方向选择
            return self._random_direction_decision()
    
    async def _execute_decision(self, decision: Dict):
        """执行决策"""
        action = decision.get('action')
        
        if action == 'move_to_poi':
            target_location = decision.get('target_location')
            # 捕获当前决策位置的视野快照，供路径单元使用
            try:
                if not decision.get('visible_pois_snapshot'):
                    visible_pois = await self._get_visible_pois()
                    decision['visible_pois_snapshot'] = self._build_visible_snapshot(visible_pois)
            except Exception:
                decision['visible_pois_snapshot'] = []
            if target_location:
                await self._move_to_location(target_location, decision)
            else:
                # 如果没有target_location，尝试根据target名称查找POI位置
                target_name = decision.get('target')
                if target_name:
                    visible_pois = await self._get_visible_pois()
                    poi_found = False
                    for poi in visible_pois:
                        if poi['name'] == target_name:
                            decision['target_location'] = poi['location']
                            await self._move_to_location(poi['location'], decision)
                            poi_found = True
                            break
                    
                    # 如果没有找到目标POI，改为随机探索
                    if not poi_found:
                        print(f"未找到目标POI：{target_name}，改为随机探索")
                        direction = random.randint(0, 360)
                        await self._move_in_direction(direction, decision)
                else:
                    print("move_to_poi动作缺少target参数，改为随机探索")
                    direction = random.randint(0, 360)
                    await self._move_in_direction(direction, decision)
        elif action == 'explore_direction':
            direction = decision.get('target', 0)
            await self._move_in_direction(direction, decision)
        else:
            print(f"未知的动作类型：{action}，改为随机探索")
            direction = random.randint(0, 360)
            await self._move_in_direction(direction, decision)
        
        # 记录决策到原有路径（兼容性）
        self.exploration_path.append({
            'location': self.current_location.copy(),
            'timestamp': datetime.now(),
            'action': action,
            'decision': decision,
            'notes': decision.get('notes', '')
        })
        
        # 记录到路径记忆系统 - 使用详细版本
        path_data = {
            'start_location': self.current_location.copy(),
            'end_location': self.current_location.copy(),
            'nodes': [f"决策位置_{self.current_location[0]:.6f}_{self.current_location[1]:.6f}"],
            'segments': [{
                'name': f'决策动作_{action}',
                'length': 0,
                'road_type': '决策节点',
                'coordinates': [self.current_location.copy()]
            }],
            'poi_waypoints': [],
            'total_distance': 0,
            'start_poi': None,
            'end_poi': None
        }
        self.path_memory.record_exploration_path_detailed(path_data)
    
    async def _move_to_location(self, target_location: Tuple[float, float], 
                               decision: Dict):
        """移动到指定位置 - 支持道路约束"""
        if not target_location or len(target_location) != 2:
            print(f"无效的目标位置：{target_location}")
            # 如果目标位置无效，改为随机探索
            direction = random.randint(0, 360)
            await self._move_in_direction(direction, decision)
            return
            
        try:
            target_name = decision.get('target', '未知POI')
            print(f"🎯 AI决定前往：{target_name}")
            
            # 如果使用本地数据模式，使用道路网络路径规划
            if self.use_local_data and self.local_data_service:
                print(f"🚗 [移动决策] 使用道路网络模式移动到{target_name}")
                await self._move_along_road(target_location, decision)
            else:
                print(f"✈️ [移动决策] 使用直线模式移动到{target_name}")
                # 传统直线移动
                await self._move_direct(target_location, decision)
                
        except Exception as e:
            print(f"移动到位置时出错：{e}")
            print(f"当前位置：{self.current_location}，目标位置：{target_location}")
    
    async def _move_along_road(self, target_location: Tuple[float, float], decision: Dict):
        """沿道路移动到目标位置"""
        target_name = decision.get('target', '未知POI')
        
        try:
            print(f"🚗 [道路模式] 开始计算到{target_name}的道路路径")
            print(f"🚗 [道路模式] 起点: {self.current_location}")
            print(f"🚗 [道路模式] 终点: {target_location}")
            print(f"🚗 [道路模式] 使用本地数据: {self.use_local_data}")
            print(f"🚗 [道路模式] 本地数据服务: {self.local_data_service is not None}")
            
            # 获取路径（优先使用决策中保存的路径）
            path = decision.get('full_path')
            if not path:
                # 如果决策中没有路径，重新计算
                path = self.local_data_service.find_shortest_path(
                    (self.current_location[1], self.current_location[0]),  # 经度, 纬度
                    (target_location[1], target_location[0])
                )
            
            if not path or len(path) < 2:
                print(f"🚗 [道路模式] ❌ 无法找到到{target_name}的道路路径，使用直线移动")
                await self._move_direct(target_location, decision)
                return
            
            print(f"🚗 [道路模式] ✅ 找到道路路径，共{len(path)}个路径点")
            print(f"🚗 [道路模式] 路径预览: {path[:3]}...{path[-3:] if len(path) > 6 else path[3:]}")
            

            
            # 沿路径移动
            for i in range(1, len(path)):
                if not self.is_exploring:
                    break
                
                waypoint = path[i]
                waypoint_location = [waypoint[1], waypoint[0]]  # 纬度, 经度
                
                # 移动到路径点
                await self._move_to_waypoint(waypoint_location, target_name, i, len(path))
                
                # 确保位置在道路上
                self._ensure_on_road()
            
            # 到达目标后访问POI
            distance_to_target = self.map_service.calculate_distance(
                self.current_location, target_location
            )
            
            if distance_to_target < 50:  # 50米内认为到达
                self._current_action = f"已到达{target_name}，正在访问"
                print(f"✅ 已到达：{target_name}")
                
                await self._visit_poi(decision)
                self._current_action = f"完成访问{target_name}"
            
        except Exception as e:
            print(f"沿道路移动失败：{e}，改用直线移动")
            await self._move_direct(target_location, decision)
    
    async def _move_to_waypoint(self, waypoint_location: List[float], target_name: str, 
                               current_step: int, total_steps: int):
        """移动到路径中的一个路径点 - 严格沿道路移动"""
        # 计算移动距离
        total_distance = self.map_service.calculate_distance(
            self.current_location, waypoint_location
        )
        
        # 汇报开始移动
        progress = f"沿道路前往{target_name} ({current_step}/{total_steps})"
        self._current_action = progress
        print(f"🚶 {progress} - 距离: {total_distance:.0f}米")
        
        # 如果距离很近，直接到达
        if total_distance < 10:
            self.current_location = waypoint_location.copy()
            return
        
        # 使用更少的步数，每步距离更大，避免过多的直线插值
        step_distance = min(50, total_distance / 3)  # 每步最多50米，总共3步
        steps = max(1, int(total_distance / step_distance))
        
        # 分步移动到路径点
        for i in range(steps):
            if not self.is_exploring:
                break
            
            # 计算当前步的进度比例
            progress_ratio = (i + 1) / steps
            
            # 根据进度比例计算中间位置
            intermediate_lat = self.current_location[0] + (waypoint_location[0] - self.current_location[0]) * progress_ratio
            intermediate_lng = self.current_location[1] + (waypoint_location[1] - self.current_location[1]) * progress_ratio
            
            # 更新位置
            self.current_location = [intermediate_lat, intermediate_lng]
            
            # 如果使用本地数据，确保位置投影到道路上
            if self.use_local_data and self.local_data_service:
                projected_point = self.local_data_service.project_point_to_road(
                    (self.current_location[1], self.current_location[0])  # (经度, 纬度)
                )
                if projected_point:
                    self.current_location = [projected_point[1], projected_point[0]]  # 纬度, 经度
            
            # 汇报进度
            remaining_distance = self.map_service.calculate_distance(
                self.current_location, waypoint_location
            )
            if i % 2 == 0 or remaining_distance < 20:
                print(f"🚶 移动中... 剩余: {remaining_distance:.0f}米")
            
            await asyncio.sleep(0.6)  # 稍快的移动速度
        
        # 最终精确到达路径点
        old_location = self.current_location.copy()
        self.current_location = waypoint_location.copy()
        
        # 记录移动到路径记忆系统 - 使用详细版本
        path_data = {
            'start_location': old_location,
            'end_location': waypoint_location.copy(),
            'nodes': [f"起始_{old_location[0]:.6f}_{old_location[1]:.6f}", 
                     f"路径点_{waypoint_location[0]:.6f}_{waypoint_location[1]:.6f}"],
            'segments': [{
                'name': '移动到路径点',
                'length': self._calculate_distance(old_location, waypoint_location),
                'road_type': '路径移动',
                'coordinates': [old_location, waypoint_location]
            }],
            'poi_waypoints': [],
            'total_distance': self._calculate_distance(old_location, waypoint_location),
            'start_poi': None,
            'end_poi': None
        }
        self.path_memory.record_exploration_path_detailed(path_data)
        
        print(f"✅ 到达路径点: {waypoint_location}")
    
    async def _move_direct(self, target_location: Tuple[float, float], decision: Dict):
        """直线移动到目标位置（传统方式）"""
        target_name = decision.get('target', '未知POI')
        
        # 计算移动距离
        total_distance = self.map_service.calculate_distance(
            self.current_location, target_location
        )
        print(f"📍 目标距离：{total_distance:.0f}米")
        
        # 每次移动的距离（更小的步长，更真实的移动）
        step_distance = 20  # 每步20米
        steps = max(1, int(total_distance / step_distance))
        
        # 分步移动
        lat_step = (target_location[0] - self.current_location[0]) / steps
        lng_step = (target_location[1] - self.current_location[1]) / steps
        
        for i in range(steps):
            if not self.is_exploring:
                break
                
            self.current_location[0] += lat_step
            self.current_location[1] += lng_step
            
            # 计算剩余距离
            remaining_distance = self.map_service.calculate_distance(
                self.current_location, target_location
            )
            
            # 每隔几步汇报进度
            if i % 5 == 0 or remaining_distance < 30:
                self._current_action = f"前往{target_name}，剩余{remaining_distance:.0f}米"
                print(f"🚶 正在前往{target_name}，剩余距离：{remaining_distance:.0f}米")
            
            # 检查是否到达目标
            if i == steps - 1 or remaining_distance < 10:
                self.current_location = list(target_location)
                self._current_action = f"已到达{target_name}，正在访问"
                print(f"✅ 已到达：{target_name}")
                # 标记POI为已访问
                await self._visit_poi(decision)
                self._current_action = f"完成访问{target_name}"
                break
            
            await asyncio.sleep(1)  # 每步等待1秒，更真实的移动速度
    
    async def _move_in_direction(self, direction: float, decision: Dict):
        """朝指定方向移动 - 支持道路约束"""
        if self.use_local_data and self.local_data_service:
            await self._move_in_direction_on_road(direction, decision)
        else:
            await self._move_in_direction_direct(direction, decision)
    
    async def _move_in_direction_on_road(self, direction: float, decision: Dict):
        """智能道路移动 - 避免徘徊"""
        try:
            # 使用更大的移动距离，避免小步移动
            move_distance = max(self.min_move_distance, self.move_speed * self.move_interval)
            
            # 转换角度为弧度
            direction_rad = math.radians(direction)
            
            # 计算目标位置
            lat_offset = move_distance * math.cos(direction_rad) / 111000
            lng_offset = move_distance * math.sin(direction_rad) / (111000 * math.cos(math.radians(self.current_location[0])))
            
            target_location = [
                self.current_location[0] + lat_offset,
                self.current_location[1] + lng_offset
            ]
            
            # 检查目标位置是否合适
            if not self._is_within_boundary(target_location) or self._is_area_recently_visited(target_location):
                # 寻找更好的替代方向
                alternative_direction = self._find_best_alternative_direction(direction)
                if alternative_direction != direction:
                    print(f"🔄 道路方向调整：从{direction:.0f}度改为{alternative_direction:.0f}度")
                    await self._move_in_direction_on_road(alternative_direction, decision)
                    return
                else:
                    # 如果找不到好方向，回退到直线移动
                    print(f"🚶 道路移动受限，切换到直线移动")
                    await self._move_in_direction_direct(direction, decision)
                    return
            
            # 尝试找到到目标位置的道路路径
            path = self.local_data_service.find_shortest_path(
                (self.current_location[1], self.current_location[0]),  # 经度, 纬度
                (target_location[1], target_location[0])
            )
            
            if path and len(path) > 1:
                # 记录当前位置到历史
                self._add_position_to_history(tuple(self.current_location))
                
                # 沿道路移动到下一个路径点
                next_point = path[1]
                next_location = [next_point[1], next_point[0]]  # 纬度, 经度
                
                # 分步移动到下一个路径点
                steps = 3  # 分3步移动
                lat_step = (next_location[0] - self.current_location[0]) / steps
                lng_step = (next_location[1] - self.current_location[1]) / steps
                
                for i in range(steps):
                    if not self.is_exploring:
                        break
                    
                    self.current_location[0] += lat_step
                    self.current_location[1] += lng_step
                    
                    self._current_action = f"🛣️ 沿道路朝{direction:.0f}度方向探索 ({move_distance:.0f}米)"
                    await asyncio.sleep(0.5)
                
                # 确保位置在道路上
                old_location = self.current_location.copy()
                self._ensure_on_road()
                
                # 记录道路移动到路径记忆系统 - 使用详细版本
                path_data = {
                    'start_location': old_location,
                    'end_location': self.current_location.copy(),
                    'nodes': [f"道路起点_{old_location[0]:.6f}_{old_location[1]:.6f}", 
                             f"道路终点_{self.current_location[0]:.6f}_{self.current_location[1]:.6f}"],
                    'segments': [{
                        'name': f'道路移动_{direction:.0f}度',
                        'length': move_distance,
                        'road_type': '道路行驶',
                        'coordinates': [old_location, self.current_location.copy()],
                        'direction': direction,
                        'move_distance': move_distance
                    }],
                    'poi_waypoints': [],
                    'total_distance': move_distance,
                    'start_poi': None,
                    'end_poi': None
                }
                self.path_memory.record_exploration_path_detailed(path_data)
                
                print(f"🛣️ 道路移动完成：朝{direction:.0f}度方向移动{move_distance:.0f}米")
            else:
                # 如果找不到道路路径，投影到最近的道路
                projected_point = self.local_data_service.project_point_to_road(
                    (target_location[1], target_location[0])  # (经度, 纬度)
                )
                
                if projected_point:
                    # 记录当前位置到历史
                    self._add_position_to_history(tuple(self.current_location))
                    self.current_location = [projected_point[1], projected_point[0]]  # 纬度, 经度
                    print(f"🛣️ 投影到最近道路: {self.current_location}")
                else:
                    # 如果投影失败，尝试直线移动
                    print(f"⚠️ 无法找到附近道路，切换到直线移动")
                    await self._move_in_direction_direct(direction, decision)
                    
        except Exception as e:
            print(f"道路移动失败：{e}，使用直线移动")
            await self._move_in_direction_direct(direction, decision)
    
    async def _move_in_direction_direct(self, direction: float, decision: Dict):
        """智能直线方向移动 - 避免徘徊"""
        # 使用更大的移动距离，避免小步移动
        move_distance = max(self.min_move_distance, self.move_speed * self.move_interval)
        
        # 转换角度为弧度
        direction_rad = math.radians(direction)
        
        # 计算新位置（简化计算）
        lat_offset = move_distance * math.cos(direction_rad) / 111000  # 约111km/度
        lng_offset = move_distance * math.sin(direction_rad) / (111000 * math.cos(math.radians(self.current_location[0])))
        
        new_location = [
            self.current_location[0] + lat_offset,
            self.current_location[1] + lng_offset
        ]
        
        # 检查新位置是否合适
        if self._is_within_boundary(new_location) and not self._is_area_recently_visited(new_location):
            # 记录当前位置到历史
            self._add_position_to_history(tuple(self.current_location))
            
            # 记录移动前位置
            old_location = self.current_location.copy()
            
            # 移动到新位置
            self.current_location = new_location
            
            # 记录直线移动到路径记忆系统 - 使用详细版本
            path_data = {
                'start_location': old_location,
                'end_location': new_location.copy(),
                'nodes': [f"直线起点_{old_location[0]:.6f}_{old_location[1]:.6f}", 
                         f"直线终点_{new_location[0]:.6f}_{new_location[1]:.6f}"],
                'segments': [{
                    'name': f'直线移动_{direction:.0f}度',
                    'length': move_distance,
                    'road_type': '直线行走',
                    'coordinates': [old_location, new_location.copy()],
                    'direction': direction,
                    'move_distance': move_distance
                }],
                'poi_waypoints': [],
                'total_distance': move_distance,
                'start_poi': None,
                'end_poi': None
            }
            self.path_memory.record_exploration_path_detailed(path_data)
            
            print(f"🚶 智能移动：朝{direction:.0f}度方向移动{move_distance:.0f}米")
            
            # 添加移动间隔
            await asyncio.sleep(0.5)
        else:
            # 如果新位置不合适，选择更好的替代方向
            alternative_direction = self._find_best_alternative_direction(direction)
            if alternative_direction != direction:
                print(f"🔄 方向调整：从{direction:.0f}度改为{alternative_direction:.0f}度")
                await self._move_in_direction_direct(alternative_direction, decision)
            else:
                # 如果找不到好的替代方向，进行小幅移动
                print(f"⚠️ 无法找到合适方向，进行小幅移动")
                small_move_distance = move_distance * 0.3
                small_lat_offset = small_move_distance * math.cos(direction_rad) / 111000
                small_lng_offset = small_move_distance * math.sin(direction_rad) / (111000 * math.cos(math.radians(self.current_location[0])))
                
                small_new_location = [
                    self.current_location[0] + small_lat_offset,
                    self.current_location[1] + small_lng_offset
                ]
                
                if self._is_within_boundary(small_new_location):
                    self._add_position_to_history(tuple(self.current_location))
                    self.current_location = small_new_location
                    await asyncio.sleep(0.5)
    
    def _find_best_alternative_direction(self, original_direction: float) -> float:
        """寻找最佳替代方向 - 优先考虑边界反弹"""
        # 检查是否接近边界
        if self._is_near_boundary():
            # 如果接近边界，计算远离边界的方向
            boundary_escape_direction = self._calculate_boundary_escape_direction()
            if boundary_escape_direction is not None:
                print(f"🔄 接近边界，调整方向为{boundary_escape_direction:.0f}度")
                return boundary_escape_direction
        
        # 获取未探索的方向
        unexplored_directions = self._get_unexplored_directions()
        
        if unexplored_directions:
            # 从未探索方向中选择与原方向最接近的
            best_direction = min(unexplored_directions, 
                               key=lambda d: min(abs(d - original_direction), 360 - abs(d - original_direction)))
            return best_direction
        
        # 如果没有未探索方向，尝试相对方向
        alternative_directions = [
            (original_direction + 90) % 360,   # 右转90度
            (original_direction - 90) % 360,   # 左转90度
            (original_direction + 45) % 360,   # 右转45度
            (original_direction - 45) % 360,   # 左转45度
        ]
        
        for alt_dir in alternative_directions:
            test_location = self._calculate_target_location(self.current_location, alt_dir, self.min_move_distance)
            if self._is_within_boundary(test_location) and not self._is_area_recently_visited(test_location):
                return alt_dir
        
        return original_direction  # 如果都不行，返回原方向
    
    def _is_near_boundary(self, threshold_distance: float = 100) -> bool:
        """检查是否接近边界"""
        if not self.exploration_boundary:
            return False
            
        # 计算当前位置到边界的最短距离
        min_distance_to_boundary = float('inf')
        
        for i in range(len(self.exploration_boundary)):
            p1 = self.exploration_boundary[i]
            p2 = self.exploration_boundary[(i + 1) % len(self.exploration_boundary)]
            
            # 计算点到线段的距离
            distance = self._point_to_line_distance(self.current_location, p1, p2)
            min_distance_to_boundary = min(min_distance_to_boundary, distance)
        
        return min_distance_to_boundary < threshold_distance
    
    def _calculate_boundary_escape_direction(self) -> Optional[float]:
        """计算远离边界的方向"""
        if not self.exploration_boundary:
            return None
    
    def _answer_path_question(self, question: str) -> str:
        """回答路径规划相关问题"""
        try:
            # 简化的路径问题回答，不依赖路径记忆
            poi_names = [poi_info['poi']['name'] for poi_info in self.interesting_pois]
            mentioned_pois = []
            for poi_name in poi_names:
                if poi_name in question:
                    mentioned_pois.append(poi_name)
            
            if len(mentioned_pois) >= 2:
                # 询问两个特定POI之间的路径
                start_poi = mentioned_pois[0]
                end_poi = mentioned_pois[1]
                return f"我可以看到{start_poi}和{end_poi}，但需要实际探索才能了解它们之间的具体路径。"
            
            elif len(mentioned_pois) == 1:
                # 询问与特定POI相关的路径
                poi_name = mentioned_pois[0]
                return f"关于{poi_name}，我需要通过实际探索来了解与它相关的路径信息。"
            
            else:
                # 一般性路径问题
                return "我正在通过探索来了解这个区域的路径信息。随着探索的深入，我会对路径有更好的理解。"
                
        except Exception as e:
            return f"回答路径问题时出错：{e}"
            
        # 计算边界中心点
        center_lat = sum(p[0] for p in self.exploration_boundary) / len(self.exploration_boundary)
        center_lng = sum(p[1] for p in self.exploration_boundary) / len(self.exploration_boundary)
        
        # 计算朝向中心的方向
        lat_diff = center_lat - self.current_location[0]
        lng_diff = center_lng - self.current_location[1]
        
        angle_rad = math.atan2(lng_diff, lat_diff)
        angle_deg = math.degrees(angle_rad)
        if angle_deg < 0:
            angle_deg += 360
            
        return angle_deg
    
    def _point_to_line_distance(self, point: Tuple[float, float], line_start: Tuple[float, float], line_end: Tuple[float, float]) -> float:
        """计算点到线段的距离（简化版本）"""
        # 简化计算：使用点到直线的距离公式
        x0, y0 = point[1], point[0]  # 经度, 纬度
        x1, y1 = line_start[1], line_start[0]
        x2, y2 = line_end[1], line_end[0]
        
        # 如果线段长度为0，返回点到点的距离
        if x1 == x2 and y1 == y2:
            return math.sqrt((x0 - x1)**2 + (y0 - y1)**2) * 111000  # 转换为米
        
        # 计算点到直线的距离
        A = y2 - y1
        B = x1 - x2
        C = x2 * y1 - x1 * y2
        
        distance = abs(A * x0 + B * y0 + C) / math.sqrt(A**2 + B**2)
        return distance * 111000  # 转换为米
    
    async def _visit_poi(self, decision: Dict):
        """访问POI"""
        target_name = decision.get('target')
        if not target_name:
            print("访问POI时缺少target参数")
            return
            
        try:
            # 从边界内的POI中查找目标POI
            boundary_pois = self.mental_map.get('available_pois', [])
            target_poi = None
            
            for poi in boundary_pois:
                if poi.get('name') == target_name:
                    target_poi = poi
                    break
            
            if not target_poi:
                print(f"在边界POI中未找到目标POI：{target_name}")
                return
            
            # 检查是否已访问过
            if target_poi.get('id') in self.visited_pois:
                print(f"POI {target_name} 已经访问过了")
                return
            
            # 检查距离是否足够近（50米内）
            distance = self.map_service.calculate_distance(
                self.current_location, target_poi['location']
            )
            
            if distance > 50:
                print(f"距离目标POI {target_name} 还有 {distance:.1f} 米，需要继续移动")
                return
            
            # 访问POI
            self.visited_pois.add(target_poi['id'])
            
            # 添加到感兴趣的POI列表
            poi_info = {
                'poi': target_poi,
                'visit_time': datetime.now(),
                'interest_level': decision.get('interest_level', 5),
                'notes': decision.get('notes', ''),
                'location_when_visited': self.current_location.copy()
            }
            self.interesting_pois.append(poi_info)
            
            # 更新心理地图
            self._update_mental_map(poi_info)
            
            # 记录POI访问到路径记忆系统
            self.path_memory.record_poi_visit(target_poi, {
                'visit_time': datetime.now().isoformat(),
                'interest_level': decision.get('interest_level', 5),
                'notes': decision.get('notes', ''),
                'location_when_visited': self.current_location.copy(),
                'approach_path': {
                    'start_location': self.current_location.copy(),
                    'end_location': target_poi['location'],
                    'distance': distance
                },
                'visible_snapshot': decision.get('visible_pois_snapshot', [])
            })
            
            print(f"成功访问POI：{target_name}，距离：{distance:.1f}米")
            
            # 检查是否是最短路径探索的两阶段移动
            if (self.shortest_path_stage and 
                self.shortest_path_stage.get('current_stage') == 'to_start' and
                target_name == self.shortest_path_stage.get('start_poi', {}).get('name')):
                
                print(f"🎯 已到达起点POI：{target_name}，开始第二阶段：前往终点")
                
                # 切换到第二阶段：前往终点
                self.shortest_path_stage['current_stage'] = 'to_end'
                end_poi = self.shortest_path_stage['end_poi']
                
                # 创建第二阶段的决策
                second_stage_decision = {
                    "action": "move_to_poi",
                    "target": end_poi['name'],
                    "target_location": end_poi['location'],
                    "reason": f"最短路径探索第二阶段：从起点{target_name}前往终点{end_poi['name']}",
                    "interest_level": 9,
                    "notes": f"最短路径探索：从{target_name}到{end_poi['name']}的第二阶段移动",
                    "start_point": self.shortest_path_stage['start_point'],
                    "end_point": self.shortest_path_stage['end_point'],
                    "exploration_mode": "最短路径探索",
                    "shortest_path_stage": "to_end"
                }
                
                # 如果使用本地数据，计算从起点到终点的路径
                if self.use_local_data and self.local_data_service:
                    try:
                        path = self.local_data_service.find_shortest_path(
                            (self.current_location[1], self.current_location[0]),  # 经度, 纬度
                            (end_poi['location'][1], end_poi['location'][0])
                        )
                        if path and len(path) > 1:
                            second_stage_decision['full_path'] = path
                            print(f"🛣️ 规划从{target_name}到{end_poi['name']}的道路路径")
                    except Exception as e:
                        print(f"第二阶段路径规划失败：{e}")
                
                # 立即执行第二阶段移动
                print(f"🚀 开始第二阶段移动：前往{end_poi['name']}")
                await self._execute_decision(second_stage_decision)
                
            elif (self.shortest_path_stage and 
                  self.shortest_path_stage.get('current_stage') == 'to_end' and
                  target_name == self.shortest_path_stage.get('end_poi', {}).get('name')):
                
                print(f"🎉 最短路径探索完成！已到达终点POI：{target_name}")
                # 清除两阶段移动状态
                self.shortest_path_stage = None
                    
        except Exception as e:
            print(f"访问POI时出错：{e}")
            print(f"目标POI：{target_name}，当前位置：{self.current_location}")
    
    def _update_mental_map(self, poi_info: Dict):
        """更新心理地图 - 增强空间记忆能力"""
        poi = poi_info['poi']
        poi_id = poi['id']
        
        # 记录POI关系
        if poi_id not in self.mental_map['poi_relationships']:
            self.mental_map['poi_relationships'][poi_id] = {
                'poi_info': poi,
                'visit_info': poi_info,
                'nearby_pois': [],
                'relative_positions': {},
                'absolute_coordinates': poi['location'],  # 记录绝对坐标
                'poi_type': poi.get('type', '未知'),  # 记录POI类型
                'visit_time': datetime.now().isoformat()  # 记录访问时间
            }
        
        # 计算与其他POI的相对位置和方向
        for other_poi_info in self.interesting_pois[:-1]:  # 排除当前POI
            other_poi = other_poi_info['poi']
            other_poi_id = other_poi['id']
            
            # 计算距离
            distance = self.map_service.calculate_distance(
                poi['location'], other_poi['location']
            )
            
            # 计算方向
            direction = self._calculate_direction(poi['location'], other_poi['location'])
            
            # 记录相对位置关系
            self.mental_map['poi_relationships'][poi_id]['relative_positions'][other_poi_id] = {
                'distance': distance,
                'direction': direction,
                'poi_name': other_poi['name'],
                'poi_type': other_poi.get('type', '未知')
            }
            
            # 如果距离在1公里内，记录为附近POI
            if distance < 1000:
                self.mental_map['poi_relationships'][poi_id]['nearby_pois'].append({
                    'poi_id': other_poi_id,
                    'poi_name': other_poi['name'],
                    'distance': distance,
                    'direction': direction,
                    'poi_type': other_poi.get('type', '未知')
                })
        
        # 更新POI类型统计
        poi_type = poi.get('type', '未知')
        if 'poi_type_stats' not in self.mental_map:
            self.mental_map['poi_type_stats'] = {}
        
        if poi_type not in self.mental_map['poi_type_stats']:
            self.mental_map['poi_type_stats'][poi_type] = 0
        self.mental_map['poi_type_stats'][poi_type] += 1
        
        # 更新区域密度统计
        self._update_region_density(poi['location'])
    
    def _update_region_density(self, location: Tuple[float, float]):
        """更新区域密度统计"""
        lat, lng = location
        
        # 将区域划分为4个象限：东北、东南、西南、西北
        if 'region_density' not in self.mental_map:
            self.mental_map['region_density'] = {
                '东北': 0, '东南': 0, '西南': 0, '西北': 0
            }
        
        # 计算区域中心点
        if hasattr(self, 'exploration_boundary') and self.exploration_boundary:
            # 计算边界的中心点
            center_lat = sum(point[0] for point in self.exploration_boundary) / len(self.exploration_boundary)
            center_lng = sum(point[1] for point in self.exploration_boundary) / len(self.exploration_boundary)
        else:
            # 使用当前位置作为参考点
            center_lat, center_lng = self.current_location
        
        # 判断POI在哪个象限
        if lat >= center_lat and lng >= center_lng:
            region = '东北'
        elif lat < center_lat and lng >= center_lng:
            region = '东南'
        elif lat < center_lat and lng < center_lng:
            region = '西南'
        else:
            region = '西北'
        
        self.mental_map['region_density'][region] += 1
    
    def _is_within_boundary(self, location: Tuple[float, float]) -> bool:
        """检查位置是否在边界内"""
        if not self.exploration_boundary:
            return True
        
        # 简化的点在多边形内判断
        x, y = location[1], location[0]  # 经度, 纬度
        n = len(self.exploration_boundary)
        inside = False
        
        p1x, p1y = self.exploration_boundary[0][1], self.exploration_boundary[0][0]
        for i in range(1, n + 1):
            p2x, p2y = self.exploration_boundary[i % n][1], self.exploration_boundary[i % n][0]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def _add_position_to_history(self, location: Tuple[float, float]):
        """添加位置到历史记录"""
        self.position_history.append(location)
        if len(self.position_history) > self.max_history_size:
            self.position_history.pop(0)
    
    def _is_area_recently_visited(self, location: Tuple[float, float]) -> bool:
        """检查某个区域是否最近被访问过"""
        for hist_location in self.position_history:
            distance = self.map_service.calculate_distance(location, hist_location)
            if distance < self.avoid_radius:
                return True
        return False
    
    def _add_direction_to_history(self, direction: float):
        """添加方向到历史记录"""
        self.direction_history.append(direction)
        if len(self.direction_history) > self.max_direction_history:
            self.direction_history.pop(0)
    
    def _get_unexplored_directions(self) -> List[float]:
        """获取未探索的方向列表"""
        all_directions = [0, 45, 90, 135, 180, 225, 270, 315]  # 8个主要方向
        unexplored = []
        
        for direction in all_directions:
            # 检查这个方向是否最近被使用过
            recently_used = False
            for hist_dir in self.direction_history:
                if abs(direction - hist_dir) < 30:  # 30度范围内认为是相同方向
                    recently_used = True
                    break
            
            if not recently_used:
                # 检查这个方向是否会导致访问已访问过的区域
                test_location = self._calculate_target_location(self.current_location, direction, self.min_move_distance * 2)
                if not self._is_area_recently_visited(test_location):
                    unexplored.append(direction)
        
        return unexplored if unexplored else all_directions  # 如果所有方向都被访问过，返回所有方向
    
    def _find_nearest_unvisited_poi(self) -> Optional[Dict]:
        """找到最近的未访问POI"""
        if not hasattr(self, 'boundary_pois') or not self.boundary_pois:
            return None
            
        nearest_poi = None
        min_distance = float('inf')
        
        for poi in self.boundary_pois:
            # 检查是否已访问
            if poi['id'] not in self.visited_pois:
                # 计算距离
                distance = self.map_service.calculate_distance(
                    self.current_location, poi['location']
                )
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_poi = poi.copy()
                    nearest_poi['distance'] = distance
        
        return nearest_poi
    
    def _calculate_direction_to_poi(self, poi: Dict) -> float:
        """计算朝向POI的方向角度"""
        current_lat, current_lng = self.current_location
        target_lat, target_lng = poi['location']
        
        # 计算方向角度
        lat_diff = target_lat - current_lat
        lng_diff = target_lng - current_lng
        
        # 使用atan2计算角度（弧度）
        angle_rad = math.atan2(lng_diff, lat_diff)
        
        # 转换为度数，并调整为0-360度范围
        angle_deg = math.degrees(angle_rad)
        if angle_deg < 0:
            angle_deg += 360
            
        return angle_deg
    
    def _calculate_target_location(self, start_location: Tuple[float, float], direction: float, distance: float) -> Tuple[float, float]:
        """根据起始位置、方向和距离计算目标位置"""
        import math
        
        lat, lng = start_location
        # 将方向转换为弧度
        direction_rad = math.radians(direction)
        
        # 地球半径（米）
        earth_radius = 6371000
        
        # 计算新的纬度和经度
        lat_rad = math.radians(lat)
        lng_rad = math.radians(lng)
        
        new_lat_rad = math.asin(math.sin(lat_rad) * math.cos(distance / earth_radius) +
                               math.cos(lat_rad) * math.sin(distance / earth_radius) * math.cos(direction_rad))
        
        new_lng_rad = lng_rad + math.atan2(math.sin(direction_rad) * math.sin(distance / earth_radius) * math.cos(lat_rad),
                                          math.cos(distance / earth_radius) - math.sin(lat_rad) * math.sin(new_lat_rad))
        
        return (math.degrees(new_lat_rad), math.degrees(new_lng_rad))
    
    def _generate_exploration_report(self) -> Dict:
        """生成探索报告"""
        try:
            # 安全地获取各种数据，提供默认值
            exploration_path = getattr(self, 'exploration_path', [])
            visited_pois = getattr(self, 'visited_pois', set())
            interesting_pois = getattr(self, 'interesting_pois', [])
            mental_map = getattr(self, 'mental_map', {})
            move_interval = getattr(self, 'move_interval', 1.0)
            
            # 计算总距离/时间：优先使用路径记忆统计，回退到原始路径
            total_distance = 0.0
            exploration_time = 0.0
            try:
                stats = None
                if hasattr(self, 'path_memory') and self.path_memory:
                    stats = self.path_memory.get_exploration_stats()
                if isinstance(stats, dict):
                    td = float(stats.get('total_distance_meters', 0) or 0)
                    tt = float(stats.get('total_time_seconds', 0) or 0)
                    if td > 0 or tt > 0:
                        total_distance = td
                        exploration_time = tt
                if total_distance == 0.0 and exploration_time == 0.0:
                    try:
                        total_distance = self._calculate_total_distance()
                    except Exception as e:
                        print(f"计算总距离时出错: {e}")
                        total_distance = 0.0
                    try:
                        exploration_time = len(exploration_path) * move_interval
                    except Exception as e:
                        print(f"计算探索时间时出错: {e}")
                        exploration_time = 0.0
            except Exception:
                pass
            
            # 安全地计算POI数量
            try:
                poi_count = len(interesting_pois) if interesting_pois else 0
            except Exception as e:
                print(f"计算POI数量时出错: {e}")
                poi_count = 0
            
            report = {
                'exploration_path': exploration_path,
                'visited_pois': list(visited_pois) if visited_pois else [],
                'interesting_pois': interesting_pois if interesting_pois else [],
                'mental_map': mental_map if mental_map else {},
                'total_distance': total_distance,
                'exploration_time': exploration_time,
                'poi_count': poi_count,
                'round_index': int(getattr(self, 'exploration_round', 1)),
                'rounds_completed': int(getattr(self, 'rounds_completed', 0))
            }
            
            print(f"生成探索报告成功: 路径点数={len(exploration_path)}, 访问POI数={len(visited_pois)}, 感兴趣POI数={poi_count}")
            return report
            
        except Exception as e:
            print(f"生成探索报告时发生错误: {e}")
            import traceback
            traceback.print_exc()
            
            # 返回最基本的报告
            return {
                'exploration_path': [],
                'visited_pois': [],
                'interesting_pois': [],
                'mental_map': {},
                'total_distance': 0.0,
                'exploration_time': 0.0,
                'poi_count': 0
            }
    
    def _calculate_total_distance(self) -> float:
        """计算总探索距离"""
        try:
            exploration_path = getattr(self, 'exploration_path', [])
            if len(exploration_path) < 2:
                return 0.0
                
            total_distance = 0
            map_service = getattr(self, 'map_service', None)
            
            if not map_service:
                print("地图服务未初始化，无法计算距离")
                return 0.0
            
            for i in range(1, len(exploration_path)):
                try:
                    prev_location = exploration_path[i-1].get('location', [0, 0])
                    curr_location = exploration_path[i].get('location', [0, 0])
                    
                    # 确保位置数据有效
                    if not prev_location or not curr_location:
                        continue
                        
                    distance = map_service.calculate_distance(prev_location, curr_location)
                    total_distance += distance
                except Exception as e:
                    print(f"计算第{i}段距离时出错: {e}")
                    continue
                    
            return total_distance
        except Exception as e:
            print(f"计算总距离时发生错误: {e}")
            return 0.0
    
    def get_current_status(self) -> Dict:
        """获取当前状态"""
        # 确定当前状态描述
        if not self.is_exploring:
            current_status = "待机中"
        elif hasattr(self, '_current_action'):
            current_status = self._current_action
        else:
            current_status = "探索中"
            
        # 获取最近的决策信息
        last_decision = None
        if hasattr(self, '_last_decision') and self._last_decision:
            last_decision = self._last_decision
            
        # 获取已访问POI的名称列表
        visited_poi_names = []
        for poi_info in self.interesting_pois:
            poi_name = poi_info.get('poi', {}).get('name')
            if poi_name:
                visited_poi_names.append(poi_name)
        
        # 确保exploration_path格式正确：[[lat, lng], [lat, lng], ...]
        formatted_exploration_path = []
        if self.exploration_path:
            for point in self.exploration_path:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    # 确保格式为[纬度, 经度]
                    formatted_exploration_path.append([float(point[0]), float(point[1])])
                elif isinstance(point, dict) and 'lat' in point and 'lng' in point:
                    # 处理字典格式的坐标
                    formatted_exploration_path.append([float(point['lat']), float(point['lng'])])
                elif isinstance(point, dict) and 'latitude' in point and 'longitude' in point:
                    # 处理另一种字典格式
                    formatted_exploration_path.append([float(point['latitude']), float(point['longitude'])])
            
        return {
            'current_location': self.current_location,
            'is_exploring': self.is_exploring,
            'current_status': current_status,
            'visited_poi_count': len(self.visited_pois),
            'visited_pois': visited_poi_names,  # 添加已访问POI名称列表
            'exploration_distance': self._calculate_total_distance(),
            'exploration_steps': getattr(self, 'exploration_steps', 0),
            'last_decision': last_decision,
            'total_pois_in_map': len(self.all_boundary_pois or []),
            'mental_map_size': len(self.mental_map.get('poi_relationships', {})),
            'exploration_path': formatted_exploration_path,
            'exploration_complete': bool(self.exploration_complete),
            'round_index': int(getattr(self, 'exploration_round', 1)),
            'rounds_completed': int(getattr(self, 'rounds_completed', 0))
        }
    
    def answer_location_question(self, question: str) -> str:
        """回答关于位置的问题"""
        question_lower = question.lower()
        
        try:
            # 问题1：总探索距离
            if any(keyword in question_lower for keyword in ['走了', '多远', '总距离', '探索距离']):
                total_distance = self._calculate_total_distance()
                if total_distance > 0:
                    return f"我总共走了 {total_distance:.0f} 米的距离。"
                else:
                    return "我还没有开始移动，总探索距离为0米。"
            
            # 问题2：已探索POI数量
            elif any(keyword in question_lower for keyword in ['探索了', '哪些poi', '多少poi', 'poi数量']):
                if self.interesting_pois:
                    poi_names = [poi_info['poi']['name'] for poi_info in self.interesting_pois]
                    return f"我总共探索了 {len(poi_names)} 个POI：{', '.join(poi_names)}。"
                else:
                    return "我还没有探索到任何POI。"
            
            # 问题3：路径规划相关问题（使用路径记忆系统）
            elif any(keyword in question_lower for keyword in ['路径', '路线', '怎么走', '如何到达', '最短路径']):
                return self.path_memory.answer_path_question(question)
            
            # 问题4：POI相对位置（优先级提高，包含具体POI名称或相对位置关键词）
            elif (any(keyword in question_lower for keyword in ['相对', '位于']) or 
                  any(poi_info['poi']['name'] in question for poi_info in self.interesting_pois) or
                  ('在' in question and ('什么位置' in question or '哪个位置' in question or '什么方向' in question))):
                return self._describe_poi_relationships(question)
            
            # 问题5：当前位置（更精确的判断条件）
            elif any(keyword in question_lower for keyword in ['我现在', '我当前', '我的位置', '我在哪']):
                return self._describe_current_location()
            
            # 问题6：最近POI方向
            elif any(keyword in question_lower for keyword in ['最近', '方向', '哪个方向']):
                return self._describe_nearest_poi_direction()
            
            # 问题7：POI在地图中的位置
            elif any(keyword in question_lower for keyword in ['地图', '坐标', '经纬度']):
                return self._describe_poi_locations(question)
            
            else:
                return "我可以回答关于探索距离、POI数量、路径规划、当前位置、POI相对关系和地图坐标的问题。请问您想了解什么？"
                
        except Exception as e:
            return f"回答问题时出错：{e}"

    def set_memory_mode(self, mode: str) -> None:
        try:
            m = str(mode or "context").lower()
            if m in ("context", "graph", "map"):
                self.memory_mode = m
        except Exception:
            pass

    def get_memory_summary(self) -> Dict:
        try:
            if self.memory_mode == "graph":
                snap = self.path_memory.build_graph_memory_snapshot()
                return {
                    "mode": "graph",
                    "data": snap,
                    "counts": {
                        "nodes": len(snap.get("nodes", [])),
                        "edges": len(snap.get("edges", [])),
                        "poi_relations": len(snap.get("poi_relations", []))
                    }
                }
            if self.memory_mode == "map":
                boundary = self.exploration_boundary or []
                snap = self.path_memory.build_map_memory_snapshot(boundary, 20)
                cells = (snap.get("road_grid", {}) or {}).get("cells", [])
                return {
                    "mode": "map",
                    "data": snap,
                    "counts": {
                        "nodes": len(snap.get("nodes", [])),
                        "road_cells": len(cells)
                    }
                }
            stats = self.path_memory.get_memory_stats()
            return {"mode": "context", "counts": stats}
        except Exception as e:
            return {"mode": self.memory_mode, "error": str(e)}
    
    def _describe_current_location(self) -> str:
        """描述当前位置"""
        if not self.current_location:
            return "我还没有初始化位置信息。"
        
        description = "我当前正在探索区域中。"
        
        # 查找最近的已访问POI
        nearest_poi = None
        min_distance = float('inf')
        
        for poi_info in self.interesting_pois:
            poi_location = poi_info['poi']['location']
            distance = self.map_service.calculate_distance(self.current_location, poi_location)
            if distance < min_distance:
                min_distance = distance
                nearest_poi = poi_info['poi']
        
        if nearest_poi and min_distance < 500:  # 500米内
            direction = self._calculate_direction(self.current_location, nearest_poi['location'])
            description += f"\n我距离 {nearest_poi['name']} 约 {min_distance:.0f}米，位于其{direction}方向。"
        
        return description
    
    def _describe_poi_relationships(self, question: str) -> str:
        """描述POI之间的相对位置关系 - 增强空间认知"""
        if len(self.interesting_pois) == 0:
            return "我还没有探索过任何POI，无法回答POI之间的相对位置关系。请先让我探索一些POI。"
        
        if len(self.interesting_pois) < 2:
            return "我只探索过1个POI，需要探索更多POI才能描述它们之间的相对位置关系。"
        
        # 提取问题中的POI名称
        mentioned_pois = []
        for poi_info in self.interesting_pois:
            poi_name = poi_info['poi']['name']
            if poi_name in question:
                mentioned_pois.append(poi_info['poi'])
        
        # 如果问题中提到了具体的POI
        if len(mentioned_pois) >= 2:
            poi1, poi2 = mentioned_pois[0], mentioned_pois[1]
            distance = self.map_service.calculate_distance(poi1['location'], poi2['location'])
            direction = self._calculate_direction(poi1['location'], poi2['location'])
            
            return f"{poi2['name']}位于{poi1['name']}的{direction}方向，距离约{distance:.0f}米。"
        
        elif len(mentioned_pois) == 1:
            # 如果只提到一个POI，描述它与其他POI的关系
            target_poi = mentioned_pois[0]
            relationships = []
            
            for poi_info in self.interesting_pois:
                other_poi = poi_info['poi']
                if other_poi['id'] != target_poi['id']:
                    distance = self.map_service.calculate_distance(target_poi['location'], other_poi['location'])
                    direction = self._calculate_direction(target_poi['location'], other_poi['location'])
                    relationships.append(f"{other_poi['name']}在{target_poi['name']}的{direction}方向，距离约{distance:.0f}米")
            
            if relationships:
                return f"关于{target_poi['name']}的位置关系：\n" + "\n".join(relationships)
        
        # 如果没有提到具体POI，返回所有POI的相对关系概述
        return self._describe_all_poi_relationships()
    
    def _describe_all_poi_relationships(self) -> str:
        """描述所有POI的相对关系概述"""
        if len(self.interesting_pois) < 2:
            return "需要至少2个POI才能描述相对关系。"
        
        relationships = []
        poi_list = [poi_info['poi'] for poi_info in self.interesting_pois]
        
        # 计算所有POI之间的相对关系
        for i, poi1 in enumerate(poi_list):
            for j, poi2 in enumerate(poi_list):
                if i < j:  # 避免重复计算
                    distance = self.map_service.calculate_distance(poi1['location'], poi2['location'])
                    direction = self._calculate_direction(poi1['location'], poi2['location'])
                    relationships.append(f"{poi2['name']}位于{poi1['name']}的{direction}方向，距离约{distance:.0f}米")
        
        return "已探索POI的相对位置关系：\n" + "\n".join(relationships[:5])  # 限制显示前5个关系
    
    def _describe_poi_pair_relationship(self, poi1: Dict, poi2: Dict) -> str:
        """描述两个POI之间的关系"""
        distance = self.map_service.calculate_distance(poi1['location'], poi2['location'])
        direction = self._calculate_direction(poi1['location'], poi2['location'])
        reverse_direction = self._calculate_direction(poi2['location'], poi1['location'])
        
        return f"{poi1['name']} 位于 {poi2['name']} 的{reverse_direction}方向，距离约 {distance:.0f}米；" \
               f"{poi2['name']} 位于 {poi1['name']} 的{direction}方向。"
    
    def _describe_poi_locations(self, question: str) -> str:
        """描述POI在地图中的位置"""
        if not self.interesting_pois:
            return "我还没有探索到任何POI。"
        
        # 提取问题中的POI名称
        target_poi = None
        for poi_info in self.interesting_pois:
            poi_name = poi_info['poi']['name']
            if poi_name in question:
                target_poi = poi_info['poi']
                break
        
        if target_poi:
            # 描述特定POI的位置（相对位置描述）
            description = f"{target_poi['name']} 的位置信息："
            
            # 相对于当前位置的描述
            if self.current_location:
                distance = self.map_service.calculate_distance(self.current_location, target_poi['location'])
                direction = self._calculate_direction(self.current_location, target_poi['location'])
                description += f"\n相对于我当前位置，{target_poi['name']} 位于{direction}方向，距离约 {distance:.0f}米。"
            
            return description
        else:
            # 描述所有POI的相对位置
            descriptions = []
            for poi_info in self.interesting_pois:
                poi = poi_info['poi']
                if self.current_location:
                    distance = self.map_service.calculate_distance(self.current_location, poi['location'])
                    direction = self._calculate_direction(self.current_location, poi['location'])
                    descriptions.append(f"{poi['name']}：位于我的{direction}方向，距离约{distance:.0f}米")
                else:
                    descriptions.append(f"{poi['name']}：已探索")
            
            return "已探索的POI位置：\n" + "\n".join(descriptions)
    
    def _calculate_direction(self, from_location: List[float], to_location: List[float]) -> str:
        """计算方向 - 使用更精确的地理坐标计算"""
        lat1, lng1 = from_location
        lat2, lng2 = to_location
        
        # 将经纬度转换为弧度
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlng_rad = math.radians(lng2 - lng1)
        
        # 使用更精确的方位角计算公式
        y = math.sin(dlng_rad) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlng_rad)
        
        # 计算方位角（弧度）
        bearing_rad = math.atan2(y, x)
        
        # 转换为度数并标准化到0-360度
        bearing_deg = math.degrees(bearing_rad)
        bearing_deg = (bearing_deg + 360) % 360
        
        # 转换为8个主要方向
        directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        
        # 计算方向索引（每个方向占45度）
        index = int((bearing_deg + 22.5) / 45) % 8
        return directions[index]
    
    def _describe_nearest_poi_direction(self) -> str:
        """描述最近POI的方向"""
        if not self.interesting_pois:
            return "我还没有探索到任何POI。"
        
        if not self.current_location:
            return "我还没有初始化位置信息。"
        
        # 找到最近的POI
        nearest_poi = None
        min_distance = float('inf')
        
        for poi_info in self.interesting_pois:
            poi_location = poi_info['poi']['location']
            distance = self.map_service.calculate_distance(self.current_location, poi_location)
            if distance < min_distance:
                min_distance = distance
                nearest_poi = poi_info['poi']
        
        if nearest_poi:
            direction = self._calculate_direction(self.current_location, nearest_poi['location'])
            return f"最近的POI是 {nearest_poi['name']}，位于我的{direction}方向，距离约 {min_distance:.0f}米。"
        else:
            return "没有找到附近的POI。"
    

    
    def _calculate_distance(self, location1: List[float], location2: List[float]) -> float:
        """计算两点之间的距离（米）"""
        lat1, lng1 = location1
        lat2, lng2 = location2
        
        # 使用Haversine公式计算地球表面两点间的距离
        R = 6371000  # 地球半径（米）
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat_rad = math.radians(lat2 - lat1)
        dlng_rad = math.radians(lng2 - lng1)
        
        a = (math.sin(dlat_rad / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(dlng_rad / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _is_within_boundary(self, location):
        """检查位置是否在探索边界内"""
        if not self.exploration_boundary:
            return True
            
        lat, lng = location
        
        # 简单的边界框检查
        min_lat = min(point[0] for point in self.exploration_boundary)
        max_lat = max(point[0] for point in self.exploration_boundary)
        min_lng = min(point[1] for point in self.exploration_boundary)
        max_lng = max(point[1] for point in self.exploration_boundary)
        
        return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng
