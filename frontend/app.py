# Streamlit前端应用

import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import json
import asyncio
import websockets
import threading
import time
from typing import List, Dict, Tuple
import pandas as pd
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import Config
from local_data_loader import load_local_shapefile_data
from backend.map_service import MapServiceManager
from backend.question_generator import EVALUATION_QUESTIONS

# 页面配置
st.set_page_config(
    page_title="AI地图探索系统",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化地图服务管理器
@st.cache_resource
def get_map_service_manager():
    """获取地图服务管理器实例"""
    return MapServiceManager()

map_service_manager = get_map_service_manager()

# 全局变量
if 'exploration_boundary' not in st.session_state:
    st.session_state.exploration_boundary = []
if 'ai_location' not in st.session_state:
    st.session_state.ai_location = Config.DEFAULT_CENTER
if 'exploration_path' not in st.session_state:
    st.session_state.exploration_path = []
if 'is_exploring' not in st.session_state:
    st.session_state.is_exploring = False
if 'pois_data' not in st.session_state:
    st.session_state.pois_data = []
if 'ai_status' not in st.session_state:
    st.session_state.ai_status = {}
if 'exploration_report' not in st.session_state:
    st.session_state.exploration_report = None
if 'drawing_mode' not in st.session_state:
    st.session_state.drawing_mode = False
if 'ai_position_mode' not in st.session_state:
    st.session_state.ai_position_mode = False
# 评估相关状态
if 'show_evaluation' not in st.session_state:
    st.session_state.show_evaluation = False
if 'evaluation_answers' not in st.session_state:
    st.session_state.evaluation_answers = {}
if 'evaluation_result' not in st.session_state:
    st.session_state.evaluation_result = None
if 'ai_answering' not in st.session_state:
    st.session_state.ai_answering = False
if 'selected_memory_mode' not in st.session_state:
    st.session_state.selected_memory_mode = '普通'
if 'selected_memory_mode_backend' not in st.session_state:
    st.session_state.selected_memory_mode_backend = 'context'

# 后端API基础URL
BACKEND_URL = f"http://{Config.BACKEND_HOST}:{Config.BACKEND_PORT}"

def call_backend_api(endpoint: str, method: str = "GET", data: dict = None):
    """调用后端API"""
    try:
        url = f"{BACKEND_URL}{endpoint}"
        print(f"调用API: {method} {url}")
        
        # 为评估相关API设置更长的超时时间
        timeout = 60 if endpoint.startswith('/evaluation/') else 10
        
        if method == "GET":
            response = requests.get(url, timeout=timeout)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=timeout)
        else:
            st.error(f"不支持的HTTP方法: {method}")
            return None
        
        print(f"API响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"API调用成功: {endpoint}")
                return result
            except json.JSONDecodeError as e:
                st.error(f"API响应解析失败: {e}")
                print(f"响应内容: {response.text}")
                return None
        else:
            error_msg = f"API调用失败 - 状态码: {response.status_code}"
            try:
                error_detail = response.json().get('detail', '未知错误')
                error_msg += f", 详情: {error_detail}"
            except:
                error_msg += f", 响应内容: {response.text[:200]}"
            
            st.error(error_msg)
            print(error_msg)
            return None
            
    except requests.exceptions.Timeout:
        error_msg = f"API调用超时: {endpoint}"
        st.error(error_msg)
        print(error_msg)
        return None
    except requests.exceptions.ConnectionError:
        error_msg = f"无法连接到后端服务: {BACKEND_URL}"
        st.error(error_msg)
        print(error_msg)
        return None
    except Exception as e:
        error_msg = f"API调用异常: {endpoint} - {str(e)}"
        st.error(error_msg)
        print(error_msg)
        import traceback
        traceback.print_exc()
        return None

def create_map():
    """创建地图"""
    # 地图中心逻辑：AI探索时优先使用AI位置，否则使用第一个边界点，最后是默认中心
    if st.session_state.is_exploring and st.session_state.ai_location:
        center_location = st.session_state.ai_location
    elif st.session_state.exploration_boundary:
        center_location = st.session_state.exploration_boundary[0]
    elif st.session_state.ai_location:
        center_location = st.session_state.ai_location
    else:
        center_location = Config.DEFAULT_CENTER
    
    # 创建基础地图
    m = folium.Map(
        location=center_location,
        zoom_start=Config.DEFAULT_ZOOM,
        tiles=None
    )
    
    # 智能选择底图服务
    # 检测区域类型并选择合适的地图服务
    region_info = map_service_manager.detect_region_and_service(center_location[1], center_location[0])
    service_type = region_info['map_service']
    
    # 获取对应的瓦片图层配置
    tile_config = map_service_manager.get_folium_tile_layer_config(service_type)
    
    # 添加智能选择的底图
    folium.TileLayer(
        tiles=tile_config['tiles'],
        attr=tile_config['attr'],
        name=tile_config['name'],
        overlay=tile_config.get('overlay', False),
        control=tile_config.get('control', True)
    ).add_to(m)
    
    # 在地图上显示当前使用的地图服务信息
    service_info_html = f"""
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 200px; height: 60px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:12px; padding: 5px;">
    <p><b>地图服务:</b> {tile_config['name']}</p>
    <p><b>区域:</b> {region_info['region_name']}</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(service_info_html))
    
    # 添加区域边界
    if st.session_state.exploration_boundary:
        boundary_coords = [[point[0], point[1]] for point in st.session_state.exploration_boundary]
        folium.Polygon(
            locations=boundary_coords,
            color='blue',
            weight=2,
            fill=True,
            fillColor='blue',
            fillOpacity=0.1
        ).add_to(m)
        
        # 添加边界点标记
        for i, point in enumerate(st.session_state.exploration_boundary):
            folium.CircleMarker(
                [point[0], point[1]],
                radius=5,
                popup=f"边界点 {i+1}",
                color='blue',
                fillColor='blue',
                fillOpacity=0.8
            ).add_to(m)
    
    # 添加AI当前位置（增强显示）
    if st.session_state.ai_location:
        # 主要标记
        folium.Marker(
            st.session_state.ai_location,
            popup='🤖 AI探索者',
            tooltip='AI当前位置',
            icon=folium.Icon(color='red', icon='user', prefix='fa')
        ).add_to(m)
        
        # 添加醒目的圆形标记
        folium.CircleMarker(
            st.session_state.ai_location,
            radius=8,
            popup="🤖 AI当前位置",
            color='red',
            fillColor='red',
            fillOpacity=0.8,
            weight=3
        ).add_to(m)
        
        # 添加AI视野范围
        folium.Circle(
            st.session_state.ai_location,
            radius=Config.AI_VISION_RADIUS,
            color='red',
            weight=1,
            fill=True,
            fillColor='red',
            fillOpacity=0.1,
            popup=f'AI视野范围({Config.AI_VISION_RADIUS}米)'
        ).add_to(m)
    
    # 添加探索路径（AI的移动轨迹）
    if len(st.session_state.exploration_path) > 1:
        path_coords = [[point[0], point[1]] for point in st.session_state.exploration_path]
        
        # 添加轨迹阴影效果
        folium.PolyLine(
            locations=path_coords,
            color='#000000',
            weight=7,
            opacity=0.3
        ).add_to(m)
        
        # 主轨迹线
        folium.PolyLine(
            locations=path_coords,
            color='#FF6B35',  # 更鲜艳的橙红色
            weight=5,
            opacity=0.9,
            popup='🤖 AI探索轨迹',
            tooltip='AI移动路径'
        ).add_to(m)
        
        # 在路径上添加方向指示点（减少密度，提高可读性）
        path_length = len(st.session_state.exploration_path)
        step = max(1, path_length // 10)  # 最多显示10个方向点
        
        for i in range(0, path_length-1, step):
            point = st.session_state.exploration_path[i]
            # 计算进度百分比
            progress = (i / (path_length - 1)) * 100
            
            folium.CircleMarker(
                [point[0], point[1]],
                radius=4,
                color='#FF6B35',
                fillColor='#FFFFFF',
                fillOpacity=0.8,
                weight=2,
                popup=f'🚶 轨迹点 {i+1}\n进度: {progress:.1f}%',
                tooltip=f'轨迹点 {i+1}'
            ).add_to(m)
        
        # 添加起点标记
        start_point = st.session_state.exploration_path[0]
        folium.Marker(
            [start_point[0], start_point[1]],
            popup='🚀 探索起点',
            tooltip='AI探索起点',
            icon=folium.Icon(color='green', icon='play', prefix='fa')
        ).add_to(m)
        
        # 添加终点标记（当前位置）
        if len(st.session_state.exploration_path) > 1:
            end_point = st.session_state.exploration_path[-1]
            folium.Marker(
                [end_point[0], end_point[1]],
                popup='📍 当前位置',
                tooltip='AI当前位置',
                icon=folium.Icon(color='red', icon='stop', prefix='fa')
            ).add_to(m)
    
    # 添加道路网络（如果有本地道路数据）
    if hasattr(st.session_state, 'roads_data') and st.session_state.roads_data:
        for road in st.session_state.roads_data:
            if 'coordinates' in road and road['coordinates']:
                # 检查坐标是否已经是[lat, lng]格式
                first_coord = road['coordinates'][0]
                if isinstance(first_coord, list) and len(first_coord) == 2:
                    # 如果第一个坐标的第一个值在纬度范围内(通常-90到90)，说明已经是[lat, lng]格式
                    if -90 <= first_coord[0] <= 90:
                        road_coords = road['coordinates']  # 已经是[lat, lng]格式
                    else:
                        # 需要转换为[lat, lng]格式
                        road_coords = [[coord[1], coord[0]] for coord in road['coordinates']]
                else:
                    road_coords = road['coordinates']  # 保持原格式
                
                folium.PolyLine(
                    locations=road_coords,
                    color='gray',
                    weight=3,
                    opacity=0.8,
                    popup=f"道路: {road.get('name', '未知道路')}",
                    tooltip=road.get('name', '道路')
                ).add_to(m)
    
    # 添加POI标记（区分已访问和未访问，第三种探索方式的已访问POI显示红色）
    visited_pois = set()
    current_exploration_mode = None
    if hasattr(st.session_state, 'ai_status') and st.session_state.ai_status:
        visited_pois = set(st.session_state.ai_status.get('visited_pois', []))
    if hasattr(st.session_state, 'exploration_mode'):
        current_exploration_mode = st.session_state.exploration_mode
    
    for poi in st.session_state.pois_data:
        # 检查POI是否已被访问
        is_visited = poi['name'] in visited_pois
        
        # 根据访问状态确定颜色
        if is_visited:
            # 所有已访问POI统一显示橙色
            poi_color = 'orange'
            poi_icon = 'check'
        else:
            # 未访问POI显示绿色
            poi_color = 'green'
            poi_icon = 'info-sign'
        
        # 转换POI位置格式：从字典转为列表
        if isinstance(poi['location'], dict):
            location = [poi['location']['latitude'], poi['location']['longitude']]
        else:
            location = poi['location']
        
        folium.Marker(
            location,
            popup=f"{poi['name']}\n{poi['type']}\n{poi['address']}{('\n✅ 已访问' if is_visited else '\n⭕ 未访问')}",
            tooltip=f"{poi['name']} {'✅' if is_visited else '⭕'}",
            icon=folium.Icon(color=poi_color, icon=poi_icon)
        ).add_to(m)
    
    # 添加图例（如果有本地数据）
    if hasattr(st.session_state, 'local_data_loaded') and st.session_state.local_data_loaded:
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 20px; left: 20px; width: 220px; height: auto; 
                    background-color: rgba(255, 255, 255, 0.95); 
                    border: 2px solid #333; 
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
                    z-index: 9999; 
                    font-family: 'Microsoft YaHei', Arial, sans-serif;
                    font-size: 13px; 
                    padding: 15px;
                    line-height: 1.6;">
        <div style="margin-bottom: 10px;">
            <b style="color: #333; font-size: 15px;">本地数据图例</b>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 8px;">
            <i class="fa fa-circle" style="color: #666; margin-right: 8px; font-size: 12px;"></i>
            <span style="color: #333;">道路网络</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 8px;">
            <i class="fa fa-map-marker" style="color: #28a745; margin-right: 8px; font-size: 14px;"></i>
            <span style="color: #333;">未访问POI</span>
        </div>
        <div style="display: flex; align-items: center;">
            <i class="fa fa-map-marker" style="color: #fd7e14; margin-right: 8px; font-size: 14px;"></i>
            <span style="color: #333;">已访问POI</span>
        </div>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

def sidebar_controls():
    """侧边栏控制组件"""
    st.sidebar.title("🗺️ AI地图探索控制")
    
    # 模型选择
    st.sidebar.header("0. 模型选择")
    model_display = st.sidebar.selectbox(
        "选择大模型",
        ["通义千问", "DeepSeek", "ChatGPT"],
        index=0,
        help="选择用于探索和评估的大语言模型"
    )
    
    provider_map = {
        "通义千问": "qwen",
        "DeepSeek": "deepseek",
        "ChatGPT": "openai"
    }
    st.session_state.model_provider = provider_map[model_display]
    
    # 区域选择部分
    st.sidebar.header("1. 区域选择")
    
    # 预设区域选择
    preset_areas = {
        # 中国区域（6个）
        "北京天安门": [[39.9042, 116.4074], [[39.910, 116.400], [39.910, 116.415], [39.898, 116.415], [39.898, 116.400]]],
        "上海外滩": [[31.2304, 121.4737], [[31.240, 121.465], [31.240, 121.485], [31.220, 121.485], [31.220, 121.465]]],
        "广州塔": [[23.1291, 113.2644], [[23.135, 113.260], [23.135, 113.270], [23.123, 113.270], [23.123, 113.260]]],
        "长沙五一广场": [[28.1956, 112.9823], [[28.203, 112.975], [28.203, 112.990], [28.188, 112.990], [28.188, 112.975]]],
        "武汉黄鹤楼": [[30.5928, 114.3055], [[30.600, 114.298], [30.600, 114.313], [30.585, 114.313], [30.585, 114.298]]],
        "晋中市榆次区": [[37.6971, 112.7085], [[37.705, 112.701], [37.705, 112.716], [37.689, 112.716], [37.689, 112.701]]],
        
        # 北美区域（5个）
        "纽约时代广场": [[40.7580, -73.9855], [[40.766983, -73.973617], [40.766983, -73.997383], [40.749017, -73.997383], [40.749017, -73.973617]]],
        "洛杉矶好莱坞": [[34.1022, -118.3406], [[34.111183, -118.329267], [34.111183, -118.351933], [34.093217, -118.351933], [34.093217, -118.329267]]],
        "旧金山联合广场": [[37.7879, -122.4075], [[37.796883, -122.396167], [37.796883, -122.418833], [37.778917, -122.418833], [37.778917, -122.396167]]],
        "芝加哥千禧公园": [[41.8826, -87.6226], [[41.891583, -87.610533], [41.891583, -87.634667], [41.873617, -87.634667], [41.873617, -87.610533]]],
        "多伦多CN塔": [[43.6426, -79.3871], [[43.651583, -79.374267], [43.651583, -79.399933], [43.633617, -79.399933], [43.633617, -79.374267]]],
        
        # 欧洲区域（5个）
        "伦敦大本钟": [[51.4994, -0.1245], [[51.508383, -0.109738], [51.508383, -0.139262], [51.490417, -0.139262], [51.490417, -0.109738]]],
        "巴黎埃菲尔铁塔": [[48.8584, 2.2945], [[48.867383, 2.307833], [48.867383, 2.281167], [48.849417, 2.281167], [48.849417, 2.307833]]],
        "罗马斗兽场": [[41.8902, 12.4922], [[41.899183, 12.504267], [41.899183, 12.480133], [41.881217, 12.480133], [41.881217, 12.504267]]],
        "柏林勃兰登堡门": [[52.5163, 13.3777], [[52.525283, 13.392462], [52.525283, 13.362938], [52.507317, 13.362938], [52.507317, 13.392462]]],
        "维也纳美泉宫": [[48.2082, 16.3738], [[48.216, 16.366], [48.216, 16.381], [48.200, 16.381], [48.200, 16.366]]]
    }
    
    selected_area = st.sidebar.selectbox(
        "选择预设区域",
        ["自定义"] + list(preset_areas.keys())
    )
    
    # 检查区域是否发生变化
    if 'current_selected_area' not in st.session_state:
        st.session_state.current_selected_area = selected_area
    
    # 如果区域发生变化，切换区域并重置相关状态
    if selected_area != st.session_state.current_selected_area and selected_area != "自定义":
        # 调用后端API切换区域
        switch_result = call_backend_api("/exploration/switch_region", "POST", {"region_name": selected_area})
        if switch_result and switch_result.get('success'):
            st.sidebar.success(f"已切换到区域: {selected_area}")
        else:
            st.sidebar.error(f"切换区域失败: {selected_area}")
        
        # 重置前端状态但保持区域相关数据
        center, boundary = preset_areas[selected_area]
        st.session_state.ai_location = center
        st.session_state.exploration_boundary = boundary
        st.session_state.current_selected_area = selected_area
        
        # 清除探索相关状态
        st.session_state.is_exploring = False
        st.session_state.exploration_path = []
        st.session_state.ai_status = {}
        st.session_state.exploration_report = None
        
        # 清除本地数据加载状态，强制重新加载
        if hasattr(st.session_state, 'local_data_loaded'):
            st.session_state.local_data_loaded = False
        if hasattr(st.session_state, 'loaded_region'):
            del st.session_state.loaded_region
        
        st.rerun()
    
    if selected_area != "自定义":
        center, boundary = preset_areas[selected_area]
        if st.sidebar.button("应用预设区域"):
            st.session_state.ai_location = center
            st.session_state.exploration_boundary = boundary
            st.session_state.drawing_mode = False  # 关闭画点模式
            st.rerun()
        
        # 为所有预设区域显示本地数据导入选项
        st.sidebar.subheader("🧪 本地数据功能")
        use_local_data = st.sidebar.checkbox("导入本地数据", key="use_local_data")
         
        if use_local_data:
            st.sidebar.info(f"✅ 已启用{selected_area}本地数据模式")
            st.sidebar.write("将使用本地道路和POI数据进行探索")
            
            # 存储本地数据模式状态和当前区域
            st.session_state.local_data_mode = True
            st.session_state.current_region = selected_area
            
            # 立即加载本地POI和道路数据
            if not hasattr(st.session_state, 'local_data_loaded') or not st.session_state.local_data_loaded or st.session_state.get('loaded_region') != selected_area:
                with st.spinner(f"正在加载{selected_area}的本地shapefile数据..."):
                    # 使用本地shapefile加载器，传入区域名称
                    result = load_local_shapefile_data(selected_area)
                    
                    if 'error' in result:
                        st.sidebar.error(f"❌ 加载本地数据时出错: {result['error']}")
                        st.session_state.local_data_loaded = False
                    else:
                        poi_success = result['poi_success']
                        road_success = result['road_success']
                        
                        if poi_success:
                            st.session_state.pois_data = result['pois']
                            st.sidebar.success(f"✅ 成功加载{len(result['pois'])}个本地POI")
                        else:
                            st.sidebar.error(f"❌ POI文件不存在: {result.get('poi_file', 'unknown')}")
                        
                        if road_success:
                            st.session_state.roads_data = result['roads']
                            st.sidebar.success(f"✅ 成功加载{len(result['roads'])}条道路")
                        else:
                            st.sidebar.error(f"❌ 道路文件不存在: {result.get('road_file', 'unknown')}")
                        
                        # 只有当POI和道路数据都加载成功时才标记为已加载
                        if poi_success and road_success:
                            st.session_state.local_data_loaded = True
                            st.session_state.loaded_region = selected_area  # 记录已加载的区域
                            st.sidebar.info("🗺️ 本地shapefile数据加载完成，地图将显示POI点和道路网络")
                        else:
                            st.session_state.local_data_loaded = False
            
            # 显示探索方式选择
            st.sidebar.subheader("🎯 探索方式选择")
            exploration_mode_display = st.sidebar.selectbox(
                "选择探索方式",
                ["随机POI探索", "最近距离探索", "最短路径探索"],
                key="exploration_mode_display"
            )
            
            # 映射显示名称到后端识别的名称
            exploration_mode_mapping = {
                "随机POI探索": "随机POI探索",
                "最近距离探索": "最近距离探索", 
                "最短路径探索": "随机选择两个POI进行最短路径探索"
            }
            
            # 存储后端识别的探索方式
            st.session_state.exploration_mode = exploration_mode_mapping[exploration_mode_display]
            
            # 显示当前选择的探索方式说明
            if exploration_mode_display == "随机POI探索":
                st.sidebar.write("🎲 AI会随机选择POI进行探索")
            elif exploration_mode_display == "最近距离探索":
                st.sidebar.write("📍 AI会选择离自己最近的POI去进行探索")
            elif exploration_mode_display == "最短路径探索":
                st.sidebar.write("🛣️ AI会在两个随机POI之间进行最短路径探索")
        else:
            # 清除本地数据模式状态
            if hasattr(st.session_state, 'local_data_mode'):
                st.session_state.local_data_mode = False
            if hasattr(st.session_state, 'exploration_mode'):
                del st.session_state.exploration_mode
            if hasattr(st.session_state, 'local_data_loaded'):
                st.session_state.local_data_loaded = False
                st.session_state.pois_data = []  # 清除本地POI数据
                st.session_state.roads_data = []  # 清除本地道路数据
                st.sidebar.info("已清除本地数据")
    else:
        # 自定义区域的画点控制
        st.sidebar.subheader("画点模式控制")
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("🖱️ 开始画点", disabled=st.session_state.drawing_mode):
                st.session_state.drawing_mode = True
                st.session_state.ai_position_mode = False  # 关闭AI位置设置模式
                st.sidebar.success("画点模式已启动！点击地图添加边界点")
                st.rerun()
        
        with col2:
            if st.button("⏹️ 结束画点", disabled=not st.session_state.drawing_mode):
                st.session_state.drawing_mode = False
                st.sidebar.info("画点模式已关闭")
                st.rerun()
        
        # 显示当前画点状态
        if st.session_state.drawing_mode:
            st.sidebar.info("🎯 画点模式已激活，点击地图添加边界点")
        else:
            st.sidebar.info("💡 请先点击'开始画点'按钮激活画点模式")
    
    # 手动设置边界
    st.sidebar.subheader("手动设置边界")
    if st.sidebar.button("清除边界"):
        st.session_state.exploration_boundary = []
        st.session_state.pois_data = []  # 清除POI数据
        st.rerun()
    
    # 显示当前边界点数
    st.sidebar.write(f"当前边界点数：{len(st.session_state.exploration_boundary)}")
    
    # 如果边界点足够，提供获取POI的按钮
    if len(st.session_state.exploration_boundary) >= 3:
        if st.sidebar.button("获取区域POI"):
            boundary_data = {
                "points": [
                    {"latitude": point[0], "longitude": point[1]} 
                    for point in st.session_state.exploration_boundary
                ]
            }
            poi_result = call_backend_api("/poi/polygon", "POST", boundary_data)
            if poi_result and poi_result.get('success'):
                st.session_state.pois_data = poi_result.get('data', [])
                st.sidebar.success(f"成功获取{len(st.session_state.pois_data)}个POI")
            else:
                st.sidebar.error("获取POI失败")
            st.rerun()
    
    # AI位置设置
    st.sidebar.header("2. AI位置设置")
    
    # AI位置设置模式控制
    st.sidebar.subheader("位置设置方式")
    
    # 地图点击设置AI位置
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("🎯 地图选点", disabled=st.session_state.ai_position_mode):
            st.session_state.ai_position_mode = True
            st.session_state.drawing_mode = False  # 关闭边界画点模式
            st.sidebar.success("AI位置设置模式已启动！点击地图设置AI位置")
            st.rerun()
    
    with col2:
        if st.button("⏹️ 结束选点", disabled=not st.session_state.ai_position_mode):
            st.session_state.ai_position_mode = False
            st.sidebar.info("AI位置设置模式已关闭")
            st.rerun()
    
    # 显示当前AI位置设置状态
    if st.session_state.ai_position_mode:
        st.sidebar.info("🎯 AI位置设置模式已激活，点击地图设置AI位置")
    else:
        st.sidebar.info("💡 可通过地图选点或手动输入坐标设置AI位置")
    
    # 手动输入坐标
    st.sidebar.subheader("手动输入坐标")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        ai_lat = st.number_input("纬度", value=st.session_state.ai_location[0], format="%.6f")
    with col2:
        ai_lng = st.number_input("经度", value=st.session_state.ai_location[1], format="%.6f")
    
    if st.sidebar.button("📍 设置AI位置"):
        st.session_state.ai_location = [ai_lat, ai_lng]
        st.sidebar.success(f"AI位置已设置为: {ai_lat:.6f}, {ai_lng:.6f}")
        st.rerun()
    
    # 显示当前AI位置
    st.sidebar.write(f"**当前AI位置：** {st.session_state.ai_location[0]:.6f}, {st.session_state.ai_location[1]:.6f}")

    # 记忆模式（提前于探索控制，确保按钮读取到最新选择）
    # 记忆模式模块已提前至“探索控制”之前，这里删除重复渲染

    # 探索控制
    st.sidebar.header("3. 探索控制")
    
    # 探索参数设置
    st.sidebar.subheader("探索参数")
    exploration_rounds = st.sidebar.number_input(
        "探索轮数", 
        min_value=1, 
        max_value=10, 
        value=1,
        help="AI在完成所有POI探索后，是否继续进行下一轮探索以完善记忆"
    )
    
    # 初始化探索
    if st.sidebar.button("初始化探索", disabled=len(st.session_state.exploration_boundary) < 3):
        init_data = {
            "start_location": {
                "latitude": st.session_state.ai_location[0],
                "longitude": st.session_state.ai_location[1]
            },
            "boundary": {
                "points": [
                    {"latitude": point[0], "longitude": point[1]} 
                    for point in st.session_state.exploration_boundary
                ]
            },
            "use_local_data": getattr(st.session_state, 'local_data_mode', False),
            "exploration_mode": getattr(st.session_state, 'exploration_mode', 'random_poi'),
            "memory_mode": (lambda: {"原始": "raw", "普通": "context", "图": "graph", "地图": "map"}.get(st.session_state.get('selected_memory_mode','普通'), 'context'))(),
            "max_rounds": int(exploration_rounds),
            "model_provider": st.session_state.get('model_provider', 'qwen')
        }
        
        result = call_backend_api("/exploration/init", "POST", init_data)
        if result and result.get('success'):
            if getattr(st.session_state, 'local_data_mode', False):
                st.sidebar.success("本地数据探索初始化成功！")
                # 如果使用本地数据，获取本地POI数据
                local_poi_result = call_backend_api("/exploration/local_pois")
                if local_poi_result and local_poi_result.get('success'):
                    poi_data = local_poi_result.get('data', [])
                    st.session_state.pois_data = poi_data
                    st.sidebar.info(f"已加载{len(poi_data)}个本地POI")
            else:
                st.sidebar.success("探索初始化成功！")
        else:
            st.sidebar.error("探索初始化失败！")
    
    # 开始/停止探索
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("开始探索", disabled=st.session_state.is_exploring):
            # 确保session_state有当前选择的模式
            if 'selected_memory_mode' not in st.session_state:
                st.session_state.selected_memory_mode = '普通'
                
            # 获取当前选择的模式
            current_mode = {"原始": "raw", "普通": "context", "图": "graph", "地图": "map"}.get(
                st.session_state.selected_memory_mode, 'context'
            )
            print(f"[DEBUG] 前端开始探索-当前选择={st.session_state.selected_memory_mode}, 映射={current_mode}")
            print(f"[DEBUG] 前端session_state.selected_memory_mode={st.session_state.selected_memory_mode}")
            print(f"[DEBUG] 前端session_state.selected_memory_mode_backend={st.session_state.get('selected_memory_mode_backend')}")
            
            # 再次确认后端模式设置
            try:
                mode_result = call_backend_api("/memory/mode", "POST", {"mode": current_mode})
                print(f"[DEBUG] 前端开始探索-设置模式结果={mode_result}")
            except Exception as e:
                print(f"[DEBUG] 前端开始探索-设置模式异常={e}")
                
            result = call_backend_api("/exploration/start", "POST", {"memory_mode": current_mode})
            
            if result:
                print(f"[DEBUG] 后端返回的memory_mode={result.get('memory_mode')}")
            if result and result.get('success'):
                st.session_state.is_exploring = True
                
                # 如果还没有POI数据，自动获取边界内的POI
                if st.session_state.exploration_boundary and not st.session_state.pois_data:
                    boundary_data = {
                        "points": [
                            {"latitude": point[0], "longitude": point[1]} 
                            for point in st.session_state.exploration_boundary
                        ]
                    }
                    poi_result = call_backend_api("/poi/polygon", "POST", boundary_data)
                    if poi_result and poi_result.get('success'):
                        st.session_state.pois_data = poi_result.get('data', [])
                        st.sidebar.success(f"探索已开始！发现{len(st.session_state.pois_data)}个POI")
                    else:
                        st.sidebar.success("探索已开始！")
                else:
                    st.sidebar.success(f"探索已开始！当前有{len(st.session_state.pois_data)}个POI")
                st.rerun()
    
    with col2:
        if st.button("停止探索", disabled=not st.session_state.is_exploring):
            print("用户点击停止探索按钮")
            result = call_backend_api("/exploration/stop", "POST")
            
            
            if result and result.get('success'):
                print("停止探索成功，更新前端状态")
                st.session_state.is_exploring = False
                st.session_state.exploration_report = result.get('report')
                eq_payload = result.get('evaluation_questions') or {}
                st.session_state.evaluation_region = eq_payload.get('region')
                st.session_state.evaluation_questions_list = eq_payload.get('questions') or []
                st.session_state.evaluation_markdown_path = eq_payload.get('markdown_path')
                # 触发评估模块
                st.session_state.show_evaluation = True
                print(f"设置show_evaluation为True: {st.session_state.show_evaluation}")
                st.sidebar.success("探索已停止！")
                st.rerun()
            else:
                print("停止探索失败")
                st.sidebar.error("停止探索失败，请重试")
    
    # 注意：POI将在AI开始探索时自动获取
    
    # 探索状态显示
    st.sidebar.header("4. 探索状态")
    status_result = call_backend_api("/exploration/status")
    if status_result and status_result.get('success'):
        status = status_result.get('data', {})
        ridx = int(status.get('round_index') or 1)
        st.sidebar.write(f"当前轮次：{ridx}")
    
    if st.session_state.is_exploring:
        st.sidebar.info("🤖 AI正在探索中...")
        
        # 获取实时状态
        if status_result and status_result.get('success'):
            st.sidebar.write(f"已访问POI：{status.get('visited_poi_count', 0)}")
            st.sidebar.write(f"探索距离：{status.get('exploration_distance', 0):.0f}米")
            st.sidebar.write(f"探索步骤：{status.get('exploration_steps', 0)}")
            if status.get('exploration_complete'):
                ridx = int(status.get('round_index') or 1)
                st.sidebar.success(f"✅ 已探索全部POI（第{ridx}轮），已自动开启下一轮")
            
            # 更新AI位置和探索路径
            current_loc = status.get('current_location')
            if current_loc:
                # 更新AI当前位置
                st.session_state.ai_location = current_loc
                
            # 更新探索路径（使用后端返回的完整路径数据）
            backend_path = status.get('exploration_path', [])
            if backend_path:
                st.session_state.exploration_path = backend_path
                    
            # 显示AI当前状态
            ai_status = status.get('current_status', '未知')
            st.sidebar.write(f"AI状态：{ai_status}")
            
            # 显示最近的决策信息
            last_decision = status.get('last_decision')
            if last_decision:
                st.sidebar.write(f"最近行动：{last_decision.get('action', '未知')}")
                if last_decision.get('target'):
                    st.sidebar.write(f"目标：{last_decision.get('target', '未知')}")
            
            # 保存状态到session_state以供其他组件使用
            st.session_state.ai_status = status
    else:
        st.sidebar.info("🛑 AI未在探索")

    st.sidebar.header("5. 记忆模式")
    
    # 确保session_state有当前选择的模式
    if 'selected_memory_mode' not in st.session_state:
        st.session_state.selected_memory_mode = '普通'
    
    # 调试：显示当前session_state中的模式选择
    print(f"[DEBUG] 前端UI-当前session_state.selected_memory_mode={st.session_state.get('selected_memory_mode')}")
    
    # 使用index参数确保radio显示正确的选中状态
    mode_options = ["原始", "普通", "图", "地图"]
    current_index = mode_options.index(st.session_state.selected_memory_mode) if st.session_state.selected_memory_mode in mode_options else 1
    
    memory_mode_display = st.sidebar.radio(
        "选择记忆模式",
        mode_options,
        index=current_index,
        key="memory_mode_radio"
    )
    
    # 立即更新session_state
    if memory_mode_display != st.session_state.selected_memory_mode:
        st.session_state.selected_memory_mode = memory_mode_display
        print(f"[DEBUG] 前端UI-模式更新：{st.session_state.selected_memory_mode} -> {memory_mode_display}")
    
    print(f"[DEBUG] 前端UI-用户选择={memory_mode_display}, session_state值={st.session_state.get('selected_memory_mode')}")
    
    mode_mapping = {"原始": "raw", "普通": "context", "图": "graph", "地图": "map"}
    selected_mode = mode_mapping[memory_mode_display]
    try:
        prev_mode = st.session_state.get('selected_memory_mode_backend', None)
        if selected_mode != prev_mode:
            print(f"[DEBUG] 前端UI-模式变更：{prev_mode} -> {selected_mode}")
            st.session_state.selected_memory_mode_backend = selected_mode
            call_backend_api("/memory/mode", "POST", {"mode": selected_mode})
    except Exception as e:
        print(f"[DEBUG] 前端UI-设置模式失败: {e}")
    if selected_mode == "graph":
        res = call_backend_api("/memory/graph", "GET")
        if res and res.get("success"):
            data = res.get("data") or {}
            st.sidebar.write(f"图节点数：{len(data.get('nodes', []))}")
            st.sidebar.write(f"图边数：{len(data.get('edges', []))}")
            st.sidebar.write(f"POI关系数：{len(data.get('poi_relations', []))}")
    elif selected_mode == "map":
        res = call_backend_api("/memory/map", "GET")
        if res and res.get("success"):
            data = res.get("data") or {}
            cells = (data.get("road_grid", {}) or {}).get("cells", [])
            st.sidebar.write(f"栅格道路格子数：{len(cells)}")
            st.sidebar.write(f"节点数：{len(data.get('nodes', []))}")



def _get_eval_questions_list():
    qs = st.session_state.get('evaluation_questions_list')
    if isinstance(qs, list) and qs:
        return qs
    return EVALUATION_QUESTIONS

def show_evaluation_module():
    """显示评估模块"""
    print(f"show_evaluation_module被调用，show_evaluation状态: {st.session_state.show_evaluation}")
    if not st.session_state.show_evaluation:
        return
        
    print("显示评估模块")
    st.subheader("🧠 AI空间意识评估")
    st.info("探索完成！现在开始评估AI的空间意识能力。")
    
    # 创建两列布局：左侧问题列表，右侧答题区域
    eval_col1, eval_col2 = st.columns([2, 1])
    
    with eval_col1:
        st.write("**📋 评估问题列表**")
        
        qs_list = _get_eval_questions_list()
        for i, question in enumerate(qs_list, 1):
            qtext = getattr(question, 'question', None) or (question.get('question') if isinstance(question, dict) else '')
            qcat = getattr(question, 'category', None) or (question.get('category') if isinstance(question, dict) else '')
            qopts = getattr(question, 'options', None) or (question.get('options') if isinstance(question, dict) else [])
            qans = getattr(question, 'correct_answer', None) or (question.get('correct_answer') if isinstance(question, dict) else '')
            with st.expander(f"问题 {i}: {str(qtext)[:30]}..."):
                st.write(f"**问题：** {qtext}")
                st.write(f"**类型：** {qcat}")
                for j, option in enumerate(qopts, 1):
                    st.write(f"{chr(64+j)}. {option}")
                st.write(f"**正确答案：** {qans}")
    
    with eval_col2:
        st.write("**🤖 AI答题区域**")
        
        if not st.session_state.ai_answering and not st.session_state.evaluation_result:
            if st.button("🚀 开始AI评估", type="primary"):
                start_ai_evaluation()
        
        elif st.session_state.ai_answering:
            st.info("🤖 AI正在思考和答题中...")
            st.progress(0.5)
            monitor_evaluation_progress()
        
        elif st.session_state.evaluation_result:
            show_evaluation_results()

def start_ai_evaluation():
    """开始AI评估"""
    st.session_state.ai_answering = True
    st.session_state.evaluation_result = None
    
    # 将EvaluationQuestion对象转换为字典格式
    src = _get_eval_questions_list()
    questions_dict = []
    for q in src:
        if isinstance(q, dict):
            questions_dict.append({
                "id": q.get("id"),
                "category": q.get("category"),
                "question": q.get("question"),
                "options": q.get("options"),
                "correct_answer": q.get("correct_answer"),
                "explanation": q.get("explanation"),
                "difficulty": q.get("difficulty"),
            })
        else:
            questions_dict.append({
                "id": getattr(q, "id", None),
                "category": getattr(q, "category", None),
                "question": getattr(q, "question", None),
                "options": getattr(q, "options", []),
                "correct_answer": getattr(q, "correct_answer", None),
                "explanation": getattr(q, "explanation", None),
                "difficulty": getattr(q, "difficulty", None),
            })
    
    # 基于探索报告筛选真实访问过的POI
    visited_poi_details = []
    try:
        report = getattr(st.session_state, 'exploration_report', None)
        visited_poi_ids = set(report.get('visited_pois', [])) if report else set()
        all_pois = getattr(st.session_state, 'pois_data', [])
        if visited_poi_ids and all_pois:
            visited_poi_details = [poi for poi in all_pois if poi.get('id') in visited_poi_ids]
    except Exception as e:
        print(f"构建真实访问POI列表失败: {e}")
        visited_poi_details = []
    
    # 新增：获取道路记忆统计，作为评估上下文的道路节点/道路段数据
    road_memory_summary = None
    try:
        mem_result = call_backend_api("/qa/memory", "GET")
        if mem_result and mem_result.get('success'):
            road_memory_summary = mem_result.get('data')
    except Exception as e:
        print(f"获取道路记忆摘要失败: {e}")
        road_memory_summary = None
    
    # 调用后端API开始评估
    evaluation_data = {
        "questions": questions_dict,
        "exploration_data": {
            "ai_location": st.session_state.ai_location,
            "exploration_path": st.session_state.exploration_path,
            "visited_pois": visited_poi_details,
            "exploration_report": st.session_state.exploration_report,
            "road_memory": road_memory_summary
        },
        "model_provider": st.session_state.get('model_provider', 'qwen')
    }
    try:
        mem = call_backend_api("/qa/memory", "GET")
        mode = None
        if mem and mem.get("success"):
            mode = ((mem.get("data") or {}).get("mode") or None)
        if mode in ("graph", "map"):
            if mode == "graph":
                g = call_backend_api("/memory/graph", "GET")
                snap = g.get("data") if (g and g.get("success")) else {}
                nodes = snap.get("nodes", [])
                edges = snap.get("edges", [])
                rels = snap.get("poi_relations", [])
                lines = []
                lines.append("[模式]\n- type: graph")
                lines.append("[数据约束]\n- nodes:{id,type}\n- edges:{road_id,length_m,from_id,to_id}\n- poi_relations:{poi_a_id,poi_b_id,direction_deg,distance_m,road_id}")
                lines.append(f"[图节点汇总]\n- 节点数: {len(nodes)}\n- POI节点数: {len([n for n in nodes if (n.get('type')=='poi')])}\n- 道路节点数: {len([n for n in nodes if (n.get('type')=='road_node')])}")
                lines.append("[图边列表]")
                for e in edges[:50]:
                    lines.append(f"- road_id: {e.get('road_id')}, from: {e.get('from_id')}, to: {e.get('to_id')}, length: {int(e.get('length_m') or 0)}m")
                lines.append("[POI相对关系]")
                for r in rels[:50]:
                    rid = r.get('road_id')
                    rid_str = rid if rid else '无'
                    lines.append(f"- {r.get('poi_a_id')} → {r.get('poi_b_id')}: 方向 {int(r.get('direction_deg') or 0)}°，距离 ≈ {int(r.get('distance_m') or 0)}m，道路: {rid_str}")
                lines.append("[回答规则]\n1) 仅使用图连通性与POI相对关系\n2) 路径比较按edges的length_m累加\n3) 方向使用direction_deg\n4) 输出不引入未提供字段")
                evaluation_data["exploration_data"]["context_text"] = "\n".join(lines)
                evaluation_data["exploration_data"]["context_mode"] = "graph"
            elif mode == "map":
                m = call_backend_api("/memory/map", "GET")
                snap = m.get("data") if (m and m.get("success")) else {}
                nodes = snap.get("nodes", [])
                grid = (snap.get("road_grid") or {})
                cells = grid.get("cells", [])
                lines = []
                lines.append("[模式]\n- type: map")
                lines.append("[数据约束]\n- nodes:{id,name,type,i,j}\n- road_grid:{grid_size,cells:[{i,j}]}")
                lines.append(f"[栅格参数]\n- grid_size: {int(grid.get('grid_size') or 30)}")
                lines.append("[节点列表]")
                for n in nodes[:100]:
                    lines.append(f"- {n.get('id')} ({n.get('name')}) [{n.get('type')}] @ ({int(n.get('i') or 0)},{int(n.get('j') or 0)})")
                lines.append(f"[道路格子]\n- road_cells_count: {len(cells)}")
                lines.append("- road_cells_sample:")
                for c in cells[:100]:
                    lines.append(f"  - ({int(c.get('i') or 0)},{int(c.get('j') or 0)})")
                lines.append("[回答规则]\n1) 仅使用(i,j)与cells\n2) 连通以cells为道路\n3) 相对位置以栅格差值\n4) 输出不引入未提供字段")
                evaluation_data["exploration_data"]["context_text"] = "\n".join(lines)
                evaluation_data["exploration_data"]["context_mode"] = "map"
    except Exception:
        pass
    
    try:
        latest = call_backend_api("/exploration/data", "GET")
        if latest and latest.get("success"):
            evaluation_data["exploration_data"]["new_exploration_data"] = latest.get("data")
            data = latest.get("data")
            if (mode == "context") and data:
                lines = []
                lines.append("POI点单元记录（按时间顺序）：")
                poi_units = data.get("poi_units", [])
                for idx, unit in enumerate(poi_units, start=1):
                    poi_name = ((unit.get("poi") or {}).get("name")) or f"POI_{idx}"
                    lines.append(f"{idx}) POI：{poi_name}")
                    vp_list = unit.get("visible_pois") or []
                    lines.append("   - 视野内POI（方向度数；距离米）：")
                    for vp in vp_list:
                        vn = vp.get("name")
                        vd = vp.get("direction_deg")
                        vm = vp.get("distance_m")
                        vn_str = vn if vn is not None else "未知POI"
                        vd_str = f"{int(vd)}" if isinstance(vd, (int, float)) else "未知"
                        vm_str = f"{int(vm)}" if isinstance(vm, (int, float)) else "未知"
                        lines.append(f"     • {vn_str}：方向 {vd_str}°，距离 ≈ {vm_str}m")
                fr = data.get("full_route") or {}
                lines.append("")
                lines.append("完整行驶路径（仅方向与距离）：")
                # 构建时间序POI名称列表用于路径编号
                poi_seq = []
                for unit in poi_units:
                    nm = ((unit.get("poi") or {}).get("name"))
                    if isinstance(nm, str) and nm.strip():
                        poi_seq.append(nm)
                poi_idx_map = {nm: i for i, nm in enumerate(poi_seq, start=1)}
                start_name = fr.get("start_name") or "起点"
                prefix_start = f"路径{poi_idx_map.get(start_name)} " if start_name in poi_idx_map else ""
                lines.append(f"- {prefix_start}起点：{start_name}")
                for seg in fr.get("segments", []):
                    to_name = seg.get("to_name") or "未知终点"
                    deg = seg.get("direction_deg")
                    dist = seg.get("distance_m")
                    deg_str = f"{int(deg)}°" if isinstance(deg, (int, float)) else "未知方向"
                    dist_str = f"≈ {int(dist)}m" if isinstance(dist, (int, float)) else "未知距离"
                    prefix_seg = f"路径{poi_idx_map.get(to_name)} " if to_name in poi_idx_map else ""
                    lines.append(f"→ {prefix_seg}{to_name}（方向 {deg_str}，距离 {dist_str}）")
                sm = data.get("exploration_summary") or {}
                lines.append("")
                lines.append("总和：")
                if sm.get("total_pois_visited") is not None:
                    lines.append(f"已访问POI数量：{int(sm.get('total_pois_visited'))}")
                if sm.get("total_road_nodes_visited") is not None:
                    lines.append(f"已访问道路节点数量（只要Name字段的）：{int(sm.get('total_road_nodes_visited'))}")
                if sm.get("total_distance_meters") is not None:
                    lines.append(f"总探索距离：{int(sm.get('total_distance_meters'))}米")
                if sm.get("total_time_seconds") is not None:
                    lines.append(f"探索时间：{int(sm.get('total_time_seconds'))}秒")
                evaluation_data["exploration_data"]["context_text"] = "\n".join(lines)
                evaluation_data["exploration_data"]["context_mode"] = "context"
    except Exception:
        pass
    result = call_backend_api("/evaluation/start", "POST", evaluation_data)
    
    if result and result.get('success'):
        st.success("评估已开始，AI正在答题...")
        st.rerun()
    else:
        st.error("评估启动失败")
        st.session_state.ai_answering = False

def monitor_evaluation_progress():
    """监控评估进度（优化的异步轮询）"""
    # 检查评估状态
    result = call_backend_api("/evaluation/status")
    
    if result and result.get('success'):
        status = result.get('status')
        progress = result.get('progress', 0)
        current_question = result.get('current_question', 0)
        total_questions = result.get('total_questions', 0)
        
        # 显示进度信息
        if total_questions > 0:
            st.progress(progress / 100.0)
            st.write(f"正在回答第 {current_question}/{total_questions} 题...")
        
        if status == 'completed':
            # 获取评估结果
            result_data = call_backend_api("/evaluation/result")
            if result_data and result_data.get('success'):
                st.session_state.evaluation_result = result_data.get('data')
                st.session_state.ai_answering = False
                st.success("评估完成！")
                st.rerun()
        elif status == 'failed':
            err = result.get('error')
            if err:
                st.error(f"评估失败：{err}")
            else:
                st.error("评估失败")
            st.session_state.ai_answering = False
            st.rerun()
        elif status in ['running', 'started']:
            # 继续轮询，使用更短的间隔
            time.sleep(2)
            st.rerun()
    else:
        # API调用失败，停止轮询
        st.error("无法获取评估状态")
        st.session_state.ai_answering = False

def show_evaluation_results():
    """显示评估结果"""
    if not st.session_state.evaluation_result:
        return
    
    result = st.session_state.evaluation_result
    
    st.success("🎉 评估完成！")
    
    # 显示总体得分
    total_score = result.get('total_score', 0)
    max_score = len(_get_eval_questions_list())
    score_percentage = (total_score / max_score) * 100
    
    st.metric("总体得分", f"{total_score}/{max_score}", f"{score_percentage:.1f}%")
    
    # 显示各类型得分
    type_scores = result.get('type_scores', {})
    if type_scores:
        st.write("**📊 各类型得分：**")
        for eval_type, score_info in type_scores.items():
            st.write(f"- **{eval_type}：** {score_info['correct']}/{score_info['total']} ({score_info['percentage']:.1f}%)")
    
    # 显示详细答题结果
    with st.expander("📝 详细答题结果"):
        answers = result.get('answers', [])
        for i, answer_info in enumerate(answers, 1):
            question = answer_info['question']
            ai_answer = answer_info['ai_answer']
            correct_answer = answer_info['correct_answer']
            is_correct = answer_info['is_correct']
            ai_exp = answer_info.get('ai_explanation') or ""
            
            status_icon = "✅" if is_correct else "❌"
            st.write(f"**{status_icon} 问题 {i}：** {question[:50]}...")
            st.write(f"AI答案：{ai_answer} | 正确答案：{correct_answer}")
            if ai_exp:
                st.write(f"AI解释：{ai_exp}")
    
    # 重新评估按钮
    if st.button("🔄 重新评估"):
        st.session_state.evaluation_result = None
        st.session_state.ai_answering = False
        st.session_state.show_evaluation = False
        st.rerun()

def main_content():
    """主要内容区域"""
    st.title("🗺️ AI地图探索系统")
    
    # 创建两列布局
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("地图区域")
        
        # 创建并显示地图
        m = create_map()
        map_data = st_folium(
            m, 
            width=800, 
            height=600,
            returned_objects=["last_object_clicked", "last_clicked"]
        )
        
        # 处理地图点击事件
        if map_data['last_clicked']:
            clicked_lat = map_data['last_clicked']['lat']
            clicked_lng = map_data['last_clicked']['lng']
            
            # 显示点击位置信息
            st.info(f"📍 点击位置: {clicked_lat:.6f}, {clicked_lng:.6f}")
            
            # 边界画点模式
            if st.session_state.drawing_mode:
                # 添加到边界点
                if st.button("✅ 添加到边界"):
                    st.session_state.exploration_boundary.append([clicked_lat, clicked_lng])
                    st.success(f"边界点已添加！当前共有 {len(st.session_state.exploration_boundary)} 个边界点")
                    st.rerun()
            
            # AI位置设置模式
            elif st.session_state.ai_position_mode:
                # 设置AI位置
                if st.button("🤖 设置为AI位置"):
                    st.session_state.ai_location = [clicked_lat, clicked_lng]
                    st.session_state.ai_position_mode = False  # 设置完成后自动关闭模式
                    st.success(f"AI位置已设置为: {clicked_lat:.6f}, {clicked_lng:.6f}")
                    st.rerun()
            
            # 无模式激活时不显示任何按钮，避免干扰
            # else:
            #     st.warning("💡 请先在左侧边栏激活'开始画点'或'地图选点'模式")
        
        # 在地图下方显示已访问的POI列表
        st.subheader("🏆 已探索的POI")
        if hasattr(st.session_state, 'ai_status') and st.session_state.ai_status:
            visited_pois = st.session_state.ai_status.get('visited_pois', [])
            if visited_pois:
                # 创建多列布局来显示POI
                cols = st.columns(3)  # 3列显示
                for i, poi_name in enumerate(visited_pois):
                    with cols[i % 3]:
                        st.write(f"✅ {poi_name}")
            else:
                st.info("暂无已访问的POI")
        else:
            st.info("AI尚未开始探索")
    
    # 显示评估模块（在整个页面底部）
    show_evaluation_module()

def auto_refresh():
    """自动刷新AI状态"""
    if st.session_state.is_exploring:
        # 每5秒刷新一次
        time.sleep(5)
        st.rerun()

def main():
    """主函数"""
    # 侧边栏控制
    sidebar_controls()
    
    # 主要内容
    main_content()
    
    # 自动刷新（仅在探索时）
    if st.session_state.is_exploring:
        # 使用Streamlit的自动刷新机制
        import time
        time.sleep(2)  # 等待2秒
        st.rerun()  # 重新运行页面

if __name__ == "__main__":
    main()
