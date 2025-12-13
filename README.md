# 🗺️ AI 空间认知探索系统 (AI Spatial Cognition Explorer)

> **项目目标**：将 AI Agent 放入陌生的地图环境中，使其像人类一样通过自主探索构建属于自己的"心理地图"（Cognitive Map），并通过标准化的空间认知测试来评估其空间意识能力。

## 📖 项目简介

本项目是一个基于 LLM（大语言模型）的自主智能体仿真系统。系统模拟了一个 AI 探索者在城市环境中的移动和感知过程。AI 能够：
1.  **感知环境**：读取周围的 POI（兴趣点）和道路网络。
2.  **自主决策**：根据不同的探索策略（如随机、最近邻、最短路径）规划移动路线。
3.  **构建记忆**：在探索过程中，动态构建不同形式的空间记忆（文本叙述、拓扑图、栅格地图）。
4.  **接受评估**：探索结束后，系统会自动生成一套基于真实地理数据的考卷，测试 AI 的定位定向、距离估算、空间关系判断等能力。

## ✨ 核心功能

### 1. 多模态地图支持
- **在线地图**：集成高德地图与 OpenStreetMap，支持全球范围的区域选择。
- **本地数据**：支持导入本地 Shapefile (.shp) 数据（POI 和路网），实现离线环境下的高精度仿真。

### 2. 智能探索机制
- **多种探索模式**：
  - 🎲 **随机 POI 探索**：随机选择目标，模拟漫无目的的游荡。
  - 📍 **最近距离探索**：贪婪策略，优先访问最近的未探索点。
  - 🛣️ **最短路径探索**：基于 Dijkstra/A* 算法的路径规划能力展示。
- **拟人化移动**：模拟真实的移动速度和视野范围（默认 1000米视野），仅能感知视野内的环境。

### 3. 多样化空间记忆 (Memory Systems)
系统实现了三种不同的记忆构建方式，用于对比 LLM 对空间信息的理解能力：
- 📝 **Context (文本流)**：将探索经历记录为线性的叙事文本（"我从A走到B，看到了C..."）。
- 🕸️ **Graph (拓扑图)**：构建节点（POI/路口）与边（道路）的拓扑网络结构。
- 🗺️ **Map (栅格地图)**：将环境抽象为网格坐标系，记录每个网格的属性。

### 4. 自动化评估系统 (Evaluation)
探索结束后，系统充当"考官"，基于真实的地理数据自动生成试卷：
- **题型**：定位与定向、空间距离估算、邻近关系判断、POI 密度识别、路径规划。
- **评分**：自动比对 AI 的回答与真实地理数据的计算结果，生成详细的得分报告。

## 🛠️ 技术栈

- **前端**：Streamlit (交互界面), Folium (地图可视化)
- **后端**：FastAPI (REST API), WebSocket (实时状态推送)
- **AI 核心**：LangChain, 阿里云通义千问 (DashScope) / OpenAI 兼容接口
- **数据处理**：GeoPandas (地理数据), NetworkX (路网图构建), Shapely
- **算法**：Dijkstra 最短路径算法, Haversine 距离公式

## 📂 项目结构

```text
AI_exploer_aoto/
├── frontend/               # Streamlit 前端应用
│   ├── app.py              # 前端主入口
│   └── local_data_loader.py# 本地 Shapefile 加载器
├── backend/                # FastAPI 后端服务
│   ├── app.py              # 后端主入口 (API & WebSocket)
│   ├── agent.py            # AI 探索者核心逻辑 (ExplorerAgent)
│   ├── evaluation_agent.py # 评估代理 (负责答题)
│   ├── evaluation_api.py   # 评估相关接口
│   ├── map_service.py      # 地图服务管理
│   ├── question_generator.py # 自动化出题模块
│   ├── data_service/       # 本地数据处理服务 (Dijkstra算法等)
│   └── path_memory/        # 空间记忆管理 (Graph/Map构建)
├── config/                 # 配置文件
├── data/                   # 本地地理数据存储 (Shapefiles)
└── requirements.txt        # 项目依赖
```

## 🚀 快速开始

### 1. 环境准备

确保 Python 版本 ≥ 3.9。

```bash
# 克隆项目
git clone [repository_url]
cd AI_exploer_aoto

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API 密钥

在项目根目录创建 `.env` 文件（参考 `.env.example`）：

```ini
# 高德地图 API Key (用于前端底图和在线数据)
AMAP_API_KEY=your_amap_key

# 通义千问 API Key (用于 AI 决策和问答)
DASHSCOPE_API_KEY=your_dashscope_key
```

### 3. 启动系统

推荐使用一键启动脚本（如果提供了 `main.py`）：

```bash
python main.py --mode all
```

或者分别启动前后端：

```bash
# 终端 1：启动后端
python start_backend.py
# (或者直接运行 uvicorn backend.app:app --reload)

# 终端 2：启动前端
python start_frontend.py
# (或者 streamlit run frontend/app.py)
```

### 4. 使用流程

1.  打开浏览器访问 `http://localhost:8501`。
2.  **区域选择**：在侧边栏选择"北京天安门"或其他预设区域。
3.  **本地数据**：勾选"导入本地数据"以获得最佳体验（需确保 `data/` 目录下有对应 Shapefile）。
4.  **初始化**：点击"初始化探索"。
5.  **开始探索**：点击"开始探索"，观察 AI 在地图上的移动。
6.  **停止与评估**：探索一段时间后点击"停止探索"，系统将自动生成评估报告。

## 📊 评估指标

系统会根据 AI 的回答生成以下维度的能力报告：
- **准确率 (Accuracy)**：回答正确的题目比例。
- **空间推理能力**：在缺乏直接观测数据时，能否通过记忆推断出相对位置。
- **幻觉率**：AI 是否编造了不存在的地理关系。

---
*本项目为 AI 空间认知研究的实验性平台。*
