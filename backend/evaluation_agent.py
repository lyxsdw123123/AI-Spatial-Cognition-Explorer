# AI评估代理

import asyncio
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from dashscope import Generation
from openai import AsyncOpenAI
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatTongyi, ChatOpenAI
from langchain_core.messages import HumanMessage
from zhipuai import ZhipuAI

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
        self.model_provider = "qwen"
        
        self.evaluation_id = None
        self.questions = []
        self.exploration_data = {}
        
        # 策略配置
        self.strategies = ["Direct", "CoT", "Self-Consistency", "ToT"]
        self.current_strategy = None
        self.enable_explanation = False # 控制是否生成文本解释的开关，设置为 False 可关闭解释
        self.results = {}  # {strategy_name: result_dict}
        self.current_strategy_answers = [] # 用于跟踪当前策略的进度
        
        self.status = "idle"  # idle, running, completed, failed
        self.last_error = None
        
        # 基础提示词模板（Direct策略）
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

输出要求（严格）：
- 第一行：答案：<一个大写字母>
- 第二行：解释：<基于上述探索上下文的简洁中文解释>
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

输出要求（严格）：
- 第一行：答案：<一个大写字母>
- 第二行：解释：<引用文本中的实体/方向/距离进行说明>
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

输出要求（严格）：
- 第一行：答案：<一个大写字母>
- 第二行：解释：<引用节点、边与路径长度/方向来说明>
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

输出要求（严格）：
- 第一行：答案：<一个大写字母>
- 第二行：解释：<第一行标注grid_size；随后引用栅格坐标差、grid_cell_size_m与连通关系进行说明>
"""
        )

        # ToT 阶段1：规划提示词
        self.tot_plan_prompt = PromptTemplate(
            input_variables=["exploration_context", "question", "options"],
            template="""
你是一个空间推理专家。基于以下探索上下文，请为解决这个问题制定一个简短的推理计划。
不要直接回答问题，而是列出你应该关注哪些地标、路径或关系，以及如何一步步推导出答案。

探索上下文：
{exploration_context}

问题：{question}
选项：
{options}

请输出你的推理计划（步骤）：
"""
        )

        # ToT 阶段3：选择提示词
        self.tot_select_prompt = PromptTemplate(
            input_variables=["question", "plan", "candidates"],
            template="""
问题：{question}

已制定的推理计划：
{plan}

基于该计划生成的多个候选答案：
{candidates}

请仔细评估上述候选答案，判断哪一个最符合推理计划且逻辑最严密。
请选出你认为最可信的一个作为最终预测。

