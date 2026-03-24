# 项目配置文件

import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# 加载.env文件
# 获取当前文件所在的目录
current_dir = Path(__file__).resolve().parent
# 获取项目根目录（假设.env在项目根目录下）
root_dir = current_dir.parent
env_path = root_dir / '.env'

# 显式指定 .env 文件路径
load_dotenv(dotenv_path=env_path, override=True)

class Config:
    """项目配置类"""
    
    # 高德地图配置
    AMAP_API_KEY = os.getenv('AMAP_API_KEY', 'YOUR_AMAP_API_KEY')
    AMAP_BASE_URL = 'https://restapi.amap.com/v3'
    
    # 通义千问配置
    DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY', '')
    
    # 其他大模型配置
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY', '')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
    
    # AI探索配置
    AI_VISION_RADIUS = 3000  # AI视野半径（米）
    AI_MOVE_SPEED = 50      # AI移动速度（米/秒）
    AI_MOVE_INTERVAL = 2    # AI移动间隔（秒）
    
    # 地图配置
    DEFAULT_CENTER = [39.9042, 116.4074]  # 默认中心点（北京天安门）
    DEFAULT_ZOOM = 15
    
    # 服务器配置
    BACKEND_HOST = '127.0.0.1'
    BACKEND_PORT = 8000
    FRONTEND_HOST = '127.0.0.1'
    FRONTEND_PORT = 8501
    
    # POI类型配置
    POI_TYPES = {
        '餐饮服务': ['中餐厅', '西餐厅', '快餐厅', '咖啡厅', '茶艺馆'],
        '购物服务': ['购物中心', '超市', '便利店', '专卖店'],
        '生活服务': ['银行', 'ATM', '医院', '药店', '加油站'],
        '体育休闲': ['公园', '健身房', '游泳馆', '电影院'],
        '住宿服务': ['酒店', '宾馆', '民宿'],
        '交通设施': ['地铁站', '公交站', '停车场']
    }
    
    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """获取所有配置"""
        return {
            'amap_api_key': cls.AMAP_API_KEY,
            'dashscope_api_key': cls.DASHSCOPE_API_KEY,
            'deepseek_api_key': cls.DEEPSEEK_API_KEY,
            'openai_api_key': cls.OPENAI_API_KEY,
            'zhipu_api_key': cls.ZHIPU_API_KEY,
            'google_api_key': cls.GOOGLE_API_KEY,
            'anthropic_api_key': cls.ANTHROPIC_API_KEY,
            'openrouter_api_key': cls.OPENROUTER_API_KEY,
            'ai_vision_radius': cls.AI_VISION_RADIUS,
            'ai_move_speed': cls.AI_MOVE_SPEED,
            'ai_move_interval': cls.AI_MOVE_INTERVAL,
            'default_center': cls.DEFAULT_CENTER,
            'default_zoom': cls.DEFAULT_ZOOM,
            'poi_types': cls.POI_TYPES
        }
