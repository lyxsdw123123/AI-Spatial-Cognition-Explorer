# AI评估代理

import asyncio
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from dashscope import Generation
from langchain.prompts import PromptTemplate

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import Config

class EvaluationAgent:
    """AI评估代理，负责根据探索经验回答空间意识评估问题"""
    
    def __init__(self):
        self.api_key = Config.DASHSCOPE_API_KEY
        self.model = "qwen-turbo"
        self.temperature = 0.1
        
        self.evaluation_id = None
        self.questions = []
        self.exploration_data = {}
        self.answers = []
        self.status = "idle"  # idle, running, completed, failed
        self.result = None
        self.last_error = None
        
        self.evaluation_prompt = PromptTemplate(
            input_variables=["exploration_context", "question", "options"],
            template="""
你是一个AI探索者。以下是你最后一次探索过程中记录的上下文，仅此为依据：

探索上下文：
{exploration_context}

严格规则：
1. 只使用提供的探索上下文，不引入任何未提供的数据与常识。
2. 若依据不足，需在解释中明确说明，但仍输出最合理的选项字母。
3. 方位角标准：统一以地理正北为0°起点，顺时针递增；90°为正东，180°为正南，270°为正西。严禁以“自身朝向”为0°或重定义角度基准。
4. 方向判断与距离比较均以上下文中的数值或明确叙述为准。

问题：{question}

选项：
{options}

输出格式：
答案：<A/B/C/D>
解释：<基于上述探索上下文的简洁中文解释>
"""
        )

        self.evaluation_prompt_text = PromptTemplate(
            input_variables=["exploration_context", "question", "options"],
            template="""
你是一个仅依赖文本记忆的AI探索者。仅使用下方上下文中的文字叙述作为依据：

探索上下文：
{exploration_context}

文本记忆规则：
1. 方位角标准：统一以地理正北为0°起点，顺时针递增；90°为正东，180°为正南，270°为正西。严禁以“自身朝向”为0°或重定义角度基准。例如：POI：金德大厦
   - 视野内POI（方向度数；距离米）：
     • 信德商务大厦：方向 353°，距离 ≈ 445m
     • 宝升商业大厦：方向 245°，距离 ≈ 282m
     你可以得知信德商务大厦位于金德大厦西北方向，距离金德大厦约445米。宝升商业大厦相对于金德大厦西南方向，距离金德大厦约282米。
2. 关于直线距离判断问题，使用两点之间直线最短距离，而不是最短路径距离，切勿搞混。
3. 引用范围：只引用上下文中出现的实体名称、方向度数（如30°/北偏东等）与距离词（如200米/近/远），不引入外部常识或新增关系。
4. 判断依据：比较方向或距离必须基于上下文原文的度数或距离表述。
5. 依据不足：若上下文未出现相关实体或数值，解释中需明确指出“依据不足”。

问题：{question}

选项：
{options}

输出格式：
答案：<A/B/C/D>
解释：<引用文本中的实体/方向/距离进行说明>
"""
        )

        self.evaluation_prompt_graph = PromptTemplate(
            input_variables=["exploration_context", "question", "options"],
            template="""
你是一个依赖图记忆（节点-边）的AI探索者。仅使用上下文中的节点与连通关系作为依据：

探索上下文：
{exploration_context}

图记忆规则：
1. 方位角标准：统一以地理正北为0°起点，顺时针递增；90°为正东，180°为正南，270°为正西。严禁以“自身朝向”为0°或重定义角度基准。
2. 参数含义与对应关系：节点列表采用“NODE[id,类型]”，其中id为唯一编号，类型为POI/ROAD；边列表采用“EDGE[起点ID,终点ID,道路长度]”，长度单位为米（m）。任一边的起点ID与终点ID必须出现在节点列表中，图的连通性完全由边集合定义。
3.节点类型语义： POI 表示兴趣点， ROAD 表示道路关键节点；路径规划优先在 ROAD 节点间依据边集合进行， POI 用于相对位置与目标识别。
4.路径选择策略：优先“总边权最小”；缺失边权则“边数最少”；并列时按“出现顺序优先”稳定裁决。
5. 连通性约束：禁止引入未出现的连接或节点；路径推理与相对位置分析仅基于上下文提供的节点与边集合。
6. 路径推理范围：仅在给定边集合上进行路径与方向判断。
7. 方向与相对位置：以上下文提供的邻接方向或从节点到节点的方向描述为准。
8. 距离比较：优先依据边权或明确距离；若缺失，仅可基于步数/边数近似比较，并在解释中说明。
9. 示例说明：例如“EDGE[12,9,180m]”表示从节点12到节点9存在一条边，长度180米；方向为从起点指向终点的方位角，按“正北为0°、顺时针递增”计算。
10. 依据不足：若题目涉及的节点或关系未在上下文出现，解释中需标注“依据不足”。

问题：{question}

选项：
{options}

输出格式：
答案：<A/B/C/D>
解释：<引用节点、边与路径长度/方向来说明>
"""
        )

        self.evaluation_prompt_map = PromptTemplate(
            input_variables=["exploration_context", "question", "options"],
            template="""
你是一个依赖MAP栅格记忆的AI探索者。仅使用上下文中的栅格坐标与连通规则作为依据：

探索上下文：
{exploration_context}

 MAP记忆规则：
 1. 方位角标准：统一以地理正北为0°起点，顺时针递增；90°为正东，180°为正南，270°为正西。严禁以“自身朝向”为0°或重定义角度基准。
 2. 参数含义与对应关系：[栅格参数]中的 grid_size 为区域栅格划分份数，grid_cell_size_m 为单元边长（米）；road_grid.cells 为可通行栅格坐标集合；坐标(i,j)定义为 i向北递增、j向东递增。
 3. 节点坐标参数说明：节点条目采用“NODE[id,类型,name,(i,j)]”，其中 id 为唯一编号，类型为 POI/ROAD，name 为名称（可选），(i,j) 为该节点的栅格坐标；节点坐标需遵循同一坐标系定义（i向北递增、j向东递增），用于在解释中明确节点相对位置与方向关系。
 4. 路径数据规范：ROAD[(i1,j1)，(i2,j2)，…] 表示按可通行栅格顺序组成的路径；序列各坐标必须属于 road_grid.cells 并满足逐步上下左右邻接。
 5. 路径连通规则：仅在给定可通行栅格上规划路径（上下左右邻接），禁止引入未出现的栅格或连通关系。
 6. 距离近似：直线近似为 |Δi|、|Δj| 栅格差乘以 grid_cell_size_m（或使用上下文给出的精确距离）；路径长度近似为步数×grid_cell_size_m。
 7. 方向计算：以起点指向终点（或源格指向目标格）的向量角度计算，遵循方位角标准。
 8. 输出要求：在解释开头明确标注“grid_size=<数值>米”，取自[栅格参数]中的 grid_cell_size_m；若未提供，写“grid_size=未提供”。
 9. 示例说明：例如“ROAD[（4，8），（4，7），…，（4，1）]”表示从(4,8)沿可通行栅格向南到(4,1)；若 grid_cell_size_m=30，则长度近似为7×30=210米；方向约为180°（正南）。
 10. 依据不足：若缺失坐标或连通信息，解释中需明确标注“依据不足”。
 

问题：{question}

选项：
{options}

输出格式：
答案：<A/B/C/D>
解释：<第一行标注grid_size；随后引用栅格坐标差、grid_cell_size_m与连通关系进行说明>
"""
        )

    def _normalize_context_mode(self, mode: Optional[str]) -> str:
        try:
            m = (mode or "").strip().lower()
            if not m:
                return "text"
            if ("map" in m) or ("栅格" in m) or ("网格" in m):
                return "map"
            if ("graph" in m) or ("图" in m):
                return "graph"
            if ("text" in m) or ("文本" in m):
                return "text"
            return "text"
        except Exception:
            return "text"

    def _get_prompt_template(self, mode: Optional[str]) -> PromptTemplate:
        m = self._normalize_context_mode(mode)
        if m == "map":
            return self.evaluation_prompt_map
        if m == "graph":
            return self.evaluation_prompt_graph
        return self.evaluation_prompt_text
    
    async def initialize(self, questions: List[Dict], exploration_data: Dict):
        """初始化评估代理"""
        self.evaluation_id = str(uuid.uuid4())
        self.questions = questions
        self.exploration_data = exploration_data
        self.answers = []
        self.status = "idle"
        self.result = None
    
    async def start_evaluation(self):
        """开始评估过程"""
        try:
            self.status = "running"
            
            exploration_context = ""
            try:
                if isinstance(self.exploration_data, dict):
                    exploration_context = self.exploration_data.get('context_text') or ""
            except Exception:
                pass
            try:
                print("\n" + "="*50, flush=True)
                print("🧠 发给AI的上下文（仅使用此上下文作为记忆）", flush=True)
                print("="*50, flush=True)
                print(exploration_context, flush=True)
                print("="*50 + "\n", flush=True)
            except Exception:
                pass
            
            rules_block = ""
            try:
                rb = self.exploration_data.get('prompt_rules')
                if isinstance(rb, str) and rb.strip():
                    rules_block = rb.strip()
            except Exception:
                rules_block = ""
            
            for i, question in enumerate(self.questions):
                try:
                    options_list = question['options']
                    qtext = question['question']
                    options_str = "\n".join([
                        f"{chr(65 + j)}. {option}" 
                        for j, option in enumerate(options_list)
                    ])
                    tmpl = self._get_prompt_template(self.exploration_data.get('context_mode'))
                    prompt = tmpl.format(
                        exploration_context=exploration_context,
                        question=qtext,
                        options=options_str
                    )
                    if rules_block:
                        prompt = f"附加规则（优先级最高）：\n{rules_block}\n\n" + prompt
                    response = await self._call_llm_async(prompt)
                    ai_answer = self._extract_answer(response)
                    ai_explanation = self._extract_explanation(response)
                    is_correct = ai_answer == question['correct_answer']
                    answer_record = {
                        "question": qtext,
                        "type": question['category'],
                        "ai_answer": ai_answer,
                        "ai_explanation": ai_explanation,
                        "correct_answer": question['correct_answer'],
                        "is_correct": is_correct,
                        "explanation": question.get('explanation', '')
                    }
                    self.answers.append(answer_record)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    self.last_error = str(e)
                    print(f"回答问题 {i+1} 时出错: {e}")
                    self.status = "failed"
                    break
            
            # 计算评估结果
            if self.status != "failed":
                self._calculate_result()
                self.status = "completed"
            
        except Exception as e:
            print(f"评估过程出错: {e}")
            self.status = "failed"
    
    def _build_exploration_context(self) -> str:
        """构建探索上下文（路径单元格式，仅使用相对方向与距离，不打印坐标）"""
        context_parts = []

        new_data = self.exploration_data.get('new_exploration_data') or {}
        exploration_paths = new_data.get('exploration_paths') or []
        # 调试：输入摘要
        try:
            is_dict = isinstance(new_data, dict)
            print(f"[DEBUG] 输入数据: new_data_is_dict={is_dict}, keys={list(new_data.keys()) if is_dict else 'N/A'}", flush=True)
            print(f"[DEBUG] exploration_paths_len={len(exploration_paths) if isinstance(exploration_paths, list) else 'N/A'}", flush=True)
        except Exception:
            pass
        # 过滤掉首段“道路→POI”的路径，直接从第一个POI开始
        try:
            if isinstance(exploration_paths, list) and exploration_paths:
                first = exploration_paths[0] or {}
                start = first.get('start_poi') or {}
                name = start.get('name')
                if isinstance(name, str):
                    n = name.strip()
                    # 常见道路起点名称："道路"、"起点道路"、或包含"道路"的名称（如"道路位置_..."）
                    if n in ("道路", "起点道路") or ("道路" in n):
                        exploration_paths = exploration_paths[1:]
        except Exception:
            # 过滤过程非关键路径，出错时忽略，保持原有逻辑
            pass

        # 辅助：提取坐标用于内部计算（不打印）
        def _to_coords(loc):
            if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                return [float(loc[0]), float(loc[1])]
            elif isinstance(loc, dict):
                return [float(loc.get('latitude') or loc.get('lat') or 0), float(loc.get('longitude') or loc.get('lng') or 0)]
            return [0.0, 0.0]

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

        def _distance(a_lat, a_lng, b_lat, b_lng):
            try:
                import math
                R = 6371000.0
                dlat = math.radians(b_lat - a_lat)
                dlng = math.radians(b_lng - a_lng)
                s = (math.sin(dlat/2)**2 + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(dlng/2)**2)
                return 2 * R * math.asin(math.sqrt(max(0.0, min(1.0, s))))
            except Exception:
                return 0.0

        # 使用 POI点单元 + 完整行驶路径 生成文本（不输出经纬度/兴趣度）
        try:
            poi_units = new_data.get('poi_units') or []
            full_route = new_data.get('full_route') or {}
            # 调试：新结构长度
            try:
                print(f"[DEBUG] poi_units_len={len(poi_units) if isinstance(poi_units, list) else 'N/A'}", flush=True)
                print(f"[DEBUG] full_route_segments_len={len(full_route.get('segments', [])) if isinstance(full_route, dict) else 'N/A'}", flush=True)
            except Exception:
                pass

            # 1) POI点单元记录（按时间顺序）
            if isinstance(poi_units, list) and poi_units:
                context_parts.append("POI点单元记录（按时间顺序）：")
                for idx, unit in enumerate(poi_units, start=1):
                    poi = unit.get('poi') or {}
                    name = poi.get('name') or f"POI_{idx}"
                    context_parts.append(f"{idx}) POI：{name}")

                    visible = unit.get('visible_pois') or []
                    if isinstance(visible, list) and visible:
                        context_parts.append("   - 视野内POI（方向度数；距离米）：")
                        for vp in visible:
                            vname = vp.get('name') or "未知POI"
                            deg = vp.get('direction_deg')
                            dist = vp.get('distance_m')
                            deg_str = f"{int(deg)}°" if isinstance(deg, (int, float)) else "未知方向"
                            dist_str = f"≈ {int(dist)}m" if isinstance(dist, (int, float)) else "未知距离"
                            context_parts.append(f"     • {vname}：方向 {deg_str}，距离 {dist_str}")
                    else:
                        context_parts.append("   - 视野内POI：无")

                    notes = unit.get('notes')
                    if isinstance(notes, str) and notes.strip():
                        context_parts.append(f"   - 备注：{notes.strip()}")

                context_parts.append("")
            else:
                context_parts.append("未提供POI点单元数据")

            # 2) 完整行驶路径（仅方向与距离）
            context_parts.append("完整行驶路径（仅方向与距离）：")
            start_name = full_route.get('start_name') or "起点"
            context_parts.append(f"- 起点：{start_name}")

            segments = full_route.get('segments') or []
            if isinstance(segments, list) and segments:
                for seg in segments:
                    to_name = seg.get('to_name') or "未知终点"
                    deg = seg.get('direction_deg')
                    dist = seg.get('distance_m')
                    deg_str = f"{int(deg)}°" if isinstance(deg, (int, float)) else "未知方向"
                    dist_str = f"≈ {int(dist)}m" if isinstance(dist, (int, float)) else "未知距离"
                    context_parts.append(f"→ {to_name}（方向 {deg_str}，距离 {dist_str}）")
            else:
                context_parts.append("→ 未提供路径段数据")
        except Exception as e:
            import traceback
            print(f"[ERROR] POI点单元/路径生成失败: {e}", flush=True)
            traceback.print_exc()
            context_parts.append("上下文生成失败")

        # 总和统计
        summary = new_data.get('exploration_summary') or {}
        total_pois_visited = summary.get('total_pois_visited')
        total_road_nodes_visited = summary.get('total_road_nodes_visited')
        total_distance_meters = summary.get('total_distance_meters')
        total_time_seconds = summary.get('total_time_seconds')

        context_parts.append("")
        context_parts.append("总和：")
        if total_pois_visited is not None:
            context_parts.append(f"已访问POI数量：{int(total_pois_visited)}")
        if total_road_nodes_visited is not None:
            context_parts.append(f"已访问道路节点数量（只要Name字段的）：{int(total_road_nodes_visited)}")
        if total_distance_meters is not None:
            try:
                context_parts.append(f"总探索距离：{int(total_distance_meters)}米")
            except Exception:
                pass
        if total_time_seconds is not None:
            try:
                context_parts.append(f"探索时间：{int(total_time_seconds)}秒")
            except Exception:
                pass

        # 返回最终发给AI的探索上下文，不在此处打印，避免重复输出
        context_text = "\n".join(context_parts)
        return context_text

    async def _fetch_latest_new_data(self):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:8000/exploration/data") as resp:
                    if resp.status == 200:
                        payload = await resp.json()
                        if isinstance(payload, dict) and payload.get("success") and payload.get("data"):
                            return payload.get("data")
        except Exception as e:
            try:
                print(f"获取最新探索数据失败: {e}")
            except Exception:
                pass
        return None

    async def _call_llm_async(self, prompt: str, retry_count: int = 3) -> str:
        last_error = None
        
        for attempt in range(retry_count):
            try:
                response = Generation.call(
                    model=self.model,
                    prompt=prompt,
                    api_key=self.api_key,
                    temperature=self.temperature
                )
                
                if response.status_code == 200:
                    return response.output.text
                else:
                    last_error = f"API返回错误状态码: {response.status_code}, 消息: {response.message}"
                    print(f"LLM调用失败 (尝试 {attempt + 1}/{retry_count}): {last_error}")
                    
                    if attempt < retry_count - 1:
                        await asyncio.sleep(1)
                        
            except Exception as e:
                last_error = str(e)
                print(f"LLM调用异常 (尝试 {attempt + 1}/{retry_count}): {e}")
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(1)
        
        err_msg = f"LLM调用完全失败，已重试{retry_count}次。最后错误: {last_error}"
        print(err_msg)
        raise RuntimeError(err_msg)
    
    def _extract_answer(self, response: str) -> str:
        """从LLM响应中提取答案"""
        response = response.strip().upper()
        
        # 优先查找明确的答案格式
        import re
        
        # 查找"答案：X"或"答案:X"格式
        answer_pattern = r'答案[：:]\s*([ABCD])'
        match = re.search(answer_pattern, response)
        if match:
            return match.group(1)
        
        # 查找单独的选项字母（前后有空格或标点）
        for option in ['A', 'B', 'C', 'D']:
            # 查找独立的选项字母
            pattern = r'\b' + option + r'\b'
            if re.search(pattern, response):
                return option
        
        # 查找选项格式 "选择X" 或 "我选择X"
        choice_pattern = r'选择\s*([ABCD])'
        match = re.search(choice_pattern, response)
        if match:
            return match.group(1)
        
        # 最后尝试简单包含检查，但要避免误判
        option_counts = {}
        for option in ['A', 'B', 'C', 'D']:
            option_counts[option] = response.count(option)
        
        # 如果某个选项出现次数明显更多，选择它
        max_count = max(option_counts.values())
        if max_count > 0:
            # 找到出现次数最多且唯一的选项
            candidates = [opt for opt, count in option_counts.items() if count == max_count]
            if len(candidates) == 1:
                return candidates[0]
        
        # 如果仍然无法确定，进行智能推测
        print(f"警告：无法从响应中提取明确答案，响应内容：{response[:100]}...")
        
        # 使用随机选择而不是总是返回A
        import random
        fallback_answer = random.choice(['A', 'B', 'C', 'D'])
        print(f"使用随机答案: {fallback_answer}")
        return fallback_answer
    
    def _extract_explanation(self, response: str) -> str:
        try:
            import re
            text = (response or "").strip()
            pattern = r'(解释|依据)[：:]\s*(.*)'
            m = re.search(pattern, text, re.S)
            if m:
                return m.group(2).strip()
            # 回退：去除"答案：X"前缀后的剩余文本
            ans_pref = re.split(r'答案[：:]\s*[ABCD]', text)
            if len(ans_pref) >= 2:
                return ans_pref[1].strip()
            return ""
        except Exception:
            return ""
    
    def _has_context_evidence(self, context_text: str, question_text: str, options: List[str]) -> bool:
        try:
            ctx = (context_text or "").strip()
            q = (question_text or "").strip()
            if not ctx:
                return False
            if "相对于" in q:
                parts = q.split("相对于")
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].replace("在哪个方向？", "").replace("在哪个方向?", "").strip()
                    if left and right and (left in ctx) and (right in ctx):
                        return True
            for opt in options or []:
                if isinstance(opt, str) and opt and (opt in ctx):
                    return True
        except Exception:
            pass
        return False

    def _pick_unknown_option(self, options: List[str]) -> str:
        keywords = ["无法确定", "无法判断", "信息不足", "无法确认", "未知"]
        try:
            for i, opt in enumerate(options or []):
                text = (opt or "")
                if any(k in text for k in keywords):
                    return chr(65 + i)
        except Exception:
            pass
        return 'D' if isinstance(options, list) and len(options) >= 4 else 'A'
    
    def _calculate_result(self):
        """计算评估结果"""
        if not self.answers:
            return
        
        # 计算总分
        total_score = sum(1 for answer in self.answers if answer['is_correct'])
        total_questions = len(self.answers)
        
        # 按类型统计
        type_scores = {}
        for answer in self.answers:
            answer_type = answer['type']
            if answer_type not in type_scores:
                type_scores[answer_type] = {'correct': 0, 'total': 0}
            
            type_scores[answer_type]['total'] += 1
            if answer['is_correct']:
                type_scores[answer_type]['correct'] += 1
        
        # 计算各类型百分比
        for type_name, scores in type_scores.items():
            scores['percentage'] = (scores['correct'] / scores['total']) * 100 if scores['total'] > 0 else 0
        
        self.result = {
            "evaluation_id": self.evaluation_id,
            "total_score": total_score,
            "total_questions": total_questions,
            "accuracy": (total_score / total_questions) * 100 if total_questions > 0 else 0,
            "type_scores": type_scores,
            "answers": self.answers,
            "completed_at": datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "status": self.status,
            "evaluation_id": self.evaluation_id,
            "progress": len(self.answers) / len(self.questions) if self.questions else 0,
            "current_question": len(self.answers),
            "total_questions": len(self.questions),
            "error": self.last_error
        }
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """获取评估结果"""
        return self.result
    
    def reset(self):
        """重置评估状态"""
        self.evaluation_id = None
        self.questions = []
        self.exploration_data = {}
        self.answers = []
        self.status = "idle"
        self.result = None