输出要求（严格）：
- 第一行：答案：<一个大写字母>
- 第二行：解释：<你的最终解释>
"""
        )

    def _build_exploration_context(self) -> str:
        """构建探索上下文（兼容旧版API调用）"""
        # 优先使用已存在的 context_text
        if isinstance(self.exploration_data, dict):
            context = self.exploration_data.get('context_text')
            if context and isinstance(context, str) and context.strip():
                return context
        return "暂无上下文数据"

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

    def _get_base_prompt_template(self, mode: Optional[str]) -> PromptTemplate:
        m = self._normalize_context_mode(mode)
        if m == "map":
            return self.evaluation_prompt_map
        if m == "graph":
            return self.evaluation_prompt_graph
        return self.evaluation_prompt_text
    
    async def initialize(self, questions: List[Dict], exploration_data: Dict, model_provider: str = "qwen", strategies: Optional[List[str]] = None):
        """初始化评估代理"""
        self.evaluation_id = str(uuid.uuid4())
        self.questions = questions
        self.exploration_data = exploration_data
        self.model_provider = model_provider
        self.results = {}
        self.current_strategy = None
        self.current_strategy_answers = []
        self.status = "idle"
        self.last_error = None
        
        if strategies:
            self.strategies = strategies
        else:
            self.strategies = ["Direct", "CoT", "Self-Consistency", "ToT"]
        
        # Initialize LLM based on provider
        self.llm_config = {
            "api_key": Config.DASHSCOPE_API_KEY,
            "model": "qwen-max-latest"
        }
        
        if self.model_provider == "qwen":
            self.llm_config["api_key"] = Config.DASHSCOPE_API_KEY
            self.llm_config["model"] = "qwen-max-latest"
        
        elif self.model_provider.startswith("qwen3"):
            self.llm_config["api_key"] = Config.DASHSCOPE_API_KEY
            self.llm_config["model"] = self.model_provider
            
        elif self.model_provider == "deepseek":
            self.llm_config["api_key"] = Config.DEEPSEEK_API_KEY
            self.llm_config["base_url"] = "https://api.deepseek.com"
            self.llm_config["model"] = "deepseek-chat"
            
        elif self.model_provider == "openai" or self.model_provider == "chatgpt":
            self.llm_config["api_key"] = Config.OPENAI_API_KEY
            self.llm_config["model"] = "gpt-5.2"

        elif self.model_provider.startswith("anthropic/"):
            self.llm_config["api_key"] = Config.OPENROUTER_API_KEY
            self.llm_config["base_url"] = "https://openrouter.ai/api/v1"
            self.llm_config["model"] = self.model_provider

        elif self.model_provider == "claude":
            self.llm_config["api_key"] = Config.OPENROUTER_API_KEY
            self.llm_config["base_url"] = "https://openrouter.ai/api/v1"
            self.llm_config["model"] = "anthropic/claude-3.5-sonnet"
            
        elif self.model_provider == "gemini":
            self.llm_config["api_key"] = Config.OPENROUTER_API_KEY
            self.llm_config["base_url"] = "https://openrouter.ai/api/v1"
            self.llm_config["model"] = "google/gemini-2.5-pro"
            
        elif self.model_provider == "zhipu":
            self.llm_config["api_key"] = Config.ZHIPU_API_KEY
            self.llm_config["model"] = "glm-4.6"
    
    async def start_evaluation(self):
        """开始批量评估过程（顺序执行四种策略）"""
        try:
            self.status = "running"
            self.results = {}
            
            for strategy in self.strategies:
                self.current_strategy = strategy
                self.current_strategy_answers = [] # 重置当前策略的答案列表
                print(f"\n开始执行评估策略: {strategy}")
                
                try:
                    await self._evaluate_single_strategy(strategy)
                except Exception as e:
                    print(f"策略 {strategy} 执行失败: {e}")
                    # 即使一个策略失败，也继续尝试下一个
                    self.results[strategy] = {"error": str(e), "status": "failed"}
                
                # 稍微暂停，避免请求过于密集
                await asyncio.sleep(1)
            
            self.status = "completed"
            
        except Exception as e:
            print(f"评估过程总控出错: {e}")
            self.status = "failed"
            self.last_error = str(e)

    async def _evaluate_single_strategy(self, strategy: str):
        """执行单个策略的评估"""
        exploration_context = ""
        try:
            if isinstance(self.exploration_data, dict):
                exploration_context = self.exploration_data.get('context_text') or ""
        except Exception:
            pass
        
        rules_block = ""
        try:
            rb = self.exploration_data.get('prompt_rules')
            if isinstance(rb, str) and rb.strip():
                rules_block = rb.strip()
        except Exception:
            rules_block = ""
            
        answers = []
        
        for i, question in enumerate(self.questions):
            try:
                options_list = question['options']
                qtext = question['question']
                options_str = "\n".join([
                    f"{chr(65 + j)}. {option}" 
                    for j, option in enumerate(options_list)
                ])
                
                base_tmpl = self._get_base_prompt_template(self.exploration_data.get('context_mode'))
                base_prompt = base_tmpl.format(
                    exploration_context=exploration_context,
                    question=qtext,
                    options=options_str
                )
                
                # 如果关闭了解释功能，修改 Prompt 要求只输出答案
                if not self.enable_explanation:
                    base_prompt += "\n\n输出要求（严格）：只输出一个大写字母作为答案（对应选项标签），不要输出\"答案：\"前缀、不要输出解释、不要输出任何其他字符。"

                if rules_block:
                    base_prompt = f"附加规则（优先级最高）：\n{rules_block}\n\n" + base_prompt
                
                ai_answer = ""
                ai_explanation = ""
                
                # 根据不同策略执行不同的逻辑
                if strategy == "Direct":
                    # 直接提问
                    response = await self._call_llm_async(base_prompt)
                    ai_answer = self._extract_answer(response)
                    ai_explanation = self._extract_explanation(response)
                    
                elif strategy == "CoT":
                    # Zero-Shot CoT
                    # Strict Requirement: append a short instruction ‘Let’s think step by step’ to the end of each task prompt.
                    cot_prompt = base_prompt + "\n\nLet's think step by step."
                    response = await self._call_llm_async(cot_prompt)
                    ai_answer = self._extract_answer(response)
                    ai_explanation = self._extract_explanation(response)
                    
                elif strategy == "Self-Consistency":
                    # Self-Consistency with CoT (5 samples, temp=1.0)
                    # Strict Requirement: sample multiple reasoning chains by setting the model temperature to 1.0 and generating several CoT answers (five).
                    cot_prompt = base_prompt + "\n\nLet's think step by step."
                    responses = []
                    # 并行请求以节省时间
                    tasks = [self._call_llm_async(cot_prompt, temperature=1.0) for _ in range(5)]
                    responses = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    valid_responses = [r for r in responses if isinstance(r, str)]
                    extracted_answers = [self._extract_answer(r) for r in valid_responses]
                    
                    if extracted_answers:
                        # 多数投票
                        from collections import Counter
                        vote_counts = Counter(extracted_answers)
                        ai_answer = vote_counts.most_common(1)[0][0]
                        
                        # 找到第一个匹配该答案的解释
                        for r in valid_responses:
                            if self._extract_answer(r) == ai_answer:
                                ai_explanation = self._extract_explanation(r)
                                break
                    else:
                        ai_answer = "A" # Fallback
                        ai_explanation = "无法获取有效响应"
                        
                elif strategy == "ToT":
                    # Tree-of-Thoughts (ToT)
                    # Strict Requirement:
                    # Stage 1: propose and select a tentative reasoning plan.
                    # Stage 2: conditioned on the chosen plan, the model generates several candidate answers and then selects the one it judges most plausible.
                    
                    # Stage 1: Planning
                    plan_prompt = self.tot_plan_prompt.format(
                        exploration_context=exploration_context,
                        question=qtext,
                        options=options_str
                    )
                    plan = await self._call_llm_async(plan_prompt)
                    
                    # Stage 2: Generate several candidate answers (we use 3 for "several")
                    candidate_gen_prompt = base_prompt + f"\n\n请严格遵循以下推理计划进行思考：\n{plan}\n\nLet's think step by step."
                    
                    cand_tasks = [self._call_llm_async(candidate_gen_prompt, temperature=1.0) for _ in range(3)]
                    candidate_responses = await asyncio.gather(*cand_tasks, return_exceptions=True)
                    valid_candidates = [r for r in candidate_responses if isinstance(r, str) and r.strip()]
                    
                    if not valid_candidates:
                         ai_answer = "A"
                         ai_explanation = "ToT生成候选失败"
                    else:
                        # Stage 3: Selection (Select the most plausible one)
                        candidates_text = ""
                        for idx, cand in enumerate(valid_candidates, 1):
                            candidates_text += f"候选答案 {idx}:\n{cand}\n{'-'*20}\n"
                        
                        select_prompt = self.tot_select_prompt.format(
                            question=qtext,
                            plan=plan,
                            candidates=candidates_text
                        )
                        
                        # 如果关闭了解释功能，修改 ToT 选择阶段的 Prompt 要求只输出答案
                        if not self.enable_explanation:
                            select_prompt += "\n\n输出要求（严格）：只输出一个大写字母作为答案（对应选项标签），不要输出\"答案：\"前缀、不要输出解释、不要输出任何其他字符。"
                        
                        selection_response = await self._call_llm_async(select_prompt, temperature=0.1)
                        ai_answer = self._extract_answer(selection_response)
                        ai_explanation = f"[推理计划]\n{plan}\n\n[最终选定]\n{self._extract_explanation(selection_response)}"

                # 记录结果
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
                answers.append(answer_record)
                self.current_strategy_answers.append(answer_record) # 更新进度
                
                await asyncio.sleep(0.2) # 避免过快
                
            except Exception as e:
                print(f"策略 {strategy} 回答问题 {i+1} 时出错: {e}")
                # 记录错误但继续
                answers.append({
                    "question": question.get('question', ''),
                    "type": question.get('category', ''),
                    "ai_answer": "Error",
                    "ai_explanation": str(e),
                    "correct_answer": question.get('correct_answer', ''),
                    "is_correct": False,
                    "explanation": ""
                })
        
        # 计算并存储该策略的结果
        self.results[strategy] = self._calculate_result_dict(answers)

    def _calculate_result_dict(self, answers: List[Dict]) -> Dict:
        """计算单个策略的结果字典"""
        if not answers:
            return {}
        
        total_score = sum(1 for answer in answers if answer.get('is_correct'))
        total_questions = len(answers)
        
        type_scores = {}
        for answer in answers:
            answer_type = answer.get('type', 'unknown')
            if answer_type not in type_scores:
                type_scores[answer_type] = {'correct': 0, 'total': 0}
            
            type_scores[answer_type]['total'] += 1
            if answer.get('is_correct'):
                type_scores[answer_type]['correct'] += 1
        
        for type_name, scores in type_scores.items():
            scores['percentage'] = (scores['correct'] / scores['total']) * 100 if scores['total'] > 0 else 0
            
        return {
            "total_score": total_score,
            "total_questions": total_questions,
            "accuracy": (total_score / total_questions) * 100 if total_questions > 0 else 0,
            "type_scores": type_scores,
            "answers": answers,
            "completed_at": datetime.now().isoformat()
        }

    async def _call_llm_async(self, prompt: str, retry_count: int = 3, temperature: float = None) -> str:
        """调用LLM，支持覆盖temperature"""
        last_error = None
        current_temp = temperature if temperature is not None else self.temperature
        
        for attempt in range(retry_count):
            try:
                if self.model_provider == "zhipu":
                    def call_zhipu():
                        client = ZhipuAI(api_key=self.llm_config["api_key"])
                        response = client.chat.completions.create(
                            model=self.llm_config["model"],
                            messages=[{"role": "user", "content": prompt}],
                            temperature=current_temp
                        )
                        return response.choices[0].message.content
                    
                    return await asyncio.to_thread(call_zhipu)

                elif not self.model_provider.startswith("qwen"):
                    client = AsyncOpenAI(
                        api_key=self.llm_config["api_key"],
                        base_url=self.llm_config.get("base_url")
                    )
                    response = await client.chat.completions.create(
                        model=self.llm_config["model"],
                        messages=[{"role": "user", "content": prompt}],
                        temperature=current_temp
                    )
                    return response.choices[0].message.content
                else:
                    # Default to Qwen (DashScope)
                    # For Qwen3, ensure enable_thinking is False for non-streaming calls
                    kwargs = {}
                    if self.model_provider.startswith("qwen3"):
                        kwargs["enable_thinking"] = False
                        
                    response = Generation.call(
                        model=self.llm_config["model"],
                        prompt=prompt,
                        api_key=self.llm_config["api_key"],
                        temperature=current_temp,
                        **kwargs
                    )
                    
                    if response.status_code == 200:
                        if response.output.text:
                            return response.output.text
                        # Fallback for models that return content in choices but text is null
                        elif response.output.choices and len(response.output.choices) > 0:
                            msg = response.output.choices[0].message
                            if hasattr(msg, 'content'):
                                return msg.content
                            elif isinstance(msg, dict):
                                return msg.get('content', '')
                        return ""
                    else:
                        last_error = f"API返回错误状态码: {response.status_code}, 消息: {response.message}"
                        print(f"LLM调用失败 (尝试 {attempt + 1}/{retry_count}): {last_error}")
                        if attempt < retry_count - 1:
                            await asyncio.sleep(1)
                        continue

            except Exception as e:
                last_error = str(e)
                print(f"LLM调用异常 (尝试 {attempt + 1}/{retry_count}): {e}")
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(1)
        
        err_msg = f"LLM调用完全失败，已重试{retry_count}次。最后错误: {last_error}"
        print(err_msg)
        return "" # 返回空字符串而不是抛出异常，以免中断整个流程
    
    def _extract_answer(self, response: str) -> str:
        """从LLM响应中提取答案"""
        if not response:
            return "A"
        text = (response or "").strip().upper()
        
        # 0. 如果直接是单个字母
        if text in {"A", "B", "C", "D"}:
            return text

        import re

        # 1. 查找"答案：X"或"答案:X"格式 (增强：支持括号等)
        match = re.search(r"答案[：:]\s*[<（\[]?\s*([ABCD])\s*[>）\]]?", text)
        if match:
            return match.group(1)

        # 2. 查找选项格式 "选择X" 或 "我选择X"
        match = re.search(r"选择\s*([ABCD])", text)
        if match:
            return match.group(1)

        # 3. 查找独立的选项字母
        letters = re.findall(r"\b([ABCD])\b", text)
        uniq = list(dict.fromkeys(letters)) # 去重保持顺序
        if len(uniq) == 1:
            return uniq[0]

        # 4. 统计法
        option_counts = {opt: text.count(opt) for opt in ["A", "B", "C", "D"]}
        max_count = max(option_counts.values())
        if max_count > 0:
            candidates = [opt for opt, count in option_counts.items() if count == max_count]
            if len(candidates) == 1:
                return candidates[0]

        # 5. 随机兜底 (仅在完全无法解析时)
        import random
        return random.choice(["A", "B", "C", "D"])
    
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
            return text # 如果没有特定格式，返回全部文本作为解释
        except Exception:
            return ""

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        total_qs = len(self.questions)
        current_qs = len(self.current_strategy_answers)
        strategy_idx = 0
        if self.current_strategy in self.strategies:
            strategy_idx = self.strategies.index(self.current_strategy) + 1
        
        return {
            "status": self.status,
            "evaluation_id": self.evaluation_id,
            "current_strategy": self.current_strategy,
            "strategy_progress": f"{strategy_idx}/{len(self.strategies)}",
            "current_question": current_qs,
            "total_questions": total_qs,
            "error": self.last_error
        }
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """获取评估结果"""
        if not self.results:
            return self.results
            
        # 返回结果副本并注入上下文信息
        final_result = self.results.copy()
        if self.exploration_data and isinstance(self.exploration_data, dict):
            final_result['context_text'] = self.exploration_data.get('context_text')
            final_result['context_mode'] = self.exploration_data.get('context_mode')
            
        return final_result
    
    def reset(self):
        """重置评估状态"""
        self.evaluation_id = None
        self.questions = []
        self.exploration_data = {}
        self.answers = []
        self.results = {}
        self.current_strategy = None
        self.current_strategy_answers = []
        self.status = "idle"
