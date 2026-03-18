# 探索系统与评估系统：传给 Agent 的提示词汇总

更新时间：2026-03-18

本文件汇总当前代码库中两条主链路里，实际发送给大模型/Agent 的提示词（Prompt）模板与拼接规则：

- 探索系统：`ExplorerAgent`（LangChain tools agent）
- 评估系统：`EvaluationAgent`（批量答题，多策略）

说明：

- “传给 Agent 的提示词”指最终传入模型接口的文本内容（system/user message 或 DashScope `prompt=` 的字符串）。
- 代码位置以仓库绝对路径为准，便于定位与比对。

---

## 1. 探索系统（ExplorerAgent）

代码位置：

- 核心：`backend/agent.py` 的 `ExplorerAgent.setup_agent()` 与 `start_exploration()`  
  - [agent.py](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/agent.py)
  - [setup_agent() 片段](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/agent.py#L76-L154)
  - [start_exploration() 片段](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/agent.py#L210-L255)

### 1.1 System Prompt（固定主模板 + mode_hint）

该探索 Agent 使用 `ChatPromptTemplate.from_messages` 组装消息，其中 system message 为以下字符串，并在末尾追加 `mode_hint`（由探索模式决定）。

system message（固定主模板）：

```text
You are an AI explorer in a map environment.
The environment consists of:
1. POI Points (Points of Interest): Specific locations like shops, parks, and landmarks that you can visit.
2. Road Nodes: Key points on the road network (intersections, endpoints) that define where you can move.
3. Road Data: Connectivity information that allows you to navigate along actual paths and streets.

Your goal is to explore the area, visit interesting POIs.
You have access to tools to scan the environment, move to POIs, explore directions, plan paths, and check your memory.

Rules:
1. STRICT SEQUENCE: First use 'scan_environment'. THEN, if interesting POIs are found, use 'move_to_poi' or 'plan_path'.
2. DO NOT move randomly if you have not scanned recently or if there are unvisited POIs visible.
3. If you see unvisited interesting POIs, you MUST visit them. Use 'move_to_poi' directly if close, or 'plan_path' if far/complex.
4. Only use 'explore_direction' if 'scan_environment' returns NO interesting unvisited POIs.
5. Do not visit the same POI twice unless absolutely necessary for navigation.
6. Keep track of your exploration path and avoid backtracking unnecessarily.
```

mode_hint（根据 `exploration_mode` 追加）：

- 最近优先（`exploration_mode` 包含“最近”）：

```text
Mode: Nearest-POI exploration. After each scan_environment call, you MUST choose the single nearest unvisited visible POI as your next target and move there. Do not skip a closer unvisited POI in favour of a farther one. Never call explore_direction while any unvisited visible POIs exist.
```

- 最短路径（`exploration_mode` 包含“最短”）：

```text
Mode: Shortest-path exploration between POI pairs. Repeatedly do the following cycle: (1) pick two distinct POIs (start and end), which you may choose randomly from the currently visible or otherwise known POIs; (2) plan a road-aware path that approximately minimises total travel distance between them (using move_to_poi and any path-planning tools); (3) follow that path step by step until you reach the end POI, then choose a new pair. In this mode, focus on path optimality between the chosen pair, rather than greedily visiting whichever POI is locally nearest.
```

- 默认（随机探索，其它情况）：

```text
Mode: Random exploration. You may choose among visible POIs or directions more freely, while still respecting the basic rules above.
```

### 1.2 User Prompt（每一步循环实际发给模型的输入）

在每个探索循环中，后端构造本轮 user 输入（`input_text`）并调用 `agent_executor.ainvoke({"input": input_text})`。

构造逻辑（当前版本）：

- 先拼状态字符串：
  - `Current Location: <当前坐标>.`
  - 如果已访问过 POI：追加 `Visited POIs count: <数量>.`
- 最终 user input 固定追加一句：
  - `Analyze surroundings and perform the next move.`

最终 user input 形态：

```text
Current Location: [<lat>, <lng>]. Visited POIs count: <n>. Analyze surroundings and perform the next move.
```

对应代码片段：

- [agent.py:L215-L224](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/agent.py#L215-L224)

### 1.3 工具调用与“隐含提示词”

该探索 Agent 使用 LangChain 的 tools agent（优先 `create_openai_tools_agent`，异常时 fallback 到 ReAct）。

- 当走 tools agent 路径时，“工具描述/工具参数 schema”会作为模型可见信息的一部分参与推理（这属于框架层的隐含提示词，不在本仓库以纯文本常量形式出现）。
- 工具调用的返回文本（如 `scan_environment` 返回的 POI 列表/距离/方向）也会成为后续推理的关键上下文。

---

## 2. 评估系统（EvaluationAgent）

代码位置：

- 评估 Agent：`backend/evaluation_agent.py`  
  - [evaluation_agent.py](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/evaluation_agent.py)
  - [提示词模板定义](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/evaluation_agent.py#L42-L198)
  - [策略与拼接逻辑](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/evaluation_agent.py#L319-L449)
- 评估 API（附加规则 prompt_rules 的默认注入）：`backend/evaluation_api.py`  
  - [evaluation_api.py:L170-L205](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/evaluation_api.py#L170-L205)

### 2.1 基础 Prompt：按 context_mode 选择（text/graph/map）

评估时先根据 `context_mode` 选择一个“基础模板”，然后填充：

- `{exploration_context}`：探索上下文纯文本（context_text）
- `{question}`：题干
- `{options}`：四个选项（按 A-D 带标签拼成多行文本）

选择规则：

- `context_mode` 包含 map/栅格/网格 -> `evaluation_prompt_map`
- `context_mode` 包含 graph/图 -> `evaluation_prompt_graph`
- 其它/缺省 -> `evaluation_prompt_text`

对应函数：

- [_get_base_prompt_template()](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/evaluation_agent.py#L224-L230)

注意：

- 文件中还定义了 `evaluation_prompt`（“通用 Direct 模板”），但当前实际选择逻辑不会使用它（默认走 `evaluation_prompt_text/graph/map`）。
- `context_mode=raw` 时同样会回落到 `evaluation_prompt_text`，但会通过 API 注入的 `prompt_rules` 提示模型如何读 raw log（见 2.3）。

### 2.2 三个基础模板（原文）

#### 2.2.1 文本记忆模板（evaluation_prompt_text）

```text
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
```

#### 2.2.2 图记忆模板（evaluation_prompt_graph）

```text
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
```

#### 2.2.3 栅格 MAP 模板（evaluation_prompt_map）

```text
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
```

### 2.3 API 注入的附加规则（prompt_rules，优先级最高）

评估 API 会在请求未显式给出 `prompt_rules` 时，根据 `context_mode` 生成默认规则，并在评估 Agent 内部把它拼到基础模板前面：

拼接形态：

```text
附加规则（优先级最高）：
<prompt_rules>

<基础模板（text/graph/map）...>
```

对应代码：

- [evaluation_api.py:L170-L199](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/evaluation_api.py#L170-L199)
- [evaluation_agent.py:L358-L360](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/evaluation_agent.py#L358-L360)

默认规则（按 mode）：

- graph：

```text
1. 方位角以地理正北为0°、顺时针递增
2. NODE[id,类型]，EDGE[起点ID,终点ID,道路长度m]；仅在给定节点与边集合内推理
3. 路径比较以length_m累加最小为准；并列按边数最少
4. 禁止引入未出现的连接或节点；仅用上下文提供的关系
```

- map：

```text
1. 方位角以地理正北为0°、顺时针递增
2. 坐标系：i向北递增、j向东递增；ROAD为cells的上下左右邻接序列
3. 距离近似：|Δi|、|Δj|×grid_cell_size_m；路径为步数×grid_cell_size_m
4. 解释首行标注grid_size=<数值>米（若未提供则写未提供）；不得引入未出现字段
```

- raw（原始日志阅读提示）：

```text
1. 这是AI探索者与环境交互的原始日志（Raw Log），包含用户的指令、AI的思考过程(Thought)、工具调用(Action)和工具返回结果(Observation)。
2. 请通过阅读这些日志来还原AI的探索路径和所见所闻。
3. 关注日志中的 'Found ... visible POIs' (视野感知) 和 'Successfully moved to ...' (移动行为) 等关键信息。
4. 仅依据日志内容回答问题，不要引入外部知识。
```

- 默认（text 记忆规则补充）：

```text
1. 方位角以地理正北为0°、顺时针递增
2. 距离题用直线距离而非路径距离
3. 仅引用上下文出现的实体/方向/距离；不引入外部常识
4. 依据不足需在解释中明确说明
```

### 2.4 策略层 Prompt 拼接（Direct / CoT / Self-Consistency / ToT）

基础模板构建为 `base_prompt` 后，会按策略继续拼接：

- Direct：直接调用 `base_prompt`
- CoT：`base_prompt + "\n\nLet's think step by step."`
- Self-Consistency：
  - 与 CoT 相同的 prompt
  - 并行采样 5 次（temperature=1.0）
  - 多数投票决定最终答案
- ToT：
  - 阶段 1（Plan）：使用 `tot_plan_prompt`（单独模板）
  - 阶段 2（Candidates）：`base_prompt + 计划 + "Let's think step by step."`，并行生成 3 个候选（temperature=1.0）
  - 阶段 3（Select）：使用 `tot_select_prompt`（单独模板），让模型在候选中选择

ToT 阶段 1：tot_plan_prompt（原文）：

```text
你是一个空间推理专家。基于以下探索上下文，请为解决这个问题制定一个简短的推理计划。
不要直接回答问题，而是列出你应该关注哪些地标、路径或关系，以及如何一步步推导出答案。

探索上下文：
{exploration_context}

问题：{question}
选项：
{options}

请输出你的推理计划（步骤）：
```

ToT 阶段 3：tot_select_prompt（原文）：

```text
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
```

### 2.5 “只输出字母”开关（enable_explanation=False）

当 `enable_explanation` 为 False（当前默认就是 False）时，评估 Agent 会在 `base_prompt` 或 ToT 的 `select_prompt` 末尾追加一段更严格的输出要求，使模型只返回单个字母：

```text
输出要求（严格）：只输出一个大写字母作为答案（对应选项标签），不要输出"答案："前缀、不要输出解释、不要输出任何其他字符。
```

对应代码：

- [evaluation_agent.py:L354-L357](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/evaluation_agent.py#L354-L357)
- [evaluation_agent.py:L442-L445](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/evaluation_agent.py#L442-L445)

### 2.6 最终如何“发给模型”

评估 Agent 最终把拼好的 prompt 作为“单段 user 内容”发给不同模型提供方：

- OpenAI / OpenRouter / DeepSeek / Zhipu：`messages=[{"role":"user","content": prompt}]`
- Qwen（DashScope）：`Generation.call(..., prompt=prompt, ...)`

对应代码：

- [_call_llm_async()](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/evaluation_agent.py#L512-L567)

