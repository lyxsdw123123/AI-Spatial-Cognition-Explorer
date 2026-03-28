# ExplorerAgent（后端探索 Agent）工具汇总

基于：[agent.py](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/agent.py) 与 [tools.py](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/tools.py)。

LangChain Agent 在运行时实际可调用的工具由 [get_exploration_tools](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/tools.py#L18-L86) 提供（当前暴露 5 个工具）。

## 工具一览

| 工具名 | 入参 | 主要用途 | 典型返回（摘要） |
|---|---|---|---|
| scan_environment | 无 | 扫描可见 POI，刷新“当前看到什么” | `Found N visible POIs...` |
| move_to_poi | `poi_name: str` | 朝某个 POI 移动并尝试“到达即访问” | `Successfully moved to and visited ...` |
| explore_direction | `direction: float` `reason: str` | 当附近没有可访问 POI 时，按方向探索移动 | `Explored direction ... Now see N visible POIs.` |
| reselect_start_point | `reason: str` | 多次探索仍无收获时，直接跳转到一个未探索 POI 作为新起点 | `Reselected start point to unexplored POI ...` |
| check_memory | 无 | 查看探索进度摘要（访问数、路径点数） | `Visited X POIs. Path length: Y points.` |

## scan_environment

代码位置：[tool_scan_environment](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/agent.py#L364-L393)，工具注册：[tools.py](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/tools.py#L26-L66)

- 功能：在 `vision_radius` 范围内扫描未访问 POI 列表，并返回文本摘要（包含 POI 名称、类型、距离、方向）。
- 行为要点：
  - 若扫到 POI，会把 `random_move_no_poi_count` 清零（避免触发“连续没 POI 自动重选起点”的逻辑）。
  - 若一个都没有：
    - 如果已知 `available_pois` 且已无未探索 POI：直接停止探索并提示完成。
    - 如果已知 `available_pois` 且仍存在未探索 POI：会触发一次 `reselect_start_point`（后端自动纠偏）。

## move_to_poi

代码位置：[tool_move_to_poi](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/agent.py#L395-L487)，工具注册：[tools.py](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/tools.py#L33-L70)

- 入参：`poi_name`（字符串，允许附带形如 `"xxx (xxx)"` 的后缀，内部会取 `(" (")` 前的 base name 做匹配）。
- 功能：从 `mental_map["available_pois"]` 中按“同名候选”匹配出目标 POI，并选择其中最近的未访问实例移动。
- 异常/防抖逻辑：
  - 对“找不到 POI”的输入做累计计数；超过阈值会停止探索（避免 LLM 反复调用错误目标）。
  - 如果同名 POI 全都已访问，会返回“换目标/改方向”提示，不再移动。
- 移动实现：
  - `use_local_data` 且 `local_data_service` 存在：优先走路网最短路（`find_shortest_path`），并沿路网逐步移动与记录轨迹点。
  - 否则：使用直线插值移动（模拟）。
- 访问判定：
  - 抵达后距离目标 `< 50m`：视为到达并触发访问记录。
  - 使用路网模式时，允许“最后一公里”更宽松（`< 300m` 时可直接贴到 POI 并访问），解决“最近路网点”与 POI 实际点位不一致的问题。

## explore_direction

代码位置：[tool_explore_direction](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/agent.py#L488-L527)，工具注册：[tools.py](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/tools.py#L40-L75)

- 入参：
  - `direction`：角度（0–360）
  - `reason`：选择该方向的理由（会被记录在决策信息里）
- 功能：在没有可访问 POI 时，用于扩展探索范围。
- 行为要点：
  - 移动后会再次计算可见 POI；若看到 POI，会清零 `random_move_no_poi_count` 并返回“现在看到 N 个”。
  - 如果连续多次探索仍看不到 POI，会递增 `random_move_no_poi_count`；当达到 `max_no_poi_moves_before_reselect`（默认 2）时，会自动调用 `reselect_start_point` 跳转到未探索 POI。
  - 若 `available_pois` 已全部探索完成，也会在这里触发停止并返回完成提示。

## reselect_start_point

代码位置：[tool_reselect_start_point](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/agent.py#L528-L575)，工具注册：[tools.py](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/tools.py#L53-L85)

- 入参：`reason`（可空，用于记录为什么需要重选起点）。
- 功能：从未探索 POI 列表里随机挑一个，把当前位置直接设置为该 POI 的坐标，并立刻标记访问（相当于“传送 + 访问”）。
- 典型触发场景：
  - 连续多次 `explore_direction` 仍然“Found 0 visible POIs”。
  - `scan_environment` 发现附近完全没有可见 POI，但全局仍有未探索 POI（后端自动纠偏）。
- 副作用（重要）：
  - `reselect_start_count += 1`，`random_move_no_poi_count = 0`。
  - 会清理 `path_memory` 的部分“当前 leg”状态（若这些字段存在）。
  - 会构造一次“当前位置可见 POI 快照”写入访问记录（用于后续上下文/记忆）。

## check_memory

代码位置：[tool_check_memory](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/agent.py#L611-L613)，工具注册：[tools.py](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/tools.py#L47-L85)

- 功能：返回最简“探索进度摘要”，用于让 Agent 自查目前访问了多少 POI、走过多少路径点。
- 返回：`Visited X POIs. Path length: Y points.`

## 备注：agent.py 内部存在但未暴露的能力

- [tool_plan_path](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/agent.py#L577-L609)：仅在 `use_local_data` 且存在 `local_data_service` 时可用，用于计算到指定 POI 的路网最短路摘要。目前没有在 [get_exploration_tools](file:///d:/a_project_study/AI_exploer_aoto_onlybeijing/AI_exploer_aotoV10/AI_exploer_aoto/backend/tools.py#L18-L86) 中注册为工具，因此 LLM 侧不可直接调用。
