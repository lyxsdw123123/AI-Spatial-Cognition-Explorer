# AI地图探索项目

## 项目简介

本项目旨在将AI放入陌生的地图环境中，让AI自主探索周围的POI（兴趣点），并形成属于自己的"心理地图"。

## 核心功能

1. **区域选择**：在前端地图上框选探索区域
2. **AI探索**：AI在指定视野范围内自主探索POI
3. **实时可视化**：前端实时显示AI的移动轨迹和决策过程
4. **心理地图验证**：通过问答检验AI对探索区域的理解

## 技术栈

- **前端**：Streamlit + Folium/Plotly
- **后端**：FastAPI + Uvicorn
- **AI决策**：LangChain + 通义千问
- **地图服务**：高德地图API
- **数据处理**：Pandas + GeoPandas

## 项目结构

```
AI_exploer_aoto/
├── frontend/          # Streamlit前端
├── backend/           # FastAPI后端
├── ai_agent/          # AI决策模块
├── map_service/       # 地图服务模块
├── config/            # 配置文件
├── data/              # 数据存储
└── requirements.txt   # 依赖包
```

## 快速开始

### 1. 环境准备

```bash
# 克隆或下载项目
cd AI_exploer_aoto

# 安装依赖
pip install -r requirements.txt

# 配置API密钥
cp .env.example .env
# 编辑.env文件，填入高德地图和通义千问的API密钥
```

### 2. 获取API密钥

- **高德地图API密钥**：访问 [高德开放平台](https://console.amap.com/dev/key/app) 申请
- **通义千问API密钥**：访问 [阿里云DashScope](https://dashscope.console.aliyun.com/) 申请

### 3. 启动系统

#### 方式一：一键启动（推荐）
```bash
python main.py --mode all
```

#### 方式二：分别启动
```bash
# 启动后端服务
python start_backend.py

# 启动前端应用（新终端）
python start_frontend.py
```

#### 方式三：检查环境
```bash
python main.py --check
```

### 4. 访问系统

- **前端界面**：http://localhost:8501
- **后端API**：http://localhost:8000
- **API文档**：http://localhost:8000/docs

## 使用说明

### 基本流程

1. **选取区域**：在前端地图上框选或选择预设区域
2. **设置AI位置**：指定AI探索者的起始位置
3. **初始化探索**：系统爬取区域内POI数据
4. **开始探索**：AI根据视野和兴趣自主探索
5. **实时监控**：观察AI的移动轨迹和决策过程
6. **停止探索**：查看探索报告和统计数据
7. **问答验证**：测试AI的"心理地图"形成情况

### 功能特性

#### 🎯 智能探索
- AI具有500米视野范围
- 基于LangChain的智能决策
- 自动避免重复探索
- 记录POI兴趣程度和相对位置

#### 🗺️ 地图可视化
- 高德地图底图支持
- 实时显示AI位置和移动轨迹
- 探索边界和视野范围可视化
- POI标记和信息展示

#### 📊 数据分析
- 探索路径统计
- POI访问记录
- 兴趣程度分析
- 心理地图构建

#### 🤖 AI问答
- 位置查询
- POI相关问题
- 距离计算
- 兴趣偏好分析