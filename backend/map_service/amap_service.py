# 高德地图服务模块

import requests
import asyncio
import aiohttp
import logging
from typing import List, Dict, Tuple, Optional
import json
from config.config import Config

logger = logging.getLogger(__name__)

class AmapService:
    """高德地图服务类"""
    
    def __init__(self):
        self.api_key = Config.AMAP_API_KEY
        self.base_url = Config.AMAP_BASE_URL
        
        # 高德地图瓦片URL模板
        self.tile_url_template = "https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}"
        
        logger.info("高德地图服务初始化完成")
    
    def get_tile_url(self, z: int, x: int, y: int) -> str:
        """
        获取高德地图瓦片URL
        
        Args:
            z: 缩放级别
            x: 瓦片X坐标
            y: 瓦片Y坐标
            
        Returns:
            瓦片URL
        """
        return self.tile_url_template.format(x=x, y=y, z=z)
    
    def get_folium_tile_config(self) -> Dict[str, str]:
        """
        获取Folium地图瓦片配置
        
        Returns:
            Folium瓦片配置字典
        """
        return {
            'tiles': self.tile_url_template,
            'attr': '高德地图',
            'name': '高德地图'
        }
        
    def get_poi_around(self, location: Tuple[float, float], radius: int = 1000, 
                      poi_type: str = '') -> List[Dict]:
        """获取指定位置周围的POI
        
        Args:
            location: (纬度, 经度)
            radius: 搜索半径（米）
            poi_type: POI类型
            
        Returns:
            POI列表
        """
        url = f"{self.base_url}/place/around"
        params = {
            'key': self.api_key,
            'location': f"{location[1]},{location[0]}",  # 高德API使用经度,纬度
            'radius': radius,
            'types': poi_type,
            'output': 'json',
            'extensions': 'all'
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if data.get('status') == '1':
                pois = data.get('pois', [])
                return self._format_pois(pois)
            else:
                print(f"高德API错误: {data.get('info')}")
                return []
                
        except Exception as e:
            print(f"获取POI数据失败: {e}")
            return []
    
    def get_poi_in_polygon(self, polygon: List[Tuple[float, float]], 
                          poi_type: str = '') -> List[Dict]:
        """获取多边形区域内的POI
        
        Args:
            polygon: 多边形顶点列表 [(纬度, 经度), ...]
            poi_type: POI类型
            
        Returns:
            POI列表
        """
        # 将多边形转换为高德API格式
        polygon_str = '|'.join([f"{lng},{lat}" for lat, lng in polygon])
        
        url = f"{self.base_url}/place/polygon"
        params = {
            'key': self.api_key,
            'polygon': polygon_str,
            'types': poi_type,
            'output': 'json',
            'extensions': 'all'
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if data.get('status') == '1':
                pois = data.get('pois', [])
                return self._format_pois(pois)
            else:
                print(f"高德API错误: {data.get('info')}")
                return []
                
        except Exception as e:
            print(f"获取POI数据失败: {e}")
            return []
    
    def _format_pois(self, pois: List[Dict]) -> List[Dict]:
        """格式化POI数据"""
        if not pois:
            return []
            
        formatted_pois = []
        
        for poi in pois:
            if not poi or not isinstance(poi, dict):
                continue
                
            location = poi.get('location', '')
            if not location:
                continue
                
            location_parts = location.split(',')
            if len(location_parts) == 2:
                try:
                    lng, lat = float(location_parts[0]), float(location_parts[1])
                    
                    # 确保POI有基本的必需字段
                    poi_id = poi.get('id')
                    poi_name = poi.get('name')
                    
                    if not poi_id or not poi_name:
                        continue
                    
                    formatted_poi = {
                        'id': poi_id,
                        'name': poi_name,
                        'type': poi.get('type', '未知类型'),
                        'typecode': poi.get('typecode', ''),
                        'address': poi.get('address', ''),
                        'location': [lat, lng],  # 转换为[纬度, 经度]
                        'distance': poi.get('distance', 0),
                        'tel': poi.get('tel', ''),
                        'business_area': poi.get('business_area', ''),
                        'tag': poi.get('tag', '')
                    }
                    formatted_pois.append(formatted_poi)
                except (ValueError, TypeError) as e:
                    print(f"格式化POI数据时出错：{e}，POI数据：{poi}")
                    continue
                    
        return formatted_pois
    
    async def get_poi_around_async(self, location: Tuple[float, float], 
                                  radius: int = 1000, poi_type: str = '') -> List[Dict]:
        """异步获取POI数据"""
        if not location or len(location) != 2:
            print(f"无效的位置参数：{location}")
            return []
            
        url = f"{self.base_url}/place/around"
        params = {
            'key': self.api_key,
            'location': f"{location[1]},{location[0]}",
            'radius': radius,
            'types': poi_type,
            'output': 'json',
            'extensions': 'all'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status != 200:
                        print(f"HTTP错误：{response.status}")
                        return []
                        
                    data = await response.json()
                    
                    if data is None:
                        print("API返回空数据")
                        return []
                        
                    if data.get('status') == '1':
                        pois = data.get('pois', [])
                        formatted_pois = self._format_pois(pois)
                        print(f"成功获取{len(formatted_pois)}个POI")
                        return formatted_pois
                    else:
                        print(f"高德API错误: {data.get('info', '未知错误')}")
                        return []
                        
        except asyncio.TimeoutError:
            print("API请求超时")
            return []
        except Exception as e:
            print(f"异步获取POI数据失败: {e}")
            return []
    
    def calculate_distance(self, point1: Tuple[float, float], 
                          point2: Tuple[float, float]) -> float:
        """计算两点间距离（米）
        
        使用简化的距离计算公式
        """
        import math
        
        lat1, lng1 = point1
        lat2, lng2 = point2
        
        # 转换为弧度
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)
        
        # 计算差值
        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad
        
        # 使用Haversine公式
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # 地球半径（米）
        r = 6371000
        
        return r * c