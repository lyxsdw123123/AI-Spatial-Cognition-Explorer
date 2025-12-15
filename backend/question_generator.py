# 空间意识涌现评估题目数据结构
# 基于本地POI数据的静态评估题目

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import sys
import os
import math
import pandas as pd

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.data_service.local_data_service import LocalDataService

@dataclass
class EvaluationQuestion:
    """评估题目数据结构"""
    id: int
    category: str  # 题目类型
    question: str  # 题目内容
    options: List[str]  # 选项列表
    correct_answer: str  # 正确答案字母（A、B、C、D）
    explanation: str  # 答案解释
    difficulty: str  # 难度等级：easy, medium, hard

class EvaluationQuestions:
    """评估题目管理类"""
    
    def __init__(self, region_name: str = "北京天安门"):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.chdir(project_root)
        self.region_name = region_name
        self.local_data_service = LocalDataService(self.region_name)
        self.poi_data = []
        self._load_local_poi_data()
        self.questions = self._generate_static_questions()
    
    def _load_local_poi_data(self):
        """加载本地POI数据"""
        try:
            success = self.local_data_service.load_poi_data()
            if success:
                self.poi_data = self.local_data_service.get_poi_data()
                # print(f"成功加载{len(self.poi_data)}个POI数据用于生成评估题目")
            else:
                print("加载本地POI数据失败")
                self.poi_data = []
        except Exception as e:
            print(f"加载POI数据时出错: {e}")
            self.poi_data = []
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """计算两点间的距离（米）"""
        # 使用Haversine公式计算球面距离
        R = 6371000  # 地球半径（米）
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lng/2) * math.sin(delta_lng/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _get_direction(self, lat1: float, lng1: float, lat2: float, lng2: float) -> str:
        """计算方向（四个对角象限：东北/东南/西北/西南）"""
        delta_lat = lat2 - lat1
        delta_lng = lng2 - lng1
        eps = 1e-9
        if delta_lat >= -eps and delta_lng >= -eps:
            return "东北"
        if delta_lat < -eps and delta_lng >= -eps:
            return "东南"
        if delta_lat < -eps and delta_lng < -eps:
            return "西南"
        return "西北"
    
    def _generate_static_questions(self) -> List[EvaluationQuestion]:
        """基于本地POI数据生成固定的评估题目（动态编号）"""
        questions = []
        
        if not self.poi_data or len(self.poi_data) < 6:
            raise ValueError(f"POI数据不足，无法生成评估题目。当前POI数量: {len(self.poi_data) if self.poi_data else 0}")
        
        # 选择一些有代表性的POI用于生成题目
        selected_pois = self._select_representative_pois()
        
        if len(selected_pois) < 6:
            raise ValueError(f"有效POI数据不足，无法生成评估题目。当前有效POI数量: {len(selected_pois)}")
        
        # 1. 定位与定向题目（8题：原始4题 + 反向4题）
        questions.extend(self._generate_direction_questions(selected_pois))
        
        # 2. 空间距离估算题目（4题）
        questions.extend(self._generate_distance_questions(selected_pois))
        
        # 3. 邻近关系判断题目（4题）
        questions.extend(self._generate_proximity_questions(selected_pois))
        
        # 4. POI密度识别题目（2题）
        questions.extend(self._generate_density_questions(selected_pois))
        
        # 5. 路径规划题目（4题）
        questions.extend(self._generate_path_questions(selected_pois))
        
        # 动态重排ID，确保题目ID从1到N顺序唯一
        for idx, q in enumerate(questions, start=1):
            q.id = idx
        return questions
    
    def _select_representative_pois(self) -> List[Dict]:
        """选择有代表性的POI用于生成题目"""
        # 按类型分组POI
        poi_by_type = {}
        for poi in self.poi_data:
            poi_type = poi.get('type', 'unknown')
            if poi_type not in poi_by_type:
                poi_by_type[poi_type] = []
            poi_by_type[poi_type].append(poi)
        
        # 选择不同类型的POI，确保多样性
        selected = []
        for poi_type, pois in poi_by_type.items():
            # 每种类型最多选择2个
            selected.extend(pois[:2])
            if len(selected) >= 10:
                break
        
        # 如果选择的POI不够，补充更多
        if len(selected) < 10:
            remaining = [poi for poi in self.poi_data if poi not in selected]
            selected.extend(remaining[:10-len(selected)])
        
        return selected[:10]  # 最多返回10个POI
    
    def _generate_direction_questions(self, pois: List[Dict]) -> List[EvaluationQuestion]:
        questions = []
        originals = []
        reverses = []
        count = min(4, len(pois)-1)
        reverse_map = {"东北": "西南", "东南": "西北", "西北": "东南", "西南": "东北"}
        directions = ["东北", "东南", "西北", "西南"]
        
        for i in range(count):
            poi1 = pois[i]
            poi2 = pois[i+1]
            lat1, lng1 = poi1['location']['lat'], poi1['location']['lng']
            lat2, lng2 = poi2['location']['lat'], poi2['location']['lng']
            correct_direction = self._get_direction(lat1, lng1, lat2, lng2)
            options = directions
            correct_answer = chr(65 + directions.index(correct_direction))
            originals.append(EvaluationQuestion(
                id=0,
                category="定位与定向",
                question=f"{poi2['name']}相对于{poi1['name']}在哪个方向？",
                options=options,
                correct_answer=correct_answer,
                explanation=f"{poi2['name']}位于{poi1['name']}的{correct_direction}面。",
                difficulty="medium"
            ))
            reverse_direction = reverse_map.get(correct_direction, correct_direction)
            reverse_answer = chr(65 + directions.index(reverse_direction))
            reverses.append(EvaluationQuestion(
                id=0,
                category="定位与定向",
                question=f"{poi1['name']}相对于{poi2['name']}在哪个方向？",
                options=options,
                correct_answer=reverse_answer,
                explanation=f"{poi1['name']}位于{poi2['name']}的{reverse_direction}面。",
                difficulty="medium"
            ))
        
        questions.extend(originals)
        questions.extend(reverses)
        return questions
    
    def _generate_distance_questions(self, pois: List[Dict]) -> List[EvaluationQuestion]:
        """生成空间距离估算题目"""
        questions = []
        
        for i in range(min(4, len(pois)-2)):
            poi1 = pois[i]
            poi2 = pois[i+2]  # 跳过一个POI，增加距离
            
            lat1, lng1 = poi1['location']['lat'], poi1['location']['lng']
            lat2, lng2 = poi2['location']['lat'], poi2['location']['lng']
            
            distance = self._calculate_distance(lat1, lng1, lat2, lng2)
            
            def _build_bins(d: float) -> Tuple[List[str], str]:
                bins: List[Tuple[int, int]]
                if d < 400:
                    if d < 300:
                        bins = [(0, 100), (100, 200), (200, 300), (300, 500)]
                    else:
                        bins = [(0, 100), (100, 200), (200, 400), (400, 800)]
                elif d < 800:
                    bins = [(0, 200), (200, 400), (400, 800), (800, 1200)]
                else:
                    bins = [(0, 400), (400, 800), (800, 1200), (1200, 2000)]
                options = [f"{lo}-{hi}米" for lo, hi in bins]
                idx = 0
                for i_bin, (lo, hi) in enumerate(bins):
                    if d >= lo and d < hi:
                        idx = i_bin
                        break
                return options, chr(65 + idx)

            options, correct_answer = _build_bins(distance)
            
            question = EvaluationQuestion(
                id=i+5,
                category="空间距离估算",
                question=f"{poi1['name']}到{poi2['name']}的直线距离大约是多少？",
                options=options,
                correct_answer=correct_answer,
                explanation=f"{poi1['name']}到{poi2['name']}的直线距离约为{int(distance)}米。",
                difficulty="medium"
            )
            questions.append(question)
        
        return questions
    
    def _generate_proximity_questions(self, pois: List[Dict]) -> List[EvaluationQuestion]:
        """生成邻近关系判断题目"""
        questions = []
        
        for i in range(min(4, len(pois)-3)):
            center_poi = pois[i]
            nearby_pois = pois[i+1:i+4]  # 选择3个附近的POI
            
            # 计算距离并找到最近的POI
            distances = []
            for poi in nearby_pois:
                lat1, lng1 = center_poi['location']['lat'], center_poi['location']['lng']
                lat2, lng2 = poi['location']['lat'], poi['location']['lng']
                dist = self._calculate_distance(lat1, lng1, lat2, lng2)
                distances.append((poi, dist))
            
            # 按距离排序
            distances.sort(key=lambda x: x[1])
            closest_poi = distances[0][0]
            farthest_poi = distances[-1][0]
            
            # 生成选项
            options = [poi['name'] for poi in nearby_pois]  # 直接使用选项文本，不添加标签
            ask_farthest = (i >= 2)
            target = farthest_poi if ask_farthest else closest_poi
            correct_answer = chr(65 + nearby_pois.index(target))
            
            question = EvaluationQuestion(
                id=i+9,
                category="邻近关系判断",
                question=(f"在以下POI中，哪个距离{center_poi['name']}最远？" if ask_farthest else f"在以下POI中，哪个距离{center_poi['name']}最近？"),
                options=options,
                correct_answer=correct_answer,
                explanation=(
                    f"{farthest_poi['name']}距离{center_poi['name']}最远，约{int(max([d for _, d in distances]))}米。"
                    if ask_farthest
                    else f"{closest_poi['name']}距离{center_poi['name']}最近，约{int(min([d for _, d in distances]))}米。"
                ),
                difficulty="medium"
            )
            questions.append(question)
        
        return questions
    
    def _generate_density_questions(self, pois: List[Dict]) -> List[EvaluationQuestion]:
        questions = []
        poi_densities = []
        for i, poi in enumerate(pois):
            lat1, lng1 = poi['location']['lat'], poi['location']['lng']
            nearby_count = 0
            for j, other_poi in enumerate(pois):
                if i != j:
                    lat2, lng2 = other_poi['location']['lat'], other_poi['location']['lng']
                    distance = self._calculate_distance(lat1, lng1, lat2, lng2)
                    if distance <= 500:
                        nearby_count += 1
            poi_densities.append({'poi': poi, 'density': nearby_count, 'name': poi['name']})
        poi_densities.sort(key=lambda x: x['density'])
        if not poi_densities:
            return questions
        highest_list = poi_densities[-2:][::-1] if len(poi_densities) >= 2 else poi_densities[-1:]
        lowest_list = poi_densities[:2] if len(poi_densities) >= 2 else poi_densities[:1]
        def build_options(correct_item):
            opts = [correct_item]
            for d in poi_densities:
                if d['name'] != correct_item['name'] and len(opts) < 4:
                    opts.append(d)
            return [o['name'] for o in opts]
        for item in highest_list:
            options = build_options(item)
            correct_index = options.index(item['name'])
            questions.append(EvaluationQuestion(
                id=0,
                category="POI密度识别",
                question="在当前区域内，哪个POI周围的POI密度最高？",
                options=options,
                correct_answer=chr(65 + correct_index),
                explanation=f"{item['name']}周围的POI密度最高，500米范围内有{item['density']}个其他POI。",
                difficulty="medium"
            ))
        for item in lowest_list:
            options = build_options(item)
            correct_index = options.index(item['name'])
            questions.append(EvaluationQuestion(
                id=0,
                category="POI密度识别",
                question="在当前区域内，哪个POI周围的POI密度最低？",
                options=options,
                correct_answer=chr(65 + correct_index),
                explanation=f"{item['name']}周围的POI密度最低，500米范围内只有{item['density']}个其他POI。",
                difficulty="medium"
            ))
        return questions
    
    def _generate_path_questions(self, pois: List[Dict]) -> List[EvaluationQuestion]:
        """生成路径规划题目"""
        import random
        questions = []
        
        # 初始化本地数据服务以获取道路网络和节点数据
        local_data_service = LocalDataService(self.region_name)
        local_data_service.load_road_data()
        local_data_service.load_road_nodes_data()
        
        # 检查道路节点数据是否可用
        if (not hasattr(local_data_service, 'road_nodes_gdf') or 
            local_data_service.road_nodes_gdf is None or
            len(local_data_service.road_nodes_gdf) == 0):
            print("⚠️ 道路节点数据不可用，使用简化的路径规划问题")
            return self._generate_simple_path_questions(pois)
        
        # 获取道路节点数据
        road_nodes_data = {}
        for idx, node in local_data_service.road_nodes_gdf.iterrows():
            node_name = node.get('Name')  # 注意这里是大写的Name
            if pd.isna(node_name) or node_name is None or str(node_name).lower() == 'null':
                node_name = None
            
            road_nodes_data[str(idx)] = {
                'id': str(idx),
                'name': node_name,
                'coordinates': (node.geometry.x, node.geometry.y),
                'location': {
                    'lng': node.geometry.x,
                    'lat': node.geometry.y
                }
            }
        
        # 预定义答案分布，确保A、B、C、D都有
        answer_distribution = ['A', 'B', 'C', 'D']
        
        for i in range(min(4, len(pois)-1)):
            start_poi = pois[i]
            end_poi = pois[i+1]
            
            # 获取起点和终点坐标
            start_coords = (start_poi['location']['lng'], start_poi['location']['lat'])
            end_coords = (end_poi['location']['lng'], end_poi['location']['lat'])
            
            # 计算实际路径
            path_coords = local_data_service.find_shortest_path(start_coords, end_coords)
            
            # 生成多个路径选项
            path_options = self._generate_path_options(start_poi, end_poi, path_coords, road_nodes_data, local_data_service, pois)
            
            if len(path_options) >= 2:
                # 找到最短路径
                shortest_option = min(path_options, key=lambda x: x['distance'])
                
                # 确定这道题的正确答案位置
                target_answer = answer_distribution[i] if i < len(answer_distribution) else 'A'
                target_index = ord(target_answer) - 65  # A=0, B=1, C=2, D=3
                
                # 重新排列选项，使最短路径在目标位置
                other_options = [opt for opt in path_options if opt != shortest_option]
                new_options = [None] * 4
                
                # 将最短路径放在目标位置
                new_options[target_index] = shortest_option
                
                # 填充其他位置
                other_index = 0
                for j in range(4):
                    if new_options[j] is None and other_index < len(other_options):
                        new_options[j] = other_options[other_index]
                        other_index += 1
                
                # 如果选项不够4个，用最后一个选项填充
                for j in range(4):
                    if new_options[j] is None:
                        new_options[j] = other_options[-1] if other_options else shortest_option
                
                question = EvaluationQuestion(
                    id=i+15,
                    category="路径规划",
                    question=f"从{start_poi['name']}到{end_poi['name']}，以下哪种路径最短？",
                    options=[option['description'] for option in new_options],
                    correct_answer=target_answer,
                    explanation=f"最短路径是：{shortest_option['description']}，总距离约{int(shortest_option['distance'])}米。",
                    difficulty="hard"
                )
                questions.append(question)
        
        return questions
    
    def _generate_simple_path_questions(self, pois: List[Dict]) -> List[EvaluationQuestion]:
        """生成简化的路径规划题目（当无法加载道路数据时使用）"""
        questions = []
        
        for i in range(min(4, len(pois)-2)):
            start_poi = pois[i]
            end_poi = pois[i+2]
            middle_poi = pois[i+1]
            
            # 计算直接路径和经过中间点的路径距离
            lat1, lng1 = start_poi['location']['lat'], start_poi['location']['lng']
            lat2, lng2 = end_poi['location']['lat'], end_poi['location']['lng']
            lat3, lng3 = middle_poi['location']['lat'], middle_poi['location']['lng']
            
            direct_distance = self._calculate_distance(lat1, lng1, lat2, lng2)
            via_distance = (self._calculate_distance(lat1, lng1, lat3, lng3) + 
                          self._calculate_distance(lat3, lng3, lat2, lng2))
            
            # 判断哪条路径更短
            if direct_distance < via_distance:
                correct_answer = "A"
                explanation = f"直接路径约{int(direct_distance)}米，经过{middle_poi['name']}约{int(via_distance)}米，直接路径更短。"
            else:
                correct_answer = "B"
                explanation = f"直接路径约{int(direct_distance)}米，经过{middle_poi['name']}约{int(via_distance)}米，经过中间点的路径更短。"
            
            question = EvaluationQuestion(
                id=i+15,
                category="路径规划",
                question=f"从{start_poi['name']}到{end_poi['name']}，哪种路径更短？",
                options=[
                "直接前往",
                f"经过{middle_poi['name']}",
                "两种路径距离相同",
                "无法确定"
            ],
                correct_answer=correct_answer,
                explanation=explanation,
                difficulty="hard"
            )
            questions.append(question)
        
        return questions
    
    def _generate_path_options(self, start_poi: Dict, end_poi: Dict, main_path_coords: List, 
                             road_nodes_data: Dict, local_data_service, pois: List[Dict] = None) -> List[Dict]:
        """生成多个路径选项"""
        options = []
        
        # 如果没有传入POI数据，使用类的POI数据
        if pois is None:
            pois = self.poi_data
        
        # 主路径选项
        main_path_description = self._format_path_description(start_poi, end_poi, main_path_coords, road_nodes_data, pois)
        main_path_distance = self._calculate_path_distance(main_path_coords)
        
        options.append({
            'description': main_path_description,
            'distance': main_path_distance,
            'path_coords': main_path_coords
        })
        
        # 计算主路径的节点数量，用于生成相似长度的错误答案
        main_path_node_count = len(main_path_coords) - 2  # 减去起点和终点
        
        # 生成替代路径选项（通过添加一些变化）
        for i in range(3):  # 生成3个额外选项
            # 创建稍微不同的路径描述和距离
            alt_distance = main_path_distance * (1.1 + i * 0.2)  # 增加10%, 30%, 50%的距离
            alt_description = self._create_alternative_path_description(start_poi, end_poi, road_nodes_data, i, main_path_node_count, pois)
            
            options.append({
                'description': alt_description,
                'distance': alt_distance,
                'path_coords': main_path_coords  # 简化处理，使用相同的坐标
            })
        
        return options[:4]  # 最多返回4个选项
    
    def _format_path_description(self, start_poi: Dict, end_poi: Dict, path_coords: List, road_nodes_data: Dict, pois: List[Dict] = None) -> str:
        """格式化路径描述为：起点POI -> (Name字段1) -> (Name字段2) -> ... -> 终点POI"""
        if len(path_coords) <= 2:
            return f"{start_poi['name']} -> {end_poi['name']}"
        
        # 如果没有传入POI数据，使用类的POI数据
        if pois is None:
            pois = self.poi_data
        
        description_parts = [start_poi['name']]
        
        # 找到与路径坐标最接近的道路节点
        for i, coord in enumerate(path_coords[1:-1], 1):  # 跳过起点和终点
            closest_node = self._find_closest_road_node(coord, road_nodes_data)
            if closest_node:
                if closest_node['name']:
                    node_desc = f"({closest_node['name']})"
                else:
                    # 当Name字段为空时，使用最近的POI名称
                    nearest_poi_name = self._find_nearest_poi_for_node(closest_node['coordinates'], pois)
                    node_desc = f"({nearest_poi_name})"
                description_parts.append(node_desc)
        
        description_parts.append(end_poi['name'])
        
        return " -> ".join(description_parts)
    
    def _find_closest_road_node(self, coord: Tuple[float, float], road_nodes_data: Dict) -> Dict:
        """找到最接近给定坐标的道路节点"""
        min_distance = float('inf')
        closest_node = None
        
        for node_id, node_data in road_nodes_data.items():
            node_coord = node_data['coordinates']
            distance = self._calculate_distance(coord[1], coord[0], node_coord[1], node_coord[0])
            
            if distance < min_distance:
                min_distance = distance
                closest_node = node_data
        
        return closest_node
    
    def _find_nearest_poi_for_node(self, node_coord: Tuple[float, float], pois: List[Dict]) -> str:
        """找到距离道路节点最近的POI名称"""
        if not pois:
            return "未知POI"
        
        min_distance = float('inf')
        nearest_poi_name = "未知POI"
        
        for poi in pois:
            poi_lat = poi['location']['lat']
            poi_lng = poi['location']['lng']
            distance = self._calculate_distance(node_coord[1], node_coord[0], poi_lat, poi_lng)
            
            if distance < min_distance:
                min_distance = distance
                nearest_poi_name = poi['name']
        
        return nearest_poi_name
    
    def _calculate_path_distance(self, path_coords: List) -> float:
        """计算路径总距离"""
        if len(path_coords) < 2:
            return 0.0
        
        total_distance = 0.0
        for i in range(len(path_coords) - 1):
            coord1 = path_coords[i]
            coord2 = path_coords[i + 1]
            distance = self._calculate_distance(coord1[1], coord1[0], coord2[1], coord2[0])
            total_distance += distance
        
        return total_distance
    
    def _create_alternative_path_description(self, start_poi: Dict, end_poi: Dict, road_nodes_data: Dict, variant: int, target_length: int = 10, pois: List[Dict] = None) -> str:
        """创建替代路径描述，长度与正确答案相近"""
        import random
        
        # 如果没有传入POI数据，使用类的POI数据
        if pois is None:
            pois = self.poi_data
        
        # 获取所有可用的道路节点
        available_nodes = list(road_nodes_data.values())
        
        if len(available_nodes) < target_length:
            # 如果节点不够，使用所有可用节点
            selected_nodes = available_nodes
        else:
            # 根据目标长度选择节点数量
            if variant == 0:
                # 变体1：目标长度的80-90%
                num_nodes = max(3, int(target_length * 0.8))
            elif variant == 1:
                # 变体2：目标长度的90-100%
                num_nodes = max(4, int(target_length * 0.9))
            else:
                # 变体3：目标长度的70-80%
                num_nodes = max(3, int(target_length * 0.75))
            
            # 随机选择节点
            selected_nodes = random.sample(available_nodes, min(num_nodes, len(available_nodes)))
        
        # 构建路径描述
        description_parts = [start_poi['name']]
        
        for node in selected_nodes:
            if node['name']:
                node_desc = f"({node['name']})"
            else:
                # 当Name字段为空时，使用最近的POI名称
                nearest_poi_name = self._find_nearest_poi_for_node(node['coordinates'], pois)
                node_desc = f"({nearest_poi_name})"
            description_parts.append(node_desc)
        
        description_parts.append(end_poi['name'])
        
        return " -> ".join(description_parts)

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": q.id,
                "category": q.category,
                "question": q.question,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
                "difficulty": q.difficulty,
            }
            for q in self.questions
        ]

    def build_markdown(self) -> str:
        summary = self.get_questions_summary()
        total = len(self.questions)
        lines = []
        lines.append(f"# AI探索评估 - {total}题完整问题集")
        lines.append("")
        lines.append("## 概述")
        lines.append("")
        lines.append(f"本文档包含基于{self.region_name}地区真实POI数据生成的{total}个空间认知评估问题，用于测试AI在陌生环境中的空间意识和认知能力。")
        lines.append("")
        lines.append(f"**数据来源**: {self.region_name}POI数据  ")
        lines.append("**生成时间**: 2025年1月  ")
        lines.append("**问题分布**: ")
        lines.append(f"- 定位与定向: {summary.get('定位与定向', 0)}")
        lines.append(f"- 空间距离估算: {summary.get('空间距离估算', 0)}  ")
        lines.append(f"- 邻近关系判断: {summary.get('邻近关系判断', 0)}")
        lines.append(f"- POI密度识别: {summary.get('POI密度识别', 0)}")
        lines.append(f"- 路径规划: {summary.get('路径规划', 0)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        def _section(title: str, items: List[EvaluationQuestion]):
            lines.append(f"## {title}")
            for idx, q in enumerate(items, start=1):
                lines.append("")
                lines.append(f"### 问题{idx}")
                lines.append(f"**题目**: {q.question}")
                lines.append("")
                lines.append("**选项**:")
                for opt in q.options:
                    lines.append(f"- {opt}")
                lines.append("")
                lines.append(f"**正确答案**: {q.correct_answer}  ")
                lines.append(f"**解释**: {q.explanation}  ")
                lines.append(f"**难度**: {q.difficulty}")
                lines.append("")
                lines.append("---")

        dir_items = [q for q in self.questions if q.category == "定位与定向"]
        dist_items = [q for q in self.questions if q.category == "空间距离估算"]
        prox_items = [q for q in self.questions if q.category == "邻近关系判断"]
        dens_items = [q for q in self.questions if q.category == "POI密度识别"]
        path_items = [q for q in self.questions if q.category == "路径规划"]

        _section("一、定位与定向（8题）", dir_items)
        _section("二、空间距离估算（4题）", dist_items)
        _section("三、邻近关系判断（4题）", prox_items)
        _section(f"四、POI密度识别（{len(dens_items)}题）", dens_items)
        _section("五、路径规划（4题）", path_items)

        return "\n".join(lines)
    
    def save_markdown(self, base_dir: str = None) -> str:
        md = self.build_markdown()
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base = base_dir or os.path.join(project_root, 'data', self.region_name)
        os.makedirs(base, exist_ok=True)
        out_path = os.path.join(base, 'AI探索评估-22题完整问题集.md')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(md)
        return out_path
    

    
    def get_questions_by_category(self, category: str) -> List[EvaluationQuestion]:
        """根据类别获取题目"""
        return [q for q in self.questions if q.category == category]
    
    def get_all_questions(self) -> List[EvaluationQuestion]:
        """获取所有题目"""
        return self.questions
    
    def get_question_by_id(self, question_id: int) -> EvaluationQuestion:
        """根据ID获取题目"""
        for question in self.questions:
            if question.id == question_id:
                return question
        raise ValueError(f"未找到ID为{question_id}的题目")
    
    def get_questions_summary(self) -> Dict[str, int]:
        """获取题目统计信息"""
        summary = {}
        for question in self.questions:
            if question.category not in summary:
                summary[question.category] = 0
            summary[question.category] += 1
        return summary

# 创建全局实例
evaluation_questions = EvaluationQuestions("北京天安门")

# 导出题目列表
EVALUATION_QUESTIONS = evaluation_questions.get_all_questions()
