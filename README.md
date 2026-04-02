# AI 空间认知探索系统（AI Spatial Cognition Explorer）

项目目标：将 AI Agent 放入陌生的真实地理环境中，让其在“有限视野”约束下自主探索并形成“心理地图”，然后用标准化题型对其空间认知能力进行量化评估。

## 实验覆盖（核心矩阵）

### 1) 五模型（默认覆盖）

默认实验脚本按“厂商标识/Provider”组织，覆盖 5 个模型通道：

- qwen（通义）
- openai（OpenAI 兼容接口）
- deepseek（深度求索）
- claude（Anthropic）
- gemini（Google）

说明：代码结构支持继续扩展更多 Provider（例如新增适配器），但本 README 以当前实验常用的 5 模型组合为主。

### 2) 四种记忆（Memory）

用于对比“不同记忆形态”对空间推理的影响：

- raw：原始记忆/原始信息（保留更完整的探索过程与事实信息）
- context：文本叙事记忆（线性记录：从哪到哪、看到什么、做了什么决策）
- graph：拓扑图记忆（POI/节点/连边结构化表达）
- map：栅格/地图记忆（将空间抽象为网格并记录属性）

### 3) 三种探索方式（Exploration）

- 随机 POI 探索（随机目标/随机游走风格）
- 最近距离探索（贪婪策略，优先访问最近未探索点）
- 最短路径探索（路径规划导向，体现 Dijkstra/A* 等能力）

### 4) 15 个区域（Regions）

默认实验区域为 15 个（脚本中作为 REGIONS 列表使用）：

1. 上海外滩
2. 伦敦大本钟
3. 北京天安门
4. 多伦多CN塔
5. 巴黎埃菲尔铁塔
6. 广州塔
7. 旧金山联合广场
8. 柏林勃兰登堡门
9. 武汉黄鹤楼
10. 洛杉矶好莱坞
11. 纽约时代广场
12. 维也纳美泉宫
13. 罗马斗兽场
14. 芝加哥千禧公园
15. 长沙五一广场

### 5) 四种提问方式（Question Strategies）

用于评估阶段的问答策略（同一套题目，用不同提示策略对比）：

- Direct：直接回答
- CoT：Chain-of-Thought（链式推理）
- Self-Consistency：自洽采样/投票
- ToT：Tree-of-Thought（树状推理）

## 项目结构（核心代码不动）

```text
AI_exploer_aoto/
├── backend/                 # FastAPI 后端（探索/记忆/评估核心）
├── frontend/                # Streamlit 前端（地图可视化与控制台）
├── config/                  # 配置
├── data/                    # 本地地理数据（Shapefile 等）
├── txt_statistics/          # 统计/中间数据（如 token cost、汇总等）
├── requirements.txt         # Python 依赖
└── start_backend.py         # 后端启动脚本
└── start_frontend.py        # 前端启动脚本
```

说明：根目录可能还包含大量实验脚本、报告文本、CSV 汇总、日志等，这些属于“实验产物/辅助工具”，不影响核心服务运行。

## 快速开始

### 1) 安装依赖

```bash
pip install -r requirements.txt
```

### 2) 配置密钥（.env）

根目录的 `.env` 用于配置在线服务的密钥（例如高德地图、各模型 API Key）。你可以按当前项目实际使用的 Provider 增删对应字段。

### 3) 启动前后端

```bash
# 终端 1：后端
python start_backend.py

# 终端 2：前端
python start_frontend.py
```

默认访问：

- 前端：`http://localhost:8501`
- 后端：`http://127.0.0.1:8000`

## 实验脚本入口（常用）

根目录提供了多种批处理脚本，主要用于“批量探索 + 批量评估 + 产出 CSV/报告”：

- `batch_exploration_experiment.py`：随机 POI 探索（输出到 `experiment_reports/` 与对应 CSV）
- `batch_exploration_nearest.py`：最近距离探索（输出到 `最近报告/` 与对应 CSV）
- `batch_exploration_shortest.py`：最短路径探索（输出到 `最短报告/` 与对应 CSV）
- `batch_exploration_qwen3.py`：特定模型组合的批量实验（输出到 `qwen3_reports/` 与对应 CSV）
- `evaluate_memory_reports.py` / `evaluate_reports_3memory_with_raw.py`：对已有报告进行离线/二次评估与汇总

提示：这些脚本通常假设后端已启动，并通过 `http://127.0.0.1:8000` 调用探索/评估 API。

## 输出物说明（报告/CSV/日志）

- 报告（.txt/.json）：记录每次探索的过程、记忆摘要与评估结果，便于复盘与对比。
- CSV 汇总：用于后续统计分析（按区域/模型/记忆/策略聚合）。
- `backend.log`：后端运行日志（请求日志 + 运行时输出），用于排错与复现问题。

## 技术栈（概览）

- 前端：Streamlit + Folium（地图可视化与交互控制）
- 后端：FastAPI（REST API）
- 地理数据：GeoPandas / Shapely（空间计算与数据读写）
- AI 编排：LangChain（按项目实际代码使用情况）
