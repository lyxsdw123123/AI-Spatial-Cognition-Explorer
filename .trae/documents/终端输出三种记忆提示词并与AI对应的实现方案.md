## 目标
- 在探索结束时，按当前记忆模式在终端输出对应的“探索上下文提示词”，并保证传给AI的提示词与三种记忆系统严格一一对应。

## 总体策略
- 以 `explorer_agent.memory_mode` 为切换源（context|graph|map）。
- 在 `backend/main.py` 的 `stop_exploration()` 完成现有报告构建后：
  - 构建对应模式的提示词文本
  - 打印到终端（保持你当前的输出风格）
  - 将提示词文本随评估数据一起传给 `EvaluationAgent`（优先使用“已提供的提示词”）

## 具体实现
- backend/main.py：新增三类上下文生成函数（严格字段约束）
1) `build_context_prompt_from_path_units(new_exploration_data)`（普通记忆）
- 复用现有 `EvaluationAgent._build_exploration_context()` 的逻辑
- 打印到终端（现有函数已打印）

2) `build_graph_context_prompt(graph_snapshot)`（图记忆）
- 输入来自 `explorer_agent.path_memory.build_graph_memory_snapshot()`，字段仅：
  - nodes: [{id, type}]
  - edges: [{road_id, length_m, from_id, to_id}]
  - poi_relations: [{poi_a_id, poi_b_id, direction_deg, distance_m, road_id}]
- 生成模板化文本（含模式、约束、节点/边摘要、POI关系列表、回答规则、问题占位），打印到终端

3) `build_map_context_prompt(map_snapshot)`（地图记忆）
- 输入来自 `explorer_agent.path_memory.build_map_memory_snapshot(boundary, 30)`，字段仅：
  - nodes: [{id, name, type, i, j}]
  - road_grid: {grid_size, cells:[{i,j}]}
- 生成模板化文本（含模式、约束、节点列表、道路格子计数与抽样、回答规则、问题占位），打印到终端

- backend/main.py：在 `stop_exploration()` 中增加模式分支
- 当 `memory_mode == 'context'`：保持现有 `EvaluationAgent._build_exploration_context()` 输出
- 当 `memory_mode == 'graph'`：
  - `snap = explorer_agent.path_memory.build_graph_memory_snapshot()`
  - `graph_text = build_graph_context_prompt(snap)`
  - 将 `graph_text` 附加给评估数据（见下一节）并打印到终端
- 当 `memory_mode == 'map'`：
  - `snap = explorer_agent.path_memory.build_map_memory_snapshot(explorer_agent.exploration_boundary, 30)`
  - `map_text = build_map_context_prompt(snap)`
  - 将 `map_text` 附加给评估数据并打印到终端

## 与 EvaluationAgent 对接
- evaluation_api.py 的 `/evaluation/start`：扩展 `ExplorationDataModel`，新增可选字段：
  - `context_text: Optional[str]`（直接传入已构建好的提示词文本）
  - `context_mode: Optional[str]`（'context'|'graph'|'map'）
- EvaluationAgent：
  - `initialize()` 将 `exploration_data` 保存；若 `context_text` 存在，则评估时直接使用并打印，不再调用 `_build_exploration_context()`。
  - 保留原功能以兼容“普通记忆”的旧流程

## 终端输出保证
- 在 `stop_exploration()`：
  - 对应模式的上下文文本必定打印；
  - 当进入评估流程时，EvaluationAgent 再次打印最终传给AI的上下文（现有打印保留），两次输出内容保持一致；
- 新增接口 `GET /exploration/context`（可选）：返回最近一次已构建的上下文文本与模式，便于前端或手动验证

## 字段严格性
- Graph：仅 nodes/edges/poi_relations 三类字段；不引入坐标、类型细节或其他属性
- Map：仅 nodes 的 id/name/type/i/j 与 road_grid 的 cells；不引入坐标或其他属性
- Context：保持现有“普通记忆”提示词构造逻辑

## 验证流程
- 本地数据模式下选择区域，开始探索，停止：
  - 切换 `memory_mode = graph`：终端出现图记忆提示词；调用 `/evaluation/start` 时该文本被使用
  - 切换 `memory_mode = map`：终端出现地图记忆提示词；评估使用该文本
  - 切换 `memory_mode = context`：终端输出现有路径单元上下文；评估使用该文本
- 用 `/qa/memory` 查看模式与计数，确保切换生效

## 不影响现有功能
- 不改变现有评估问题与流程；仅增加不同模式下的上下文构造与打印
- 前端已具备模式切换；若需要展示当前上下文，可调用新接口