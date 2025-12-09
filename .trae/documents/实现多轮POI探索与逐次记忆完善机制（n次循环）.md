## 总体目标
- 支持AI对同一边界进行n轮探索；每轮结束后用户手动停止，再开始下一轮。
- 每轮保持POI集合不变（每个POI至少被探索过一次），逐轮补全路径和道路记忆。
- 前端仅显示当前“轮次数量”，其余交互不变。

## 轮次与状态管理
- 在探索代理中新增：
  - `exploration_round: int` 当前轮次（默认1）；
  - `ever_visited_pois: Set[id]` 历史累计访问POI；
  - 每轮的 `visited_pois` 与 `exploration_path` 在开始新一轮时重置；
  - 保留、累积 `path_memory` 与 `mental_map`，用于跨轮补全记忆。
- `stop_exploration()` 不清空`path_memory/mental_map`；仅生成该轮报告。
- `start_exploration()` 检测若上轮已停止且`visited_pois`非空，则自增`exploration_round`并重置“本轮”游标与路径累积。

## 记忆完善策略（三种模式）
- Context模式：
  - `new_exploration_data.full_route.segments` 为跨轮合并的路段集合（按POI→POI的路径单元累积）；
  - `poi_units` 使用最新时间序POI快照（保持POI数不变）。
- Graph模式：
  - 保持POI节点总数不变；
  - 每轮追加新发现的道路节点与连通边（`nodes/edges`去重合并）。
- Map模式：
  - 保持POI节点总数不变；
  - 每轮追加/合并道路栅格`road_grid.cells`（去重），节点坐标保持同步；
  - 边界不变，网格参数不变。

## 数据结构与API联动
- 在`new_exploration_data.exploration_summary`中新增：
  - `round_index` 当前轮次；
  - `rounds_completed` 已完成轮次数；
  - 统计数采用“跨轮累计”与“本轮新增”双计：如 `total_road_nodes_visited`（累计），`new_road_nodes_this_round`（本轮新增）。
- `/exploration/status` 增加返回 `round_index`；前端读取并显示。
- 评估阶段沿用现有上下文构建，自动包含最新累计的路径/节点信息，无需额外操作。

## 前端（仅显示轮次）
- 在状态栏/侧边信息区显示：`当前轮次：{round_index}`。
- 用户继续使用“停止探索/开始探索”来人为切换轮次，无需新按钮。

## 校验与可视化
- 每轮结束后：
  - 确认POI数不变、`poi_units_len`稳定；
  - `full_route.segments_len`非递减；
  - Graph模式的`nodes/edges`、Map模式的`road_grid.cells`非递减。
- 日志打印包含轮次信息，便于对比跨轮增长。

## 风险与回退
- 若某轮无新路径（重复原路）：依旧保留轮次计数，但累计结构不变；
- 若探索边界或POI源更新：重置`ever_visited_pois/path_memory/mental_map`并回到第1轮（避免跨数据污染）。

## 交付方式
- 后端与代理的小幅扩展，前端只读显示一处；
- 不影响现有API契约；
- 提供简短演示：完成3轮探索，观察`segments/nodes/cells`随轮次递增。